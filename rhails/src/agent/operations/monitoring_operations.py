"""Monitoring operation executors for model troubleshooting and analysis.

This module implements operation executors for monitoring operations
including log analysis, metrics comparison, performance diagnosis, and prediction distribution.
"""

import time
import uuid

from kubernetes.client.rest import ApiException
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.intent import ExecutionResult, OperationRequest
from src.services.audit_logger import AuditLogger
from src.services.openshift_client import OpenShiftClient


class MonitoringOperationExecutor:
    """Execute monitoring and troubleshooting operations against OpenShift."""

    def __init__(
        self,
        openshift_client: OpenShiftClient,
        db_session: AsyncSession,
        audit_logger: AuditLogger | None = None,
    ):
        """Initialize monitoring operation executor.

        Args:
            openshift_client: OpenShift API client for resource operations
            db_session: Database session for data persistence
            audit_logger: Optional audit logger for compliance logging
        """
        self.openshift_client = openshift_client
        self.db_session = db_session
        self.audit_logger = audit_logger or AuditLogger(db_session)

    async def execute(self, operation_request: OperationRequest) -> ExecutionResult:
        """Execute monitoring operation based on request type.

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

            # Extract model name from parameters
            model_name = operation_request.parameters.get("model_name", operation_request.resource_name)

            # Execute based on operation type
            # All monitoring operations use "get" operation type
            if operation_request.operation_type == "get":
                # Use 'action' parameter to determine which specific monitoring operation
                action = operation_request.parameters.get("action", "analyze_logs")

                if action == "analyze_logs":
                    result = await self.execute_analyze_logs(operation_request, model_name)
                elif action == "compare_metrics":
                    result = await self.execute_compare_metrics(operation_request, model_name)
                elif action == "diagnose_performance":
                    result = await self.execute_diagnose_performance(operation_request, model_name)
                elif action == "get_prediction_distribution":
                    result = await self.execute_get_prediction_distribution(operation_request, model_name)
                else:
                    raise ValueError(f"Unknown monitoring action: {action}")
            else:
                raise ValueError(f"Unknown operation type for monitoring: {operation_request.operation_type}")

            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)

            # Log to audit if logger available
            if self.audit_logger:
                await self.audit_logger.log_operation(
                    user_id=operation_request.user_id,
                    session_id=operation_request.session_id,
                    user_command=f"monitor {model_name}",
                    parsed_intent={
                        "operation_type": operation_request.operation_type,
                        "resource": operation_request.target_resource,
                    },
                    openshift_operation=f"monitor_{operation_request.target_resource}",
                    operation_result={"status": result.status},
                    duration_ms=duration_ms,
                    operation_error=result.error_message,
                )

            return result

        except ApiException as e:
            duration_ms = int((time.time() - start_time) * 1000)
            error_message = self._translate_api_error(e)

            # Log error to audit
            if self.audit_logger:
                await self.audit_logger.log_operation(
                    user_id=operation_request.user_id,
                    session_id=operation_request.session_id,
                    user_command=f"monitor {operation_request.resource_name}",
                    parsed_intent={
                        "operation_type": operation_request.operation_type,
                        "resource": operation_request.target_resource,
                    },
                    openshift_operation=f"monitor_{operation_request.target_resource}",
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
                    user_command=f"monitor {operation_request.resource_name}",
                    parsed_intent={
                        "operation_type": operation_request.operation_type,
                        "resource": operation_request.target_resource,
                    },
                    openshift_operation=f"monitor_{operation_request.target_resource}",
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
        # Model name is required for all monitoring operations
        model_name = operation_request.parameters.get("model_name", operation_request.resource_name)
        if not model_name:
            raise ValueError("model_name is required for monitoring operations")

    async def execute_analyze_logs(self, operation_request: OperationRequest, model_name: str) -> ExecutionResult:
        """Execute log analysis operation.

        Args:
            operation_request: Log analysis operation request
            model_name: Name of the model to analyze

        Returns:
            ExecutionResult with log analysis results
        """
        # Get logs from OpenShift client
        logs_result = await self.openshift_client.get_model_logs(
            model_name=model_name,
            namespace=operation_request.parameters.get("namespace", "default"),
        )

        return ExecutionResult(
            execution_id=uuid.uuid4(),
            operation_id=operation_request.operation_id,
            status="success",
            resource_type=operation_request.target_resource,
            resource_name=model_name,
            result_data=logs_result,
            error_message=None,
            retry_count=0,
        )

    async def execute_compare_metrics(self, operation_request: OperationRequest, model_name: str) -> ExecutionResult:
        """Execute metrics comparison operation.

        Args:
            operation_request: Metrics comparison operation request
            model_name: Name of the model to analyze

        Returns:
            ExecutionResult with metrics comparison results
        """
        time_range = operation_request.parameters.get("time_range", "last week")

        # Get metrics from OpenShift client
        metrics_result = await self.openshift_client.get_model_metrics(
            model_name=model_name,
            namespace=operation_request.parameters.get("namespace", "default"),
            time_range=time_range,
        )

        return ExecutionResult(
            execution_id=uuid.uuid4(),
            operation_id=operation_request.operation_id,
            status="success",
            resource_type=operation_request.target_resource,
            resource_name=model_name,
            result_data=metrics_result,
            error_message=None,
            retry_count=0,
        )

    async def execute_diagnose_performance(self, operation_request: OperationRequest, model_name: str) -> ExecutionResult:
        """Execute performance diagnosis operation.

        Args:
            operation_request: Performance diagnosis operation request
            model_name: Name of the model to diagnose

        Returns:
            ExecutionResult with performance diagnosis results
        """
        # Get resource metrics from OpenShift client
        resource_metrics = await self.openshift_client.get_resource_metrics(
            model_name=model_name,
            namespace=operation_request.parameters.get("namespace", "default"),
        )

        return ExecutionResult(
            execution_id=uuid.uuid4(),
            operation_id=operation_request.operation_id,
            status="success",
            resource_type=operation_request.target_resource,
            resource_name=model_name,
            result_data=resource_metrics,
            error_message=None,
            retry_count=0,
        )

    async def execute_get_prediction_distribution(
        self, operation_request: OperationRequest, model_name: str
    ) -> ExecutionResult:
        """Execute prediction distribution analysis.

        Args:
            operation_request: Prediction distribution operation request
            model_name: Name of the model to analyze

        Returns:
            ExecutionResult with prediction distribution results
        """
        time_range = operation_request.parameters.get("time_range", "last month")

        # Get prediction statistics from OpenShift client
        prediction_stats = await self.openshift_client.get_prediction_statistics(
            model_name=model_name,
            namespace=operation_request.parameters.get("namespace", "default"),
            time_range=time_range,
        )

        return ExecutionResult(
            execution_id=uuid.uuid4(),
            operation_id=operation_request.operation_id,
            status="success",
            resource_type=operation_request.target_resource,
            resource_name=model_name,
            result_data=prediction_stats,
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
            404: "Model not found. Please check the model name.",
            403: "Permission denied. You don't have access to this model or metrics.",
            500: "OpenShift server error. Please try again later.",
        }

        status = error.status
        return error_mappings.get(status, f"OpenShift API error (HTTP {status}): {error.reason}")
