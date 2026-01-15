"""Pipeline operation executors for OpenShift AI data pipelines.

This module implements the operation executors for pipeline management operations
including creation, status queries, listing, schedule updates, and run history retrieval.
"""

import time
import uuid

from kubernetes.client.rest import ApiException
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.intent import ExecutionResult, OperationRequest
from src.services.audit_logger import AuditLogger
from src.services.openshift_client import OpenShiftClient


class PipelineOperationExecutor:
    """Execute pipeline operations against OpenShift AI."""

    def __init__(
        self,
        openshift_client: OpenShiftClient,
        db_session: AsyncSession,
        audit_logger: AuditLogger | None = None,
    ):
        """Initialize pipeline operation executor.

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

            # Execute based on operation type and target resource
            # Special handling for pipeline runs
            if operation_request.target_resource == "pipeline_runs":
                result = await self.execute_list_pipeline_runs(operation_request)
            elif operation_request.operation_type == "create":
                result = await self.execute_create_pipeline(operation_request)
            elif operation_request.operation_type == "get":
                result = await self.execute_get_pipeline_status(operation_request)
            elif operation_request.operation_type == "list":
                result = await self.execute_list_pipelines(operation_request)
            elif operation_request.operation_type == "patch":
                result = await self.execute_update_pipeline_schedule(operation_request)
            else:
                raise ValueError(f"Unknown operation type: {operation_request.operation_type}")

            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)

            # Log to audit if logger available
            if self.audit_logger:
                await self.audit_logger.log_operation(
                    user_id=operation_request.user_id,
                    session_id=operation_request.session_id,
                    user_command=f"{operation_request.operation_type} {operation_request.resource_name or 'pipelines'}",
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
                    user_command=f"{operation_request.operation_type} {operation_request.resource_name or 'pipelines'}",
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
                    user_command=f"{operation_request.operation_type} {operation_request.resource_name or 'pipelines'}",
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
        # Pipeline creation validation
        if operation_request.operation_type == "create":
            if not operation_request.resource_name:
                raise ValueError("pipeline_name is required for pipeline creation operations")

            # Validate namespace is provided
            namespace = operation_request.parameters.get("namespace")
            if not namespace:
                raise ValueError("namespace is required for pipeline creation")

        # Pipeline status query validation
        if operation_request.operation_type == "get":
            if not operation_request.resource_name:
                raise ValueError("pipeline_name is required for status query operations")

            namespace = operation_request.parameters.get("namespace")
            if not namespace:
                raise ValueError("namespace is required for pipeline status query")

        # Pipeline schedule update validation
        if operation_request.operation_type == "patch":
            if not operation_request.resource_name:
                raise ValueError("pipeline_name is required for schedule update operations")

            schedule = operation_request.parameters.get("schedule")
            if not schedule:
                raise ValueError("schedule is required for pipeline schedule update")

            namespace = operation_request.parameters.get("namespace")
            if not namespace:
                raise ValueError("namespace is required for pipeline schedule update")

        # Pipeline list validation
        if operation_request.operation_type == "list":
            # Namespace is optional for list operations (defaults to all namespaces)
            pass

        # Pipeline runs validation
        if operation_request.target_resource == "pipeline_runs":
            if not operation_request.resource_name:
                raise ValueError("pipeline_name is required for pipeline run history retrieval")

            namespace = operation_request.parameters.get("namespace")
            if not namespace:
                raise ValueError("namespace is required for pipeline run history")

    async def execute_create_pipeline(self, operation_request: OperationRequest) -> ExecutionResult:
        """Execute pipeline creation operation.

        Args:
            operation_request: Create pipeline operation request

        Returns:
            ExecutionResult with created pipeline details
        """
        pipeline_name = operation_request.resource_name
        namespace = operation_request.parameters.get("namespace")
        pipeline_yaml = operation_request.parameters.get("pipeline_yaml", "")
        parameters = operation_request.parameters.get("parameters", {})

        # Create pipeline using OpenShift client
        pipeline_result = await self.openshift_client.create_pipeline(
            name=pipeline_name,
            namespace=namespace,
            pipeline_yaml=pipeline_yaml,
            parameters=parameters,
        )

        return ExecutionResult(
            execution_id=uuid.uuid4(),
            operation_id=operation_request.operation_id,
            status="success",
            resource_type=operation_request.target_resource,
            resource_name=pipeline_name,
            result_data=pipeline_result,
            error_message=None,
            retry_count=0,
        )

    async def execute_get_pipeline_status(self, operation_request: OperationRequest) -> ExecutionResult:
        """Execute pipeline status query operation.

        Args:
            operation_request: Get pipeline status operation request

        Returns:
            ExecutionResult with pipeline status details
        """
        pipeline_name = operation_request.resource_name
        namespace = operation_request.parameters.get("namespace")

        # Get pipeline status using OpenShift client
        pipeline_status = await self.openshift_client.get_pipeline(
            name=pipeline_name,
            namespace=namespace,
        )

        return ExecutionResult(
            execution_id=uuid.uuid4(),
            operation_id=operation_request.operation_id,
            status="success",
            resource_type=operation_request.target_resource,
            resource_name=pipeline_name,
            result_data=pipeline_status,
            error_message=None,
            retry_count=0,
        )

    async def execute_list_pipelines(self, operation_request: OperationRequest) -> ExecutionResult:
        """Execute pipeline list operation.

        Args:
            operation_request: List pipelines operation request

        Returns:
            ExecutionResult with list of pipelines
        """
        namespace = operation_request.parameters.get("namespace")

        # List pipelines using OpenShift client
        pipelines = await self.openshift_client.list_pipelines(
            namespace=namespace,
        )

        return ExecutionResult(
            execution_id=uuid.uuid4(),
            operation_id=operation_request.operation_id,
            status="success",
            resource_type=operation_request.target_resource,
            resource_name="",
            result_data=pipelines,
            error_message=None,
            retry_count=0,
        )

    async def execute_update_pipeline_schedule(self, operation_request: OperationRequest) -> ExecutionResult:
        """Execute pipeline schedule update operation.

        Args:
            operation_request: Update pipeline schedule operation request

        Returns:
            ExecutionResult with updated pipeline details
        """
        pipeline_name = operation_request.resource_name
        namespace = operation_request.parameters.get("namespace")
        schedule = operation_request.parameters.get("schedule")

        # Update pipeline schedule using OpenShift client
        pipeline_result = await self.openshift_client.patch_pipeline(
            name=pipeline_name,
            namespace=namespace,
            spec_patch={"schedule": schedule},
        )

        return ExecutionResult(
            execution_id=uuid.uuid4(),
            operation_id=operation_request.operation_id,
            status="success",
            resource_type=operation_request.target_resource,
            resource_name=pipeline_name,
            result_data=pipeline_result,
            error_message=None,
            retry_count=0,
        )

    async def execute_list_pipeline_runs(self, operation_request: OperationRequest) -> ExecutionResult:
        """Execute pipeline run history retrieval operation.

        Args:
            operation_request: List pipeline runs operation request

        Returns:
            ExecutionResult with pipeline run history
        """
        pipeline_name = operation_request.resource_name
        namespace = operation_request.parameters.get("namespace")

        # List pipeline runs using OpenShift client
        pipeline_runs = await self.openshift_client.list_pipeline_runs(
            pipeline_name=pipeline_name,
            namespace=namespace,
        )

        return ExecutionResult(
            execution_id=uuid.uuid4(),
            operation_id=operation_request.operation_id,
            status="success",
            resource_type=operation_request.target_resource,
            resource_name=pipeline_name,
            result_data=pipeline_runs,
            error_message=None,
            retry_count=0,
        )

    def _translate_api_error(self, error: ApiException) -> str:
        """Translate Kubernetes API errors to user-friendly messages.

        Args:
            error: API exception from Kubernetes client

        Returns:
            User-friendly error message
        """
        # Map common API errors
        error_mappings = {
            404: "Pipeline not found. Please check the pipeline name and namespace.",
            403: "Permission denied. You don't have access to this pipeline or namespace.",
            409: "Pipeline already exists. Please use a different name or update the existing pipeline.",
            400: "Invalid pipeline configuration. Please check your pipeline parameters.",
            500: "OpenShift server error. Please try again later.",
        }

        status = error.status
        return error_mappings.get(status, f"OpenShift API error (HTTP {status}): {error.reason}")
