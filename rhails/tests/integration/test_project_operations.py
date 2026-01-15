"""Integration tests for project operation execution.

This module contains integration tests for the project operation executor,
which handles project creation, listing, user management, and resource querying.
"""

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.operations.project_operations import ProjectOperationExecutor
from src.models.intent import OperationRequest
from src.models.openshift import ResourceType


@pytest.fixture
def mock_openshift_client() -> MagicMock:
    """Provide a mocked OpenShift client for testing."""
    client = MagicMock()

    # Mock create_project
    client.create_project = AsyncMock(
        return_value={
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": "data-science",
                "namespace": "data-science",
                "annotations": {
                    "openshift.io/display-name": "data-science",
                    "openshift.io/description": "",
                },
            },
        }
    )

    # Mock list_projects
    client.list_projects = AsyncMock(
        return_value=[
            {
                "metadata": {
                    "name": "data-science",
                    "annotations": {"openshift.io/display-name": "Data Science"},
                }
            },
            {
                "metadata": {
                    "name": "customer-analytics",
                    "annotations": {"openshift.io/display-name": "Customer Analytics"},
                }
            },
        ]
    )

    # Mock get_resource_quota
    client.get_resource_quota = AsyncMock(
        return_value={
            "status": {
                "used": {
                    "requests.memory": "16Gi",
                    "requests.cpu": "8",
                }
            }
        }
    )

    # Mock add_user_to_project
    client.add_user_to_project = AsyncMock(
        return_value={
            "apiVersion": "rbac.authorization.k8s.io/v1",
            "kind": "RoleBinding",
            "metadata": {
                "name": "jane.doe-edit",
                "namespace": "data-science",
            },
        }
    )

    return client


@pytest.mark.integration
@pytest.mark.asyncio
class TestProjectCreationOperation:
    """Integration tests for project creation operations."""

    async def test_create_project_success(
        self,
        async_db_session: AsyncSession,
        mock_openshift_client: MagicMock,
    ) -> None:
        """Test successful project creation."""
        executor = ProjectOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=async_db_session,
        )

        operation_request = OperationRequest(
            session_id=uuid.uuid4(),
            user_id="test-user",
            operation_type="create",
            target_resource=ResourceType.PROJECT,
            resource_name="data-science",
            parameters={
                "project_name": "data-science",
                "memory_limit": "32Gi",
                "cpu_limit": "16",
            },
            requires_confirmation=False,
        )

        result = await executor.execute(operation_request)

        # Verify OpenShift client was called
        mock_openshift_client.create_project.assert_called_once()

        # Verify result
        assert result.status == "success"
        assert result.resource_name == "data-science"
        assert result.resource_type == ResourceType.PROJECT

    async def test_create_project_without_quotas(
        self,
        async_db_session: AsyncSession,
        mock_openshift_client: MagicMock,
    ) -> None:
        """Test project creation without resource quotas."""
        executor = ProjectOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=async_db_session,
        )

        operation_request = OperationRequest(
            session_id=uuid.uuid4(),
            user_id="test-user",
            operation_type="create",
            target_resource=ResourceType.PROJECT,
            resource_name="simple-project",
            parameters={"project_name": "simple-project"},
            requires_confirmation=False,
        )

        result = await executor.execute(operation_request)

        # Should still succeed
        assert result.status == "success"
        assert result.resource_name == "simple-project"


@pytest.mark.integration
@pytest.mark.asyncio
class TestProjectListOperation:
    """Integration tests for project listing operations."""

    async def test_list_projects_success(
        self,
        async_db_session: AsyncSession,
        mock_openshift_client: MagicMock,
    ) -> None:
        """Test successful project listing."""
        executor = ProjectOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=async_db_session,
        )

        operation_request = OperationRequest(
            session_id=uuid.uuid4(),
            user_id="test-user",
            operation_type="list",
            target_resource=ResourceType.PROJECT,
            resource_name=None,
            parameters={},
            requires_confirmation=False,
        )

        result = await executor.execute(operation_request)

        # Verify OpenShift client was called
        mock_openshift_client.list_projects.assert_called_once()

        # Verify result
        assert result.status == "success"
        assert isinstance(result.result_data, list)
        assert len(result.result_data) == 2


@pytest.mark.integration
@pytest.mark.asyncio
class TestGetProjectResourcesOperation:
    """Integration tests for getting project resource usage."""

    async def test_get_project_resources_success(
        self,
        async_db_session: AsyncSession,
        mock_openshift_client: MagicMock,
    ) -> None:
        """Test successful project resource usage query."""
        executor = ProjectOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=async_db_session,
        )

        operation_request = OperationRequest(
            session_id=uuid.uuid4(),
            user_id="test-user",
            operation_type="get",
            target_resource=ResourceType.PROJECT,
            resource_name="data-science",
            parameters={"project_name": "data-science"},
            requires_confirmation=False,
        )

        result = await executor.execute(operation_request)

        # Verify OpenShift client was called
        mock_openshift_client.get_resource_quota.assert_called_once_with(
            namespace="data-science"
        )

        # Verify result
        assert result.status == "success"
        assert result.resource_name == "data-science"
        assert "used" in result.result_data["status"]


@pytest.mark.integration
@pytest.mark.asyncio
class TestAddUserToProjectOperation:
    """Integration tests for adding users to projects."""

    async def test_add_user_to_project_success(
        self,
        async_db_session: AsyncSession,
        mock_openshift_client: MagicMock,
    ) -> None:
        """Test successful user addition to project."""
        executor = ProjectOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=async_db_session,
        )

        operation_request = OperationRequest(
            session_id=uuid.uuid4(),
            user_id="test-user",
            operation_type="update",
            target_resource=ResourceType.PROJECT,
            resource_name="data-science",
            parameters={
                "project_name": "data-science",
                "username": "jane.doe@company.com",
                "role": "edit",
            },
            requires_confirmation=False,
        )

        result = await executor.execute(operation_request)

        # Verify OpenShift client was called
        mock_openshift_client.add_user_to_project.assert_called_once_with(
            username="jane.doe@company.com",
            namespace="data-science",
            role="edit",
        )

        # Verify result
        assert result.status == "success"
        assert result.resource_name == "data-science"

    async def test_add_user_with_default_role(
        self,
        async_db_session: AsyncSession,
        mock_openshift_client: MagicMock,
    ) -> None:
        """Test adding user with default role."""
        executor = ProjectOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=async_db_session,
        )

        operation_request = OperationRequest(
            session_id=uuid.uuid4(),
            user_id="test-user",
            operation_type="update",
            target_resource=ResourceType.PROJECT,
            resource_name="data-science",
            parameters={
                "project_name": "data-science",
                "username": "john.smith@company.com",
                # No role specified - should default to "edit"
            },
            requires_confirmation=False,
        )

        result = await executor.execute(operation_request)

        # Verify default role was used
        mock_openshift_client.add_user_to_project.assert_called_once_with(
            username="john.smith@company.com",
            namespace="data-science",
            role="edit",  # Default role
        )

        assert result.status == "success"
