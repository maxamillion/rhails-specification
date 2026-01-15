"""Model operation executors for OpenShift AI InferenceServices.

This module implements the operation executors for model management operations
including deployment, status queries, listing, scaling, and deletion.
"""

import time
import uuid

from kubernetes.client.rest import ApiException
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.intent import ExecutionResult, OperationRequest
from src.models.openshift import ResourceType
from src.services.audit_logger import AuditLogger
from src.services.openshift_client import OpenShiftClient


class ModelOperationExecutor:
    """Execute model operations against OpenShift AI."""

    def __init__(
        self,
        openshift_client: OpenShiftClient,
        db_session: AsyncSession,
        audit_logger: AuditLogger | None = None,
    ):
        """Initialize model operation executor.

        Args:
            openshift_client: OpenShift API client for resource operations
            db_session: Database session for data persistence
            audit_logger: Optional audit logger for compliance logging
        """
        self.openshift_client = openshift_client
        self.db_session = db_session
        self.audit_logger = audit_logger or AuditLogger(db_session)

    async def execute(self, operation_request: OperationRequest) -> ExecutionResult:
        """Execute operation based on request type.

        Args:
            operation_request: Validated operation request

        Returns:
            ExecutionResult with operation outcome
        """
        # Start timing
        start_time = time.time()

        try:
            # Validate request
            await self.validate_request(operation_request)

            # Check if confirmation required but not provided
            if operation_request.requires_confirmation and not operation_request.confirmation_token:
                return ExecutionResult(
                    execution_id=uuid.uuid4(),
                    operation_id=operation_request.operation_id,
                    status="pending_confirmation",
                    resource_type=operation_request.target_resource,
                    resource_name=operation_request.resource_name or "",
                    result_data={},
                    error_message=None,
                    retry_count=0,
                )

            # Execute based on operation type
            if operation_request.operation_type == "create":
                result = await self.execute_deploy_model(operation_request)
            elif operation_request.operation_type == "get":
                result = await self.execute_get_model_status(operation_request)
            elif operation_request.operation_type == "list":
                result = await self.execute_list_models(operation_request)
            elif operation_request.operation_type == "patch":
                result = await self.execute_scale_model(operation_request)
            elif operation_request.operation_type == "delete":
                result = await self.execute_delete_model(operation_request)
            else:
                raise ValueError(f"Unknown operation type: {operation_request.operation_type}")

            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)

            # Log to audit if logger available
            if self.audit_logger:
                await self.audit_logger.log_operation(
                    user_id=operation_request.user_id,
                    session_id=operation_request.session_id,
                    user_command=f"{operation_request.operation_type} {operation_request.resource_name}",
                    parsed_intent={
                        "operation_type": operation_request.operation_type,
                        "resource": operation_request.target_resource,
                    },
                    openshift_operation=f"{operation_request.operation_type}_{operation_request.target_resource}",
                    operation_result={"status": result.status},
                    duration_ms=duration_ms,
                    operation_error=result.error_message,
                )

            return result

        except ApiException as e:
            duration_ms = int((time.time() - start_time) * 1000)

            # Translate Kubernetes errors to user-friendly messages
            error_message = self._translate_api_error(e)

            # Log error to audit
            if self.audit_logger:
                await self.audit_logger.log_operation(
                    user_id=operation_request.user_id,
                    session_id=operation_request.session_id,
                    user_command=f"{operation_request.operation_type} {operation_request.resource_name}",
                    parsed_intent={
                        "operation_type": operation_request.operation_type,
                        "resource": operation_request.target_resource,
                    },
                    openshift_operation=f"{operation_request.operation_type}_{operation_request.target_resource}",
                    operation_result={"status": "error"},
                    duration_ms=duration_ms,
                    operation_error=error_message,
                )

            return ExecutionResult(
                execution_id=uuid.uuid4(),
                operation_id=operation_request.operation_id,
                status="error",
                resource_type=operation_request.target_resource,
                resource_name=operation_request.resource_name or "",
                result_data={},
                error_message=error_message,
                retry_count=0,
            )

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            error_message = f"Unexpected error: {str(e)}"

            # Log error to audit
            if self.audit_logger:
                await self.audit_logger.log_operation(
                    user_id=operation_request.user_id,
                    session_id=operation_request.session_id,
                    user_command=f"{operation_request.operation_type} {operation_request.resource_name}",
                    parsed_intent={
                        "operation_type": operation_request.operation_type,
                        "resource": operation_request.target_resource,
                    },
                    openshift_operation=f"{operation_request.operation_type}_{operation_request.target_resource}",
                    operation_result={"status": "error"},
                    duration_ms=duration_ms,
                    operation_error=error_message,
                )

            return ExecutionResult(
                execution_id=uuid.uuid4(),
                operation_id=operation_request.operation_id,
                status="error",
                resource_type=operation_request.target_resource,
                resource_name=operation_request.resource_name or "",
                result_data={},
                error_message=error_message,
                retry_count=0,
            )

    async def validate_request(self, operation_request: OperationRequest) -> None:
        """Validate operation request parameters.

        Args:
            operation_request: Request to validate

        Raises:
            ValueError: If required parameters are missing or invalid
        """
        # Deployment validation
        if operation_request.operation_type == "create":
            if not operation_request.resource_name:
                raise ValueError("model_name is required for deployment operations")

            # Validate replicas if provided
            replicas = operation_request.parameters.get("replicas")
            if replicas is not None:
                if not isinstance(replicas, int):
                    raise ValueError(f"replicas must be integer, got {type(replicas).__name__}")

                if replicas < 0 or replicas > 10:
                    raise ValueError("replicas must be between 0 and 10")

        # Scaling validation
        if operation_request.operation_type == "patch":
            if not operation_request.resource_name:
                raise ValueError("model_name is required for scaling operations")

            replicas = operation_request.parameters.get("replicas")
            if replicas is None:
                raise ValueError("replicas is required for scaling operations")

            if not isinstance(replicas, int):
                raise ValueError(f"replicas must be integer, got {type(replicas).__name__}")

            if replicas < 0 or replicas > 10:
                raise ValueError("replicas must be between 0 and 10")

    async def execute_deploy_model(self, operation_request: OperationRequest) -> ExecutionResult:
        """Execute model deployment operation.

        Args:
            operation_request: Deployment request with model configuration

        Returns:
            ExecutionResult with deployment outcome
        """
        name = operation_request.resource_name or ""
        namespace = operation_request.parameters.get("namespace", "default")
        replicas = operation_request.parameters.get("replicas", 1)
        storage_uri = operation_request.parameters.get("storage_uri")
        model_format = operation_request.parameters.get("model_format", "sklearn")

        # Build predictor configuration
        predictor_config = {
            "modelFormat": {"name": model_format},
        }

        if storage_uri:
            predictor_config["storageUri"] = storage_uri

        # Create InferenceService
        result = await self.openshift_client.create_inference_service(
            name=name,
            namespace=namespace,
            predictor_config=predictor_config,
            replicas=replicas,
        )

        return ExecutionResult(
            execution_id=uuid.uuid4(),
            operation_id=operation_request.operation_id,
            status="success",
            resource_type=ResourceType.MODEL_DEPLOYMENT,
            resource_name=name,
            result_data=result,
            error_message=None,
            retry_count=0,
        )

    async def execute_get_model_status(self, operation_request: OperationRequest) -> ExecutionResult:
        """Execute model status query operation.

        Args:
            operation_request: Status query request

        Returns:
            ExecutionResult with model status
        """
        name = operation_request.resource_name or ""
        namespace = operation_request.parameters.get("namespace", "default")

        # Get InferenceService status
        result = await self.openshift_client.get_inference_service(
            name=name,
            namespace=namespace,
        )

        return ExecutionResult(
            execution_id=uuid.uuid4(),
            operation_id=operation_request.operation_id,
            status="success",
            resource_type=ResourceType.MODEL_DEPLOYMENT,
            resource_name=name,
            result_data=result,
            error_message=None,
            retry_count=0,
        )

    async def execute_list_models(self, operation_request: OperationRequest) -> ExecutionResult:
        """Execute list models operation.

        Args:
            operation_request: List request

        Returns:
            ExecutionResult with model list
        """
        namespace = operation_request.parameters.get("namespace", "default")

        # List InferenceServices
        result = await self.openshift_client.list_inference_services(
            namespace=namespace
        )

        return ExecutionResult(
            execution_id=uuid.uuid4(),
            operation_id=operation_request.operation_id,
            status="success",
            resource_type=ResourceType.MODEL_DEPLOYMENT,
            resource_name="",
            result_data=result,
            error_message=None,
            retry_count=0,
        )

    async def execute_scale_model(self, operation_request: OperationRequest) -> ExecutionResult:
        """Execute model scaling operation.

        Args:
            operation_request: Scaling request with replica count

        Returns:
            ExecutionResult with scaling outcome
        """
        name = operation_request.resource_name or ""
        namespace = operation_request.parameters.get("namespace", "default")
        replicas = operation_request.parameters.get("replicas", 1)

        # Patch InferenceService with new replica count
        result = await self.openshift_client.patch_inference_service(
            name=name,
            namespace=namespace,
            patch_data={
                "spec": {
                    "predictor": {
                        "minReplicas": replicas,
                    }
                }
            },
        )

        return ExecutionResult(
            execution_id=uuid.uuid4(),
            operation_id=operation_request.operation_id,
            status="success",
            resource_type=ResourceType.MODEL_DEPLOYMENT,
            resource_name=name,
            result_data=result,
            error_message=None,
            retry_count=0,
        )

    async def execute_delete_model(self, operation_request: OperationRequest) -> ExecutionResult:
        """Execute model deletion operation.

        Args:
            operation_request: Deletion request

        Returns:
            ExecutionResult with deletion outcome
        """
        name = operation_request.resource_name or ""
        namespace = operation_request.parameters.get("namespace", "default")

        # Delete InferenceService
        result = await self.openshift_client.delete_inference_service(
            name=name,
            namespace=namespace,
        )

        return ExecutionResult(
            execution_id=uuid.uuid4(),
            operation_id=operation_request.operation_id,
            status="success",
            resource_type=ResourceType.MODEL_DEPLOYMENT,
            resource_name=name,
            result_data=result,
            error_message=None,
            retry_count=0,
        )

    def _translate_api_error(self, error: ApiException) -> str:
        """Translate Kubernetes API errors to user-friendly messages.

        Args:
            error: ApiException from Kubernetes client

        Returns:
            User-friendly error message
        """
        status_code = error.status

        if status_code == 404:
            return "The requested resource was not found in OpenShift AI"
        elif status_code == 403:
            return f"You don't have permission to perform this operation: {error.reason}"
        elif status_code == 409:
            return "A resource with this name already exists"
        elif status_code == 500:
            return f"OpenShift AI encountered an Internal Error: {error.reason}"
        elif status_code == 503:
            return "OpenShift AI is temporarily unavailable"
        else:
            return f"OpenShift AI error: {error.reason}"
