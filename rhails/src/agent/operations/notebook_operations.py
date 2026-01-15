"""Notebook operation executors for OpenShift AI Jupyter notebooks.

This module implements the operation executors for notebook management operations
including creation, listing, start/stop control, and deletion.
"""

import time
import uuid

from kubernetes.client.rest import ApiException
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.intent import ExecutionResult, OperationRequest
from src.services.audit_logger import AuditLogger
from src.services.openshift_client import OpenShiftClient


class NotebookOperationExecutor:
    """Execute notebook operations against OpenShift AI."""

    def __init__(
        self,
        openshift_client: OpenShiftClient,
        db_session: AsyncSession,
        audit_logger: AuditLogger | None = None,
    ):
        """Initialize notebook operation executor.

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
                result = await self.execute_create_notebook(operation_request)
            elif operation_request.operation_type == "list":
                result = await self.execute_list_notebooks(operation_request)
            elif operation_request.operation_type == "patch":
                result = await self.execute_notebook_control(operation_request)
            elif operation_request.operation_type == "delete":
                result = await self.execute_delete_notebook(operation_request)
            else:
                raise ValueError(f"Unknown operation type: {operation_request.operation_type}")

            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)

            # Log to audit if logger available
            if self.audit_logger:
                await self.audit_logger.log_operation(
                    user_id=operation_request.user_id,
                    session_id=operation_request.session_id,
                    user_command=f"{operation_request.operation_type} {operation_request.resource_name or 'notebooks'}",
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
                    user_command=f"{operation_request.operation_type} {operation_request.resource_name or 'notebooks'}",
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
                    user_command=f"{operation_request.operation_type} {operation_request.resource_name or 'notebooks'}",
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
        # Notebook creation validation
        if operation_request.operation_type == "create":
            if not operation_request.resource_name:
                raise ValueError("notebook_name is required for notebook creation operations")

            # Validate namespace is provided
            namespace = operation_request.parameters.get("namespace")
            if not namespace:
                raise ValueError("namespace is required for notebook creation")

        # Notebook control (start/stop) validation
        if operation_request.operation_type == "patch":
            if not operation_request.resource_name:
                raise ValueError("notebook_name is required for notebook control operations")

            action = operation_request.parameters.get("action")
            if not action or action not in ["start", "stop"]:
                raise ValueError("action must be 'start' or 'stop' for notebook control operations")

            namespace = operation_request.parameters.get("namespace")
            if not namespace:
                raise ValueError("namespace is required for notebook control operations")

        # Notebook deletion validation
        if operation_request.operation_type == "delete":
            if not operation_request.resource_name:
                raise ValueError("notebook_name is required for notebook deletion operations")

            namespace = operation_request.parameters.get("namespace")
            if not namespace:
                raise ValueError("namespace is required for notebook deletion")

        # Notebook list validation
        if operation_request.operation_type == "list":
            # Namespace is optional for list operations (defaults to all namespaces)
            pass

    async def execute_create_notebook(self, operation_request: OperationRequest) -> ExecutionResult:
        """Execute notebook creation operation.

        Args:
            operation_request: Create notebook operation request

        Returns:
            ExecutionResult with created notebook details
        """
        notebook_name = str(operation_request.resource_name or "")
        namespace = str(operation_request.parameters.get("namespace", ""))

        # Extract notebook configuration parameters
        image = str(operation_request.parameters.get("image", "jupyter/scipy-notebook:latest"))
        memory = str(operation_request.parameters.get("memory", "2Gi"))
        cpu = str(operation_request.parameters.get("cpu", "1"))

        # Note: GPU support would require additional configuration
        # in the Notebook spec and is not currently supported by the
        # create_notebook method

        # Create notebook using OpenShift client
        notebook_result = await self.openshift_client.create_notebook(
            name=notebook_name,
            namespace=namespace,
            image=image,
            memory=memory,
            cpu=cpu,
        )

        return ExecutionResult(
            execution_id=uuid.uuid4(),
            operation_id=operation_request.operation_id,
            status="success",
            resource_type=operation_request.target_resource,
            resource_name=notebook_name,
            result_data=notebook_result,
            error_message=None,
            retry_count=0,
        )

    async def execute_list_notebooks(self, operation_request: OperationRequest) -> ExecutionResult:
        """Execute notebook list operation.

        Args:
            operation_request: List notebooks operation request

        Returns:
            ExecutionResult with list of notebooks
        """
        namespace = str(operation_request.parameters.get("namespace", ""))

        # List notebooks using OpenShift client
        notebooks = await self.openshift_client.list_notebooks(
            namespace=namespace,
        )

        return ExecutionResult(
            execution_id=uuid.uuid4(),
            operation_id=operation_request.operation_id,
            status="success",
            resource_type=operation_request.target_resource,
            resource_name="",
            result_data=notebooks,
            error_message=None,
            retry_count=0,
        )

    async def execute_notebook_control(self, operation_request: OperationRequest) -> ExecutionResult:
        """Execute notebook control (start/stop) operation.

        Args:
            operation_request: Notebook control operation request

        Returns:
            ExecutionResult with operation outcome
        """
        notebook_name = str(operation_request.resource_name or "")
        namespace = str(operation_request.parameters.get("namespace", ""))
        action = operation_request.parameters.get("action")

        # Execute control action using OpenShift client
        if action == "stop":
            notebook_result = await self.openshift_client.patch_notebook(
                name=notebook_name,
                namespace=namespace,
                spec_patch={"metadata": {"annotations": {"kubeflow-resource-stopped": "true"}}},
            )
        else:  # action == "start"
            notebook_result = await self.openshift_client.start_notebook(
                name=notebook_name,
                namespace=namespace,
            )

        return ExecutionResult(
            execution_id=uuid.uuid4(),
            operation_id=operation_request.operation_id,
            status="success",
            resource_type=operation_request.target_resource,
            resource_name=notebook_name,
            result_data=notebook_result,
            error_message=None,
            retry_count=0,
        )

    async def execute_delete_notebook(self, operation_request: OperationRequest) -> ExecutionResult:
        """Execute notebook deletion operation.

        Args:
            operation_request: Delete notebook operation request

        Returns:
            ExecutionResult with deletion confirmation
        """
        notebook_name = str(operation_request.resource_name or "")
        namespace = str(operation_request.parameters.get("namespace", ""))

        # Delete notebook using OpenShift client
        notebook_result = await self.openshift_client.delete_notebook(
            name=notebook_name,
            namespace=namespace,
        )

        return ExecutionResult(
            execution_id=uuid.uuid4(),
            operation_id=operation_request.operation_id,
            status="success",
            resource_type=operation_request.target_resource,
            resource_name=notebook_name,
            result_data=notebook_result,
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
            404: "Notebook not found. Please check the notebook name and namespace.",
            403: "Permission denied. You don't have access to this notebook or namespace.",
            409: "Notebook already exists. Please use a different name or delete the existing notebook.",
            400: "Invalid notebook configuration. Please check your notebook parameters.",
            500: "OpenShift server error. Please try again later.",
        }

        status = error.status
        return error_mappings.get(status, f"OpenShift API error (HTTP {status}): {error.reason}")
