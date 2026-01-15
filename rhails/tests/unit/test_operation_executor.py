"""Unit tests for operation executor.

These tests verify that the operation executor correctly orchestrates
model operations including validation, execution, and result handling.
"""

import uuid
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.intent import ActionType, ExecutionResult, OperationRequest
from src.models.openshift import ResourceType


@pytest.fixture
def mock_openshift_client() -> MagicMock:
    """Provide a mocked OpenShift client."""
    client = MagicMock()
    client.create_inference_service = AsyncMock(
        return_value={"metadata": {"name": "test-model"}}
    )
    client.get_inference_service = AsyncMock(
        return_value={"status": {"conditions": [{"type": "Ready", "status": "True"}]}}
    )
    client.list_inference_services = AsyncMock(return_value=[])
    client.patch_inference_service = AsyncMock(
        return_value={"spec": {"predictor": {"minReplicas": 5}}}
    )
    client.delete_inference_service = AsyncMock(
        return_value={"status": "Success"}
    )
    return client


@pytest.fixture
def mock_db_session() -> MagicMock:
    """Provide a mocked database session."""
    session = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.execute = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def mock_audit_logger() -> MagicMock:
    """Provide a mocked audit logger."""
    logger = MagicMock()
    logger.log_operation = AsyncMock(return_value=uuid.uuid4())
    return logger


@pytest.mark.unit
class TestOperationExecutorValidation:
    """Unit tests for operation request validation."""

    async def test_validates_required_parameters(
        self,
        mock_openshift_client: MagicMock,
        mock_db_session: MagicMock,
    ) -> None:
        """Test that executor validates required parameters before execution."""
        from src.agent.operations.model_operations import ModelOperationExecutor

        executor = ModelOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=mock_db_session,
        )

        # Missing required parameter (model_name)
        operation_request = OperationRequest(
            operation_id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            user_id="test-user",
            operation_type="create",
            target_resource=ResourceType.INFERENCE_SERVICE,
            parameters={},  # Missing model_name
            requires_confirmation=False,
        )

        # Should raise validation error
        with pytest.raises(ValueError, match="model_name"):
            await executor.validate_request(operation_request)

    async def test_validates_parameter_types(
        self,
        mock_openshift_client: MagicMock,
        mock_db_session: MagicMock,
    ) -> None:
        """Test that executor validates parameter data types."""
        from src.agent.operations.model_operations import ModelOperationExecutor

        executor = ModelOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=mock_db_session,
        )

        # Invalid parameter type (replicas should be int)
        operation_request = OperationRequest(
            operation_id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            user_id="test-user",
            operation_type="create",
            target_resource=ResourceType.INFERENCE_SERVICE,
            resource_name="test-model",
            parameters={"replicas": "not-a-number"},  # Should be int
            requires_confirmation=False,
        )

        # Should raise validation error
        with pytest.raises(ValueError, match="replicas"):
            await executor.validate_request(operation_request)

    async def test_validates_replica_count_range(
        self,
        mock_openshift_client: MagicMock,
        mock_db_session: MagicMock,
    ) -> None:
        """Test that executor validates replica count is within acceptable range."""
        from src.agent.operations.model_operations import ModelOperationExecutor

        executor = ModelOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=mock_db_session,
        )

        # Invalid replica count (too high)
        operation_request = OperationRequest(
            operation_id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            user_id="test-user",
            operation_type="create",
            target_resource=ResourceType.INFERENCE_SERVICE,
            resource_name="test-model",
            parameters={"replicas": 1000},  # Unreasonably high
            requires_confirmation=False,
        )

        # Should raise validation error
        with pytest.raises(ValueError, match="replicas"):
            await executor.validate_request(operation_request)


@pytest.mark.unit
class TestOperationExecutorExecution:
    """Unit tests for operation execution logic."""

    async def test_executes_deployment_operation(
        self,
        mock_openshift_client: MagicMock,
        mock_db_session: MagicMock,
    ) -> None:
        """Test that executor correctly executes deployment operations."""
        from src.agent.operations.model_operations import ModelOperationExecutor

        executor = ModelOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=mock_db_session,
        )

        operation_request = OperationRequest(
            operation_id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            user_id="test-user",
            operation_type="create",
            target_resource=ResourceType.INFERENCE_SERVICE,
            resource_name="test-model",
            parameters={"namespace": "test-ns", "replicas": 2},
            requires_confirmation=False,
        )

        # Execute operation
        result = await executor.execute(operation_request)

        # Verify client was called
        mock_openshift_client.create_inference_service.assert_called_once()

        # Verify result
        assert isinstance(result, ExecutionResult)
        assert result.status == "success"
        assert result.resource_name == "test-model"

    async def test_executes_query_operation(
        self,
        mock_openshift_client: MagicMock,
        mock_db_session: MagicMock,
    ) -> None:
        """Test that executor correctly executes query operations."""
        from src.agent.operations.model_operations import ModelOperationExecutor

        executor = ModelOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=mock_db_session,
        )

        operation_request = OperationRequest(
            operation_id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            user_id="test-user",
            operation_type="get",
            target_resource=ResourceType.INFERENCE_SERVICE,
            resource_name="test-model",
            parameters={"namespace": "test-ns"},
            requires_confirmation=False,
        )

        # Execute operation
        result = await executor.execute(operation_request)

        # Verify client was called
        mock_openshift_client.get_inference_service.assert_called_once()

        # Verify result
        assert result.status == "success"

    async def test_handles_execution_errors_gracefully(
        self,
        mock_openshift_client: MagicMock,
        mock_db_session: MagicMock,
    ) -> None:
        """Test that executor handles execution errors gracefully."""
        from kubernetes.client.rest import ApiException

        from src.agent.operations.model_operations import ModelOperationExecutor

        # Configure mock to raise error
        mock_openshift_client.create_inference_service = AsyncMock(
            side_effect=ApiException(status=500, reason="Internal Error")
        )

        executor = ModelOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=mock_db_session,
        )

        operation_request = OperationRequest(
            operation_id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            user_id="test-user",
            operation_type="create",
            target_resource=ResourceType.INFERENCE_SERVICE,
            resource_name="test-model",
            parameters={"namespace": "test-ns"},
            requires_confirmation=False,
        )

        # Execute operation
        result = await executor.execute(operation_request)

        # Should return error result, not raise exception
        assert result.status == "error"
        assert result.error_message is not None
        assert "Internal Error" in result.error_message


@pytest.mark.unit
class TestOperationExecutorAuditing:
    """Unit tests for operation auditing."""

    async def test_logs_successful_operations(
        self,
        mock_openshift_client: MagicMock,
        mock_db_session: MagicMock,
        mock_audit_logger: MagicMock,
    ) -> None:
        """Test that successful operations are logged to audit trail."""
        from src.agent.operations.model_operations import ModelOperationExecutor

        executor = ModelOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=mock_db_session,
            audit_logger=mock_audit_logger,
        )

        operation_request = OperationRequest(
            operation_id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            user_id="test-user",
            operation_type="create",
            target_resource=ResourceType.INFERENCE_SERVICE,
            resource_name="test-model",
            parameters={"namespace": "test-ns"},
            requires_confirmation=False,
        )

        # Execute operation
        await executor.execute(operation_request)

        # Verify audit log was created
        mock_audit_logger.log_operation.assert_called_once()
        call_args = mock_audit_logger.log_operation.call_args[1]

        assert call_args["user_id"] == "test-user"
        assert call_args["operation_error"] is None  # No error

    async def test_logs_failed_operations(
        self,
        mock_openshift_client: MagicMock,
        mock_db_session: MagicMock,
        mock_audit_logger: MagicMock,
    ) -> None:
        """Test that failed operations are logged with error details."""
        from kubernetes.client.rest import ApiException

        from src.agent.operations.model_operations import ModelOperationExecutor

        # Configure mock to raise error
        mock_openshift_client.create_inference_service = AsyncMock(
            side_effect=ApiException(status=403, reason="Forbidden")
        )

        executor = ModelOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=mock_db_session,
            audit_logger=mock_audit_logger,
        )

        operation_request = OperationRequest(
            operation_id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            user_id="test-user",
            operation_type="create",
            target_resource=ResourceType.INFERENCE_SERVICE,
            resource_name="test-model",
            parameters={"namespace": "test-ns"},
            requires_confirmation=False,
        )

        # Execute operation
        await executor.execute(operation_request)

        # Verify audit log was created with error
        mock_audit_logger.log_operation.assert_called_once()
        call_args = mock_audit_logger.log_operation.call_args[1]

        assert call_args["operation_error"] is not None
        assert "Forbidden" in call_args["operation_error"]

    async def test_logs_execution_duration(
        self,
        mock_openshift_client: MagicMock,
        mock_db_session: MagicMock,
        mock_audit_logger: MagicMock,
    ) -> None:
        """Test that operation execution duration is logged."""
        from src.agent.operations.model_operations import ModelOperationExecutor

        executor = ModelOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=mock_db_session,
            audit_logger=mock_audit_logger,
        )

        operation_request = OperationRequest(
            operation_id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            user_id="test-user",
            operation_type="get",
            target_resource=ResourceType.INFERENCE_SERVICE,
            resource_name="test-model",
            parameters={"namespace": "test-ns"},
            requires_confirmation=False,
        )

        # Execute operation
        await executor.execute(operation_request)

        # Verify duration was logged
        call_args = mock_audit_logger.log_operation.call_args[1]
        assert "duration_ms" in call_args
        assert call_args["duration_ms"] >= 0  # Should be non-negative


@pytest.mark.unit
class TestOperationExecutorConfirmation:
    """Unit tests for confirmation flow handling."""

    async def test_requires_confirmation_for_destructive_operations(
        self,
        mock_openshift_client: MagicMock,
        mock_db_session: MagicMock,
    ) -> None:
        """Test that destructive operations require confirmation."""
        from src.agent.operations.model_operations import ModelOperationExecutor

        executor = ModelOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=mock_db_session,
        )

        # Delete operation (destructive)
        delete_request = OperationRequest(
            operation_id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            user_id="test-user",
            operation_type="delete",
            target_resource=ResourceType.INFERENCE_SERVICE,
            resource_name="test-model",
            parameters={"namespace": "test-ns"},
            requires_confirmation=True,
            confirmation_token=None,  # No confirmation yet
        )

        # Should not execute without confirmation token
        result = await executor.execute(delete_request)

        # Should return pending confirmation status
        assert result.status == "pending_confirmation"
        assert mock_openshift_client.delete_inference_service.call_count == 0

    async def test_executes_after_confirmation(
        self,
        mock_openshift_client: MagicMock,
        mock_db_session: MagicMock,
    ) -> None:
        """Test that operations execute after confirmation is provided."""
        from src.agent.operations.model_operations import ModelOperationExecutor

        executor = ModelOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=mock_db_session,
        )

        # Delete operation with confirmation token
        delete_request = OperationRequest(
            operation_id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            user_id="test-user",
            operation_type="delete",
            target_resource=ResourceType.INFERENCE_SERVICE,
            resource_name="test-model",
            parameters={"namespace": "test-ns"},
            requires_confirmation=True,
            confirmation_token="valid-token-12345",  # Confirmation provided
        )

        # Should execute with valid confirmation
        result = await executor.execute(delete_request)

        # Should execute successfully
        assert result.status == "success"
        mock_openshift_client.delete_inference_service.assert_called_once()

    async def test_query_operations_do_not_require_confirmation(
        self,
        mock_openshift_client: MagicMock,
        mock_db_session: MagicMock,
    ) -> None:
        """Test that read-only query operations do not require confirmation."""
        from src.agent.operations.model_operations import ModelOperationExecutor

        executor = ModelOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=mock_db_session,
        )

        # Query operation (read-only)
        query_request = OperationRequest(
            operation_id=uuid.uuid4(),
            session_id=uuid.uuid4(),
            user_id="test-user",
            operation_type="get",
            target_resource=ResourceType.INFERENCE_SERVICE,
            resource_name="test-model",
            parameters={"namespace": "test-ns"},
            requires_confirmation=False,
        )

        # Should execute immediately without confirmation
        result = await executor.execute(query_request)

        assert result.status == "success"
        mock_openshift_client.get_inference_service.assert_called_once()
