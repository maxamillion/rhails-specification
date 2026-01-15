"""Integration tests for pipeline management operations.

These tests verify end-to-end pipeline operations including:
- Pipeline creation
- Pipeline status queries
- Pipeline listing
- Pipeline schedule updates
- Pipeline run history retrieval

Integration tests use real database connections and mock OpenShift API calls.
"""

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from kubernetes.client.rest import ApiException
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.intent import OperationRequest
from src.models.openshift import ResourceType
from src.services.database import DatabaseManager


@pytest.fixture
async def db_session(test_database_url: str) -> AsyncSession:
    """Provide a database session for integration tests."""
    from datetime import datetime

    db_manager = DatabaseManager(test_database_url)
    await db_manager.initialize_async()
    await db_manager.create_tables()

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

    # Mock Pipeline creation
    client.create_pipeline = AsyncMock(
        return_value={
            "apiVersion": "tekton.dev/v1beta1",
            "kind": "Pipeline",
            "metadata": {
                "name": "customer-reviews-preprocessing",
                "namespace": "test-namespace",
                "creationTimestamp": "2026-01-15T10:00:00Z",
            },
            "spec": {
                "params": [
                    {"name": "source", "default": "s3://data/customer-reviews"},
                ],
                "tasks": [
                    {
                        "name": "preprocess",
                        "taskRef": {"name": "preprocess-task"},
                    }
                ],
            },
            "status": {
                "conditions": [
                    {
                        "type": "Ready",
                        "status": "True",
                        "lastTransitionTime": "2026-01-15T10:01:00Z",
                    }
                ]
            },
        }
    )

    # Mock Pipeline get
    client.get_pipeline = AsyncMock(
        return_value={
            "metadata": {"name": "customer-reviews-preprocessing", "namespace": "test-namespace"},
            "status": {
                "conditions": [{"type": "Ready", "status": "True"}],
            },
        }
    )

    # Mock Pipeline list
    client.list_pipelines = AsyncMock(
        return_value=[
            {
                "metadata": {"name": "customer-reviews-preprocessing", "namespace": "test-namespace"},
                "status": {"conditions": [{"type": "Ready", "status": "True"}]},
            },
            {
                "metadata": {"name": "fraud-detection-pipeline", "namespace": "test-namespace"},
                "status": {"conditions": [{"type": "Ready", "status": "False"}]},
            },
        ]
    )

    # Mock Pipeline patch (for schedule updates)
    client.patch_pipeline = AsyncMock(
        return_value={
            "metadata": {"name": "customer-reviews-preprocessing", "namespace": "test-namespace"},
            "spec": {
                "schedule": "0 */6 * * *",  # Every 6 hours
            },
        }
    )

    # Mock Pipeline runs list
    client.list_pipeline_runs = AsyncMock(
        return_value=[
            {
                "metadata": {
                    "name": "customer-reviews-preprocessing-run-1",
                    "namespace": "test-namespace",
                },
                "status": {
                    "conditions": [{"type": "Succeeded", "status": "True"}],
                    "startTime": "2026-01-15T10:00:00Z",
                    "completionTime": "2026-01-15T10:15:00Z",
                },
            }
        ]
    )

    return client


@pytest.mark.integration
@pytest.mark.asyncio
class TestPipelineCreationOperation:
    """Integration tests for pipeline creation operations."""

    async def test_create_pipeline_success(
        self,
        db_session: AsyncSession,
        mock_openshift_client: MagicMock,
    ) -> None:
        """Test that creating a pipeline creates a Pipeline resource in OpenShift."""
        # Import here to avoid circular dependencies
        from src.agent.operations.pipeline_operations import PipelineOperationExecutor

        executor = PipelineOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=db_session,
        )

        # Create operation request using pre-created session
        operation_request = OperationRequest(
            operation_id=uuid.uuid4(),
            session_id=db_session.test_session_id,
            user_id="test-user",
            operation_type="create",
            target_resource=ResourceType.PIPELINE,
            resource_name="customer-reviews-preprocessing",
            parameters={
                "namespace": "test-namespace",
                "source": "s3://data/customer-reviews",
                "pipeline_yaml": "# Tekton pipeline definition",
            },
            requires_confirmation=False,
            confirmation_token=None,
        )

        # Execute pipeline creation
        result = await executor.execute(operation_request)

        # Verify OpenShift client was called correctly
        mock_openshift_client.create_pipeline.assert_called_once()

        # Verify execution result
        assert result.status == "success"
        assert result.resource_name == "customer-reviews-preprocessing"
        assert "customer-reviews-preprocessing" in result.result_data["metadata"]["name"]


@pytest.mark.integration
@pytest.mark.asyncio
class TestPipelineStatusOperation:
    """Integration tests for pipeline status query operations."""

    async def test_get_pipeline_status_returns_current_state(
        self,
        db_session: AsyncSession,
        mock_openshift_client: MagicMock,
    ) -> None:
        """Test that getting pipeline status returns current Pipeline state."""
        from src.agent.operations.pipeline_operations import PipelineOperationExecutor

        executor = PipelineOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=db_session,
        )

        operation_request = OperationRequest(
            operation_id=uuid.uuid4(),
            session_id=db_session.test_session_id,
            user_id="test-user",
            operation_type="get",
            target_resource=ResourceType.PIPELINE,
            resource_name="customer-reviews-preprocessing",
            parameters={"namespace": "test-namespace"},
            requires_confirmation=False,
        )

        # Execute status query
        result = await executor.execute(operation_request)

        # Verify OpenShift client was called
        mock_openshift_client.get_pipeline.assert_called_once_with(
            name="customer-reviews-preprocessing",
            namespace="test-namespace",
        )

        # Verify result
        assert result.status == "success"
        assert "Ready" in str(result.result_data)


@pytest.mark.integration
@pytest.mark.asyncio
class TestListPipelinesOperation:
    """Integration tests for listing pipelines operation."""

    async def test_list_pipelines_returns_all_pipelines(
        self,
        db_session: AsyncSession,
        mock_openshift_client: MagicMock,
    ) -> None:
        """Test that listing pipelines returns all Pipelines in namespace."""
        from src.agent.operations.pipeline_operations import PipelineOperationExecutor

        executor = PipelineOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=db_session,
        )

        operation_request = OperationRequest(
            operation_id=uuid.uuid4(),
            session_id=db_session.test_session_id,
            user_id="test-user",
            operation_type="list",
            target_resource=ResourceType.PIPELINE,
            parameters={"namespace": "test-namespace"},
            requires_confirmation=False,
        )

        # Execute list operation
        result = await executor.execute(operation_request)

        # Verify OpenShift client was called
        mock_openshift_client.list_pipelines.assert_called_once_with(
            namespace="test-namespace"
        )

        # Verify result
        assert result.status == "success"
        assert len(result.result_data) == 2
        assert any(p["metadata"]["name"] == "customer-reviews-preprocessing" for p in result.result_data)
        assert any(p["metadata"]["name"] == "fraud-detection-pipeline" for p in result.result_data)


@pytest.mark.integration
@pytest.mark.asyncio
class TestUpdatePipelineScheduleOperation:
    """Integration tests for pipeline schedule update operation."""

    async def test_update_pipeline_schedule_success(
        self,
        db_session: AsyncSession,
        mock_openshift_client: MagicMock,
    ) -> None:
        """Test that updating pipeline schedule updates the Pipeline resource."""
        from src.agent.operations.pipeline_operations import PipelineOperationExecutor

        executor = PipelineOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=db_session,
        )

        operation_request = OperationRequest(
            operation_id=uuid.uuid4(),
            session_id=db_session.test_session_id,
            user_id="test-user",
            operation_type="patch",
            target_resource=ResourceType.PIPELINE,
            resource_name="customer-reviews-preprocessing",
            parameters={
                "namespace": "test-namespace",
                "schedule": "0 */6 * * *",  # Every 6 hours
            },
            requires_confirmation=False,
        )

        # Execute schedule update
        result = await executor.execute(operation_request)

        # Verify OpenShift client was called
        mock_openshift_client.patch_pipeline.assert_called_once()

        # Verify result
        assert result.status == "success"


@pytest.mark.integration
@pytest.mark.asyncio
class TestGetPipelineRunsOperation:
    """Integration tests for pipeline run history retrieval."""

    async def test_get_pipeline_runs_returns_history(
        self,
        db_session: AsyncSession,
        mock_openshift_client: MagicMock,
    ) -> None:
        """Test that getting pipeline runs returns execution history."""
        from src.agent.operations.pipeline_operations import PipelineOperationExecutor

        executor = PipelineOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=db_session,
        )

        operation_request = OperationRequest(
            operation_id=uuid.uuid4(),
            session_id=db_session.test_session_id,
            user_id="test-user",
            operation_type="list",
            target_resource="pipeline_runs",  # Special resource type for run history
            resource_name="customer-reviews-preprocessing",
            parameters={"namespace": "test-namespace"},
            requires_confirmation=False,
        )

        # Execute pipeline runs query
        result = await executor.execute(operation_request)

        # Verify OpenShift client was called
        mock_openshift_client.list_pipeline_runs.assert_called_once()

        # Verify result
        assert result.status == "success"
        assert len(result.result_data) >= 1
        run = result.result_data[0]
        assert "customer-reviews-preprocessing-run" in run["metadata"]["name"]
        assert "Succeeded" in str(run["status"])
