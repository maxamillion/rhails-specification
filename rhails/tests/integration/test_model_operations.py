"""Integration tests for model management operations.

These tests verify end-to-end model operations including:
- Model deployment (InferenceService creation)
- Model status queries
- Model listing
- Model scaling
- Model deletion

Integration tests use real database connections and mock OpenShift API calls.
"""

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from kubernetes.client.rest import ApiException
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.intent import ActionType, OperationRequest, UserIntent
from src.models.openshift import ResourceType
from src.services.database import DatabaseManager


@pytest.fixture
async def db_session(test_database_url: str) -> AsyncSession:
    """Provide a database session for integration tests."""
    from datetime import datetime

    db_manager = DatabaseManager(test_database_url)
    await db_manager.initialize_async()
    await db_manager.create_tables()  # Create database tables

    async with db_manager.get_async_session() as session:
        # Create a test conversation session for foreign key constraints
        from src.models.conversation import ConversationSessionDB
        test_session_id = uuid.uuid4()
        test_session = ConversationSessionDB(
            session_id=test_session_id,
            user_id="test-user",
            status="active",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(test_session)
        await session.commit()

        # Store the session_id for tests to use
        session.test_session_id = test_session_id

        yield session

    await db_manager.shutdown_async()


@pytest.fixture
def mock_openshift_client() -> MagicMock:
    """Provide a mocked OpenShift client for testing."""
    client = MagicMock()

    # Mock InferenceService creation
    client.create_inference_service = AsyncMock(
        return_value={
            "apiVersion": "serving.kserve.io/v1beta1",
            "kind": "InferenceService",
            "metadata": {
                "name": "sentiment-analysis",
                "namespace": "test-namespace",
                "creationTimestamp": "2026-01-15T10:00:00Z",
            },
            "spec": {
                "predictor": {
                    "model": {
                        "modelFormat": {"name": "sklearn"},
                        "storageUri": "s3://models/sentiment-analysis",
                    },
                    "minReplicas": 2,
                    "maxReplicas": 10,
                }
            },
            "status": {
                "conditions": [
                    {
                        "type": "Ready",
                        "status": "True",
                        "lastTransitionTime": "2026-01-15T10:01:00Z",
                    }
                ],
                "url": "https://sentiment-analysis.test-namespace.svc.cluster.local",
            },
        }
    )

    # Mock InferenceService get
    client.get_inference_service = AsyncMock(
        return_value={
            "metadata": {"name": "sentiment-analysis", "namespace": "test-namespace"},
            "status": {
                "conditions": [{"type": "Ready", "status": "True"}],
                "url": "https://sentiment-analysis.test-namespace.svc.cluster.local",
            },
        }
    )

    # Mock InferenceService list
    client.list_inference_services = AsyncMock(
        return_value=[
            {
                "metadata": {"name": "sentiment-analysis", "namespace": "test-namespace"},
                "status": {"conditions": [{"type": "Ready", "status": "True"}]},
            },
            {
                "metadata": {"name": "fraud-detection", "namespace": "test-namespace"},
                "status": {"conditions": [{"type": "Ready", "status": "False"}]},
            },
        ]
    )

    # Mock InferenceService patch (for scaling)
    client.patch_inference_service = AsyncMock(
        return_value={
            "metadata": {"name": "sentiment-analysis", "namespace": "test-namespace"},
            "spec": {"predictor": {"minReplicas": 5, "maxReplicas": 10}},
        }
    )

    # Mock InferenceService deletion
    client.delete_inference_service = AsyncMock(
        return_value={"status": "Success", "details": {"name": "sentiment-analysis"}}
    )

    return client


@pytest.mark.integration
@pytest.mark.asyncio
class TestModelDeploymentOperation:
    """Integration tests for model deployment operations."""

    async def test_deploy_model_creates_inference_service(
        self,
        db_session: AsyncSession,
        mock_openshift_client: MagicMock,
    ) -> None:
        """Test that deploying a model creates an InferenceService in OpenShift."""
        # Import here to avoid circular dependencies
        from src.agent.operations.model_operations import ModelOperationExecutor

        executor = ModelOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=db_session,
        )

        # Create operation request using pre-created session
        operation_request = OperationRequest(
            operation_id=uuid.uuid4(),
            session_id=db_session.test_session_id,
            user_id="test-user",
            operation_type="create",
            target_resource=ResourceType.INFERENCE_SERVICE,
            resource_name="sentiment-analysis",
            parameters={
                "namespace": "test-namespace",
                "replicas": 2,
                "storage_uri": "s3://models/sentiment-analysis",
                "model_format": "sklearn",
            },
            requires_confirmation=False,
            confirmation_token=None,
        )

        # Execute deployment
        result = await executor.execute(operation_request)

        # Verify OpenShift client was called correctly
        mock_openshift_client.create_inference_service.assert_called_once_with(
            name="sentiment-analysis",
            namespace="test-namespace",
            predictor_config={
                "modelFormat": {"name": "sklearn"},
                "storageUri": "s3://models/sentiment-analysis",
            },
            replicas=2,
        )

        # Verify execution result
        assert result.status == "success"
        assert result.resource_name == "sentiment-analysis"
        assert "sentiment-analysis" in result.result_data["metadata"]["name"]

    async def test_deploy_model_handles_openshift_errors(
        self,
        db_session: AsyncSession,
        mock_openshift_client: MagicMock,
    ) -> None:
        """Test that deployment errors from OpenShift are properly handled."""
        from src.agent.operations.model_operations import ModelOperationExecutor

        # Configure mock to raise ApiException
        http_resp = MagicMock()
        http_resp.status = 409
        http_resp.reason = "Conflict"
        http_resp.data = '{"message": "InferenceService already exists"}'

        mock_openshift_client.create_inference_service = AsyncMock(
            side_effect=ApiException(http_resp=http_resp)
        )

        executor = ModelOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=db_session,
        )

        operation_request = OperationRequest(
            operation_id=uuid.uuid4(),
            session_id=db_session.test_session_id,
            user_id="test-user",
            operation_type="create",
            target_resource=ResourceType.INFERENCE_SERVICE,
            resource_name="sentiment-analysis",
            parameters={"namespace": "test-namespace"},
            requires_confirmation=False,
        )

        # Execute deployment
        result = await executor.execute(operation_request)

        # Verify error handling
        assert result.status == "error"
        assert result.error_message is not None
        assert "already exists" in result.error_message.lower()

    async def test_deploy_model_validates_permissions(
        self,
        db_session: AsyncSession,
        mock_openshift_client: MagicMock,
    ) -> None:
        """Test that deployment checks user permissions before execution."""
        from src.agent.operations.model_operations import ModelOperationExecutor

        # Configure mock to raise permission error
        http_resp = MagicMock()
        http_resp.status = 403
        http_resp.reason = "Forbidden"
        http_resp.data = '{"message": "User test-user does not have permission to create InferenceServices"}'

        mock_openshift_client.create_inference_service = AsyncMock(
            side_effect=ApiException(http_resp=http_resp)
        )

        executor = ModelOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=db_session,
        )

        operation_request = OperationRequest(
            operation_id=uuid.uuid4(),
            session_id=db_session.test_session_id,
            user_id="test-user",
            operation_type="create",
            target_resource=ResourceType.INFERENCE_SERVICE,
            resource_name="sentiment-analysis",
            parameters={"namespace": "test-namespace"},
            requires_confirmation=False,
        )

        # Execute deployment
        result = await executor.execute(operation_request)

        # Verify permission error handling
        assert result.status == "error"
        assert result.error_message is not None
        assert "permission" in result.error_message.lower()


@pytest.mark.integration
@pytest.mark.asyncio
class TestModelStatusOperation:
    """Integration tests for model status query operations."""

    async def test_get_model_status_returns_current_state(
        self,
        db_session: AsyncSession,
        mock_openshift_client: MagicMock,
    ) -> None:
        """Test that getting model status returns current InferenceService state."""
        from src.agent.operations.model_operations import ModelOperationExecutor

        executor = ModelOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=db_session,
        )

        operation_request = OperationRequest(
            operation_id=uuid.uuid4(),
            session_id=db_session.test_session_id,
            user_id="test-user",
            operation_type="get",
            target_resource=ResourceType.INFERENCE_SERVICE,
            resource_name="sentiment-analysis",
            parameters={"namespace": "test-namespace"},
            requires_confirmation=False,
        )

        # Execute status query
        result = await executor.execute(operation_request)

        # Verify OpenShift client was called
        mock_openshift_client.get_inference_service.assert_called_once_with(
            name="sentiment-analysis",
            namespace="test-namespace",
        )

        # Verify result
        assert result.status == "success"
        assert "Ready" in str(result.result_data)

    async def test_get_model_status_handles_not_found(
        self,
        db_session: AsyncSession,
        mock_openshift_client: MagicMock,
    ) -> None:
        """Test that querying non-existent model returns appropriate error."""
        from src.agent.operations.model_operations import ModelOperationExecutor

        # Configure mock to raise not found error
        http_resp = MagicMock()
        http_resp.status = 404
        http_resp.reason = "Not Found"

        mock_openshift_client.get_inference_service = AsyncMock(
            side_effect=ApiException(http_resp=http_resp)
        )

        executor = ModelOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=db_session,
        )

        operation_request = OperationRequest(
            operation_id=uuid.uuid4(),
            session_id=db_session.test_session_id,
            user_id="test-user",
            operation_type="get",
            target_resource=ResourceType.INFERENCE_SERVICE,
            resource_name="non-existent-model",
            parameters={"namespace": "test-namespace"},
            requires_confirmation=False,
        )

        # Execute status query
        result = await executor.execute(operation_request)

        # Verify error handling
        assert result.status == "error"
        assert "not found" in result.error_message.lower()


@pytest.mark.integration
@pytest.mark.asyncio
class TestListModelsOperation:
    """Integration tests for listing models operation."""

    async def test_list_models_returns_all_inference_services(
        self,
        db_session: AsyncSession,
        mock_openshift_client: MagicMock,
    ) -> None:
        """Test that listing models returns all InferenceServices in namespace."""
        from src.agent.operations.model_operations import ModelOperationExecutor

        executor = ModelOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=db_session,
        )

        operation_request = OperationRequest(
            operation_id=uuid.uuid4(),
            session_id=db_session.test_session_id,
            user_id="test-user",
            operation_type="list",
            target_resource=ResourceType.INFERENCE_SERVICE,
            parameters={"namespace": "test-namespace"},
            requires_confirmation=False,
        )

        # Execute list operation
        result = await executor.execute(operation_request)

        # Verify OpenShift client was called
        mock_openshift_client.list_inference_services.assert_called_once_with(
            namespace="test-namespace"
        )

        # Verify result
        assert result.status == "success"
        assert len(result.result_data) == 2
        assert any(m["metadata"]["name"] == "sentiment-analysis" for m in result.result_data)
        assert any(m["metadata"]["name"] == "fraud-detection" for m in result.result_data)


@pytest.mark.integration
@pytest.mark.asyncio
class TestScaleModelOperation:
    """Integration tests for model scaling operation."""

    async def test_scale_model_updates_replicas(
        self,
        db_session: AsyncSession,
        mock_openshift_client: MagicMock,
    ) -> None:
        """Test that scaling model updates replica count in InferenceService."""
        from src.agent.operations.model_operations import ModelOperationExecutor

        executor = ModelOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=db_session,
        )

        operation_request = OperationRequest(
            operation_id=uuid.uuid4(),
            session_id=db_session.test_session_id,
            user_id="test-user",
            operation_type="patch",
            target_resource=ResourceType.INFERENCE_SERVICE,
            resource_name="sentiment-analysis",
            parameters={"namespace": "test-namespace", "replicas": 5},
            requires_confirmation=False,  # Testing execution, not confirmation workflow
        )

        # Execute scaling
        result = await executor.execute(operation_request)

        # Verify OpenShift client was called
        mock_openshift_client.patch_inference_service.assert_called_once()

        # Verify result
        assert result.status == "success"


@pytest.mark.integration
@pytest.mark.asyncio
class TestDeleteModelOperation:
    """Integration tests for model deletion operation."""

    async def test_delete_model_removes_inference_service(
        self,
        db_session: AsyncSession,
        mock_openshift_client: MagicMock,
    ) -> None:
        """Test that deleting model removes InferenceService from OpenShift."""
        from src.agent.operations.model_operations import ModelOperationExecutor

        executor = ModelOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=db_session,
        )

        operation_request = OperationRequest(
            operation_id=uuid.uuid4(),
            session_id=db_session.test_session_id,
            user_id="test-user",
            operation_type="delete",
            target_resource=ResourceType.INFERENCE_SERVICE,
            resource_name="sentiment-analysis",
            parameters={"namespace": "test-namespace"},
            requires_confirmation=False,  # Testing execution, not confirmation workflow
        )

        # Execute deletion
        result = await executor.execute(operation_request)

        # Verify OpenShift client was called
        mock_openshift_client.delete_inference_service.assert_called_once_with(
            name="sentiment-analysis",
            namespace="test-namespace",
        )

        # Verify result
        assert result.status == "success"
        assert result.resource_name == "sentiment-analysis"
