"""Integration tests for notebook management operations.

These tests verify end-to-end notebook operations including:
- Notebook creation
- Notebook listing
- Notebook stop/start
- Notebook deletion

Integration tests use real database connections and mock OpenShift API calls.
"""

import uuid
from datetime import datetime
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

    # Mock Notebook creation
    client.create_notebook = AsyncMock(
        return_value={
            "apiVersion": "kubeflow.org/v1",
            "kind": "Notebook",
            "metadata": {
                "name": "ml-notebook",
                "namespace": "test-namespace",
                "creationTimestamp": "2026-01-15T10:00:00Z",
            },
            "spec": {
                "template": {
                    "spec": {
                        "containers": [{
                            "name": "notebook",
                            "image": "tensorflow/tensorflow:latest-jupyter",
                            "resources": {
                                "requests": {"memory": "4Gi", "cpu": "2"},
                                "limits": {"memory": "4Gi", "cpu": "2"},
                            },
                        }],
                    }
                },
            },
            "status": {
                "conditions": [
                    {
                        "type": "Ready",
                        "status": "True",
                        "lastTransitionTime": "2026-01-15T10:01:00Z",
                    }
                ],
                "containerState": {"running": {"startedAt": "2026-01-15T10:01:00Z"}},
            },
        }
    )

    # Mock Notebook list
    client.list_notebooks = AsyncMock(
        return_value=[
            {
                "metadata": {"name": "ml-notebook", "namespace": "test-namespace"},
                "status": {
                    "conditions": [{"type": "Ready", "status": "True"}],
                    "containerState": {"running": {"startedAt": "2026-01-15T10:01:00Z"}},
                },
            },
            {
                "metadata": {"name": "data-science-notebook", "namespace": "test-namespace"},
                "status": {
                    "conditions": [{"type": "Ready", "status": "False"}],
                    "containerState": {"terminated": {"finishedAt": "2026-01-15T09:00:00Z"}},
                },
            },
        ]
    )

    # Mock Notebook stop (patch)
    client.patch_notebook = AsyncMock(
        return_value={
            "metadata": {"name": "ml-notebook", "namespace": "test-namespace"},
            "status": {
                "containerState": {"terminated": {"finishedAt": "2026-01-15T11:00:00Z"}},
            },
        }
    )

    # Mock Notebook start (patch)
    client.start_notebook = AsyncMock(
        return_value={
            "metadata": {"name": "ml-notebook", "namespace": "test-namespace"},
            "status": {
                "containerState": {"running": {"startedAt": "2026-01-15T11:05:00Z"}},
            },
        }
    )

    # Mock Notebook delete
    client.delete_notebook = AsyncMock(
        return_value={
            "status": "Success",
            "details": {
                "name": "ml-notebook",
                "kind": "Notebook",
            },
        }
    )

    return client


@pytest.mark.integration
@pytest.mark.asyncio
class TestNotebookCreationOperation:
    """Integration tests for notebook creation operations."""

    async def test_create_notebook_success(
        self,
        db_session: AsyncSession,
        mock_openshift_client: MagicMock,
    ) -> None:
        """Test that creating a notebook creates a Notebook resource in OpenShift."""
        # Import here to avoid circular dependencies
        from src.agent.operations.notebook_operations import NotebookOperationExecutor

        executor = NotebookOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=db_session,
        )

        # Create operation request using pre-created session
        operation_request = OperationRequest(
            operation_id=uuid.uuid4(),
            session_id=db_session.test_session_id,
            user_id="test-user",
            operation_type="create",
            target_resource=ResourceType.NOTEBOOK,
            resource_name="ml-notebook",
            parameters={
                "namespace": "test-namespace",
                "image": "tensorflow/tensorflow:latest-jupyter",
                "memory": "4Gi",
                "cpu": "2",
            },
            requires_confirmation=False,
            confirmation_token=None,
        )

        # Execute notebook creation
        result = await executor.execute(operation_request)

        # Verify OpenShift client was called correctly
        mock_openshift_client.create_notebook.assert_called_once()

        # Verify execution result
        assert result.status == "success"
        assert result.resource_name == "ml-notebook"
        assert "ml-notebook" in result.result_data["metadata"]["name"]


@pytest.mark.integration
@pytest.mark.asyncio
class TestListNotebooksOperation:
    """Integration tests for listing notebooks operation."""

    async def test_list_notebooks_returns_all_notebooks(
        self,
        db_session: AsyncSession,
        mock_openshift_client: MagicMock,
    ) -> None:
        """Test that listing notebooks returns all Notebooks in namespace."""
        from src.agent.operations.notebook_operations import NotebookOperationExecutor

        executor = NotebookOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=db_session,
        )

        operation_request = OperationRequest(
            operation_id=uuid.uuid4(),
            session_id=db_session.test_session_id,
            user_id="test-user",
            operation_type="list",
            target_resource=ResourceType.NOTEBOOK,
            parameters={"namespace": "test-namespace"},
            requires_confirmation=False,
        )

        # Execute list operation
        result = await executor.execute(operation_request)

        # Verify OpenShift client was called
        mock_openshift_client.list_notebooks.assert_called_once_with(
            namespace="test-namespace"
        )

        # Verify result
        assert result.status == "success"
        assert len(result.result_data) == 2
        assert any(n["metadata"]["name"] == "ml-notebook" for n in result.result_data)
        assert any(n["metadata"]["name"] == "data-science-notebook" for n in result.result_data)


@pytest.mark.integration
@pytest.mark.asyncio
class TestStopNotebookOperation:
    """Integration tests for notebook stop operation."""

    async def test_stop_notebook_success(
        self,
        db_session: AsyncSession,
        mock_openshift_client: MagicMock,
    ) -> None:
        """Test that stopping a notebook updates the Notebook resource."""
        from src.agent.operations.notebook_operations import NotebookOperationExecutor

        executor = NotebookOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=db_session,
        )

        operation_request = OperationRequest(
            operation_id=uuid.uuid4(),
            session_id=db_session.test_session_id,
            user_id="test-user",
            operation_type="patch",
            target_resource=ResourceType.NOTEBOOK,
            resource_name="ml-notebook",
            parameters={
                "namespace": "test-namespace",
                "action": "stop",
            },
            requires_confirmation=False,
        )

        # Execute stop operation
        result = await executor.execute(operation_request)

        # Verify OpenShift client was called
        mock_openshift_client.patch_notebook.assert_called_once()

        # Verify result
        assert result.status == "success"


@pytest.mark.integration
@pytest.mark.asyncio
class TestStartNotebookOperation:
    """Integration tests for notebook start operation."""

    async def test_start_notebook_success(
        self,
        db_session: AsyncSession,
        mock_openshift_client: MagicMock,
    ) -> None:
        """Test that starting a notebook updates the Notebook resource."""
        from src.agent.operations.notebook_operations import NotebookOperationExecutor

        executor = NotebookOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=db_session,
        )

        operation_request = OperationRequest(
            operation_id=uuid.uuid4(),
            session_id=db_session.test_session_id,
            user_id="test-user",
            operation_type="patch",
            target_resource=ResourceType.NOTEBOOK,
            resource_name="ml-notebook",
            parameters={
                "namespace": "test-namespace",
                "action": "start",
            },
            requires_confirmation=False,
        )

        # Execute start operation
        result = await executor.execute(operation_request)

        # Verify OpenShift client was called
        mock_openshift_client.start_notebook.assert_called_once()

        # Verify result
        assert result.status == "success"


@pytest.mark.integration
@pytest.mark.asyncio
class TestDeleteNotebookOperation:
    """Integration tests for notebook deletion operation."""

    async def test_delete_notebook_success(
        self,
        db_session: AsyncSession,
        mock_openshift_client: MagicMock,
    ) -> None:
        """Test that deleting a notebook removes the Notebook resource."""
        from src.agent.operations.notebook_operations import NotebookOperationExecutor

        executor = NotebookOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=db_session,
        )

        operation_request = OperationRequest(
            operation_id=uuid.uuid4(),
            session_id=db_session.test_session_id,
            user_id="test-user",
            operation_type="delete",
            target_resource=ResourceType.NOTEBOOK,
            resource_name="ml-notebook",
            parameters={"namespace": "test-namespace"},
            requires_confirmation=True,
            confirmation_token="test-confirmation-token",
        )

        # Execute deletion
        result = await executor.execute(operation_request)

        # Verify OpenShift client was called
        mock_openshift_client.delete_notebook.assert_called_once_with(
            name="ml-notebook",
            namespace="test-namespace",
        )

        # Verify result
        assert result.status == "success"
