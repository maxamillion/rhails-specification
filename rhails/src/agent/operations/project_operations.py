"""Project operation executors for OpenShift AI project management.

This module implements the operation executors for project management operations
including creation, listing, user management, and resource querying.
"""

import time
import uuid

from kubernetes.client.rest import ApiException
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.intent import ExecutionResult, OperationRequest
from src.services.audit_logger import AuditLogger
from src.services.openshift_client import OpenShiftClient


class ProjectOperationExecutor:
    """Execute project operations against OpenShift."""

    def __init__(
        self,
        openshift_client: OpenShiftClient,
        db_session: AsyncSession,
        audit_logger: AuditLogger | None = None,
    ):
        """Initialize project operation executor.

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
                result = await self.execute_create_project(operation_request)
            elif operation_request.operation_type == "list":
                result = await self.execute_list_projects(operation_request)
            elif operation_request.operation_type == "get":
                result = await self.execute_get_project_resources(operation_request)
            elif operation_request.operation_type == "update":
                result = await self.execute_add_user_to_project(operation_request)
            else:
                raise ValueError(f"Unknown operation type: {operation_request.operation_type}")

            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)

            # Log to audit if logger available
            if self.audit_logger:
                await self.audit_logger.log_operation(
                    user_id=operation_request.user_id,
                    session_id=operation_request.session_id,
                    user_command=f"{operation_request.operation_type} {operation_request.resource_name or 'projects'}",
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
                    user_command=f"{operation_request.operation_type} {operation_request.resource_name or 'projects'}",
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
                    user_command=f"{operation_request.operation_type} {operation_request.resource_name or 'projects'}",
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
        # Project creation validation
        if operation_request.operation_type == "create":
            if not operation_request.resource_name:
                raise ValueError("project_name is required for project creation operations")

        # Add user to project validation
        if operation_request.operation_type == "update":
            username = operation_request.parameters.get("username")
            if not username:
                raise ValueError("username is required for add user to project operations")

            if not operation_request.resource_name:
                raise ValueError("project_name is required for add user to project operations")

        # Get project resources validation
        if operation_request.operation_type == "get":
            if not operation_request.resource_name:
                raise ValueError("project_name is required for get project resources operations")

        # List projects validation (no specific requirements)
        if operation_request.operation_type == "list":
            pass

    async def execute_create_project(self, operation_request: OperationRequest) -> ExecutionResult:
        """Execute project creation operation.

        Args:
            operation_request: Create project operation request

        Returns:
            ExecutionResult with created project details
        """
        project_name = str(operation_request.resource_name or "")

        # Extract optional display name and description
        display_name = str(operation_request.parameters.get("display_name", project_name))
        description = str(operation_request.parameters.get("description", ""))

        # Create project using OpenShift client
        project_result = await self.openshift_client.create_project(
            name=project_name,
            display_name=display_name,
            description=description,
        )

        # If resource quotas specified, create resource quota
        operation_request.parameters.get("memory_limit")
        operation_request.parameters.get("cpu_limit")

        # Note: Resource quota creation would happen here if needed
        # For now, we just return the project creation result

        return ExecutionResult(
            execution_id=uuid.uuid4(),
            operation_id=operation_request.operation_id,
            status="success",
            resource_type=operation_request.target_resource,
            resource_name=project_name,
            result_data=project_result,
            error_message=None,
            retry_count=0,
        )

    async def execute_list_projects(self, operation_request: OperationRequest) -> ExecutionResult:
        """Execute project list operation.

        Args:
            operation_request: List projects operation request

        Returns:
            ExecutionResult with list of projects
        """
        # List projects using OpenShift client
        projects = await self.openshift_client.list_projects()

        return ExecutionResult(
            execution_id=uuid.uuid4(),
            operation_id=operation_request.operation_id,
            status="success",
            resource_type=operation_request.target_resource,
            resource_name="",
            result_data=projects,
            error_message=None,
            retry_count=0,
        )

    async def execute_get_project_resources(self, operation_request: OperationRequest) -> ExecutionResult:
        """Execute get project resources operation.

        Args:
            operation_request: Get project resources operation request

        Returns:
            ExecutionResult with project resource usage
        """
        project_name = str(operation_request.resource_name or "")

        # Get resource quota for project (namespace)
        resource_quota = await self.openshift_client.get_resource_quota(
            namespace=project_name
        )

        return ExecutionResult(
            execution_id=uuid.uuid4(),
            operation_id=operation_request.operation_id,
            status="success",
            resource_type=operation_request.target_resource,
            resource_name=project_name,
            result_data=resource_quota or {},
            error_message=None,
            retry_count=0,
        )

    async def execute_add_user_to_project(self, operation_request: OperationRequest) -> ExecutionResult:
        """Execute add user to project operation.

        Args:
            operation_request: Add user to project operation request

        Returns:
            ExecutionResult with operation outcome
        """
        project_name = str(operation_request.resource_name or "")
        username = str(operation_request.parameters.get("username", ""))
        role = str(operation_request.parameters.get("role", "edit"))  # Default to edit role

        # Add user to project using OpenShift client
        role_binding_result = await self.openshift_client.add_user_to_project(
            username=username,
            namespace=project_name,
            role=role,
        )

        return ExecutionResult(
            execution_id=uuid.uuid4(),
            operation_id=operation_request.operation_id,
            status="success",
            resource_type=operation_request.target_resource,
            resource_name=project_name,
            result_data=role_binding_result,
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
            404: "Project not found. Please check the project name.",
            403: "Permission denied. You don't have access to this project or operation.",
            409: "Project already exists. Please use a different name or delete the existing project.",
            400: "Invalid project configuration. Please check your project parameters.",
            500: "OpenShift server error. Please try again later.",
        }

        status = error.status
        return error_mappings.get(status, f"OpenShift API error (HTTP {status}): {error.reason}")
