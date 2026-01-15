"""Contract tests for conversation API endpoints.

These tests verify the API contract (request/response schemas) for the conversation endpoints.
They ensure that the API adheres to the documented contract specifications.
"""

import os
import tempfile
import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import Header, HTTPException, status
from httpx import AsyncClient

from src.api.main import app
from src.api.middleware.auth import get_current_user

# Set test database URL
temp_dir = tempfile.gettempdir()
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{temp_dir}/test_contract_rhails.db"


# Override authentication dependency for testing
async def mock_get_current_user(authorization: str = Header(None)):
    """Mock authentication for contract tests.

    Validates that a valid Authorization header is present.
    """
    # If no authorization header, raise 401
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )

    # Check for valid Bearer token format
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization format",
        )

    # Extract token
    token = authorization.replace("Bearer ", "")

    # For contract tests, accept "test-token" as valid
    if token != "test-token":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    return {
        "user_id": "test-user",
        "username": "testuser",
        "email": "test@example.com",
        "groups": ["system:authenticated"],
    }


# Apply dependency override
app.dependency_overrides[get_current_user] = mock_get_current_user


# Mock OpenShift client for contract tests
@pytest.fixture(scope="module", autouse=True)
def mock_openshift_client():
    """Mock OpenShift client to avoid real cluster connections."""
    with patch("src.api.routes.query.OpenShiftClient") as mock_client_class:
        # Create mock instance
        mock_instance = MagicMock()

        # Mock successful InferenceService creation
        mock_instance.create_inference_service = AsyncMock(
            return_value={
                "apiVersion": "serving.kserve.io/v1beta1",
                "kind": "InferenceService",
                "metadata": {
                    "name": "test-model",
                    "namespace": "default",
                    "creationTimestamp": "2026-01-15T10:00:00Z",
                },
                "spec": {
                    "predictor": {
                        "model": {
                            "modelFormat": {"name": "sklearn"},
                            "storageUri": "s3://models/test-model",
                        },
                        "minReplicas": 1,
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
                    "url": "https://test-model.default.svc.cluster.local",
                },
            }
        )

        # Mock get status
        mock_instance.get_inference_service = AsyncMock(
            return_value={
                "metadata": {"name": "test-model", "namespace": "default"},
                "status": {
                    "conditions": [{"type": "Ready", "status": "True"}],
                    "url": "https://test-model.default.svc.cluster.local",
                },
            }
        )

        # Set the instance to be returned when OpenShiftClient() is instantiated
        mock_client_class.return_value = mock_instance

        yield mock_instance


@pytest.fixture(scope="module", autouse=True)
async def setup_test_database():
    """Initialize test database for contract tests."""
    from src.services.database import DatabaseManager

    db_manager = DatabaseManager(os.environ["DATABASE_URL"])
    await db_manager.initialize_async()
    await db_manager.create_tables()

    yield

    await db_manager.drop_tables()
    await db_manager.close()


@pytest.fixture
def valid_auth_headers() -> dict[str, str]:
    """Provide valid authentication headers for testing.

    In a real environment, this would use a valid OAuth token.
    For testing, we mock the authentication middleware.
    """
    return {"Authorization": "Bearer test-token"}


@pytest.fixture
def model_deployment_request() -> dict[str, Any]:
    """Provide a valid model deployment request payload."""
    return {
        "query": "Deploy my sentiment-analysis model with 2 replicas",
        "session_id": None,  # Start new session
    }


@pytest.fixture
def model_status_request() -> dict[str, Any]:
    """Provide a valid model status query request payload."""
    return {
        "query": "What's the status of my sentiment-analysis model?",
        "session_id": None,  # Start new session
    }


@pytest.mark.contract
@pytest.mark.asyncio
class TestQueryEndpointContract:
    """Contract tests for POST /v1/query endpoint."""

    async def test_model_deployment_request_schema(
        self,
        valid_auth_headers: dict[str, str],
        model_deployment_request: dict[str, Any],
    ) -> None:
        """Test that model deployment requests follow the correct schema.

        Expected Request Schema:
        {
            "query": str (required, min_length=1, max_length=1000),
            "session_id": Optional[UUID]
        }

        Expected Response Schema (Success):
        {
            "session_id": UUID,
            "message_id": UUID,
            "response": str,
            "requires_confirmation": bool,
            "confirmation_token": Optional[str],
            "metadata": {
                "intent": str,
                "confidence": float,
                "target_resources": list[dict]
            }
        }
        """
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/v1/query",
                json=model_deployment_request,
                headers=valid_auth_headers,
            )

            # Verify response status
            assert response.status_code == status.HTTP_200_OK

            # Verify response schema
            data = response.json()

            # Required fields
            assert "session_id" in data
            assert "message_id" in data
            assert "response" in data
            assert "requires_confirmation" in data

            # Validate field types
            assert isinstance(data["session_id"], str)
            assert isinstance(data["message_id"], str)
            assert isinstance(data["response"], str)
            assert isinstance(data["requires_confirmation"], bool)

            # session_id and message_id should be valid UUIDs
            uuid.UUID(data["session_id"])
            uuid.UUID(data["message_id"])

            # Confirmation token should be present if confirmation required
            if data["requires_confirmation"]:
                assert "confirmation_token" in data
                assert isinstance(data["confirmation_token"], str)

            # Metadata should contain intent information
            assert "metadata" in data
            metadata = data["metadata"]
            assert "intent" in metadata
            assert "confidence" in metadata
            assert "target_resources" in metadata

            assert isinstance(metadata["intent"], str)
            assert isinstance(metadata["confidence"], float)
            assert 0.0 <= metadata["confidence"] <= 1.0
            assert isinstance(metadata["target_resources"], list)

    async def test_model_status_query_request_schema(
        self,
        valid_auth_headers: dict[str, str],
        model_status_request: dict[str, Any],
    ) -> None:
        """Test that model status queries follow the correct schema.

        This test verifies query operations that don't require confirmation.
        """
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/v1/query",
                json=model_status_request,
                headers=valid_auth_headers,
            )

            # Verify response status
            assert response.status_code == status.HTTP_200_OK

            # Verify response schema
            data = response.json()

            # For query operations, confirmation should not be required
            assert data["requires_confirmation"] is False
            assert "confirmation_token" not in data or data["confirmation_token"] is None

            # Response should contain model status information
            assert len(data["response"]) > 0

            # Metadata should indicate query intent
            assert data["metadata"]["intent"] in [
                "get_status",
                "list_models",
                "get_model_status",
            ]

    async def test_invalid_request_missing_query(
        self,
        valid_auth_headers: dict[str, str],
    ) -> None:
        """Test that requests without query field are rejected."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/v1/query",
                json={"session_id": str(uuid.uuid4())},  # Missing query
                headers=valid_auth_headers,
            )

            # Should return validation error
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

            error_data = response.json()
            assert "detail" in error_data

    async def test_invalid_request_empty_query(
        self,
        valid_auth_headers: dict[str, str],
    ) -> None:
        """Test that requests with empty query are rejected."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/v1/query",
                json={"query": "", "session_id": None},
                headers=valid_auth_headers,
            )

            # Should return validation error
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_invalid_request_query_too_long(
        self,
        valid_auth_headers: dict[str, str],
    ) -> None:
        """Test that requests with overly long queries are rejected."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/v1/query",
                json={"query": "x" * 1001, "session_id": None},  # Exceeds max_length
                headers=valid_auth_headers,
            )

            # Should return validation error
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_invalid_request_invalid_session_id(
        self,
        valid_auth_headers: dict[str, str],
    ) -> None:
        """Test that requests with invalid session_id format are rejected."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/v1/query",
                json={"query": "List my models", "session_id": "not-a-uuid"},
                headers=valid_auth_headers,
            )

            # Should return validation error
            assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    async def test_unauthorized_request_missing_auth(
        self,
        model_deployment_request: dict[str, Any],
    ) -> None:
        """Test that requests without authentication are rejected."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/v1/query",
                json=model_deployment_request,
                # No headers - missing authentication
            )

            # Should return unauthorized
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_unauthorized_request_invalid_token(
        self,
        model_deployment_request: dict[str, Any],
    ) -> None:
        """Test that requests with invalid tokens are rejected."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/v1/query",
                json=model_deployment_request,
                headers={"Authorization": "Bearer invalid-token"},
            )

            # Should return unauthorized
            assert response.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_response_includes_request_id_header(
        self,
        valid_auth_headers: dict[str, str],
        model_deployment_request: dict[str, Any],
    ) -> None:
        """Test that all responses include X-Request-ID header for tracing."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/v1/query",
                json=model_deployment_request,
                headers=valid_auth_headers,
            )

            # Verify X-Request-ID header is present
            assert "X-Request-ID" in response.headers

            # Verify it's a valid UUID
            request_id = response.headers["X-Request-ID"]
            uuid.UUID(request_id)


@pytest.mark.contract
@pytest.mark.asyncio
class TestPipelineOperationsContract:
    """Contract tests for pipeline operations via /v1/query endpoint."""

    async def test_pipeline_creation_request_schema(
        self,
        valid_auth_headers: dict[str, str],
    ) -> None:
        """Test that pipeline creation requests follow the correct schema.

        Expected Request Schema:
        {
            "query": str (required, min_length=1, max_length=1000),
            "session_id": Optional[UUID]
        }

        Expected Response Schema (Success):
        {
            "session_id": UUID,
            "message_id": UUID,
            "response": str,
            "requires_confirmation": bool,
            "confirmation_token": Optional[str],
            "metadata": {
                "intent": str,  # Should be "create_pipeline"
                "confidence": float,
                "target_resources": list[dict]
            }
        }
        """
        pipeline_request = {
            "query": "Create a pipeline to preprocess customer reviews from S3",
            "session_id": None,
        }

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/v1/query",
                json=pipeline_request,
                headers=valid_auth_headers,
            )

            # Verify response status
            assert response.status_code == status.HTTP_200_OK

            # Verify response schema
            data = response.json()

            # Required fields
            assert "session_id" in data
            assert "message_id" in data
            assert "response" in data
            assert "requires_confirmation" in data

            # Validate field types
            assert isinstance(data["session_id"], str)
            assert isinstance(data["message_id"], str)
            assert isinstance(data["response"], str)
            assert isinstance(data["requires_confirmation"], bool)

            # session_id and message_id should be valid UUIDs
            uuid.UUID(data["session_id"])
            uuid.UUID(data["message_id"])

            # Metadata should contain intent information
            assert "metadata" in data
            metadata = data["metadata"]
            assert "intent" in metadata
            assert "confidence" in metadata
            assert "target_resources" in metadata

            # Intent should be pipeline creation
            assert metadata["intent"] == "create_pipeline"
            assert isinstance(metadata["confidence"], float)
            assert 0.0 <= metadata["confidence"] <= 1.0
            assert isinstance(metadata["target_resources"], list)


@pytest.mark.contract
@pytest.mark.asyncio
class TestNotebookOperationsContract:
    """Contract tests for notebook operations via /v1/query endpoint."""

    async def test_notebook_creation_request_schema(
        self,
        valid_auth_headers: dict[str, str],
    ) -> None:
        """Test that notebook creation requests follow the correct schema.

        Expected Request Schema:
        {
            "query": str (required, min_length=1, max_length=1000),
            "session_id": Optional[UUID]
        }

        Expected Response Schema (Success):
        {
            "session_id": UUID,
            "message_id": UUID,
            "response": str,
            "requires_confirmation": bool,
            "confirmation_token": Optional[str],
            "metadata": {
                "intent": str,  # Should be "create_notebook"
                "confidence": float,
                "target_resources": list[dict]
            }
        }
        """
        notebook_request = {
            "query": "Create a Python notebook with TensorFlow and 4GB RAM",
            "session_id": None,
        }

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/v1/query",
                json=notebook_request,
                headers=valid_auth_headers,
            )

            # Verify response status
            assert response.status_code == status.HTTP_200_OK

            # Verify response schema
            data = response.json()

            # Required fields
            assert "session_id" in data
            assert "message_id" in data
            assert "response" in data
            assert "requires_confirmation" in data

            # Validate field types
            assert isinstance(data["session_id"], str)
            assert isinstance(data["message_id"], str)
            assert isinstance(data["response"], str)
            assert isinstance(data["requires_confirmation"], bool)

            # session_id and message_id should be valid UUIDs
            uuid.UUID(data["session_id"])
            uuid.UUID(data["message_id"])

            # Metadata should contain intent information
            assert "metadata" in data
            metadata = data["metadata"]
            assert "intent" in metadata
            assert "confidence" in metadata
            assert "target_resources" in metadata

            # Intent should be notebook creation
            assert metadata["intent"] == "create_notebook"
            assert isinstance(metadata["confidence"], float)
            assert 0.0 <= metadata["confidence"] <= 1.0
            assert isinstance(metadata["target_resources"], list)


@pytest.mark.contract
@pytest.mark.asyncio
class TestProjectOperationsContract:
    """Contract tests for project operations via /v1/query endpoint.

    These tests ensure the API contract for project management operations
    including creation, listing, user management, and resource querying.
    """

    async def test_project_creation_request_schema(
        self,
        valid_auth_headers: dict[str, str],
    ) -> None:
        """Test that project creation requests follow the correct schema."""
        project_request = {
            "query": "Create a project called data-science with 32GB memory and 8 CPU limit",
            "session_id": None,
        }

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/v1/query",
                json=project_request,
                headers=valid_auth_headers,
            )

            # Verify response status
            assert response.status_code == status.HTTP_200_OK

            # Verify response schema
            data = response.json()

            # Required fields
            assert "session_id" in data
            assert "message_id" in data
            assert "response" in data
            assert "requires_confirmation" in data

            # Validate field types
            assert isinstance(data["session_id"], str)
            assert isinstance(data["message_id"], str)
            assert isinstance(data["response"], str)
            assert isinstance(data["requires_confirmation"], bool)

            # session_id and message_id should be valid UUIDs
            uuid.UUID(data["session_id"])
            uuid.UUID(data["message_id"])

            # Metadata should contain intent information
            assert "metadata" in data
            metadata = data["metadata"]
            assert "intent" in metadata
            assert "confidence" in metadata
            assert "target_resources" in metadata

            # Intent should be project creation
            assert metadata["intent"] == "create_project"
            assert isinstance(metadata["confidence"], float)
            assert 0.0 <= metadata["confidence"] <= 1.0
            assert isinstance(metadata["target_resources"], list)

    async def test_list_projects_request_schema(
        self,
        valid_auth_headers: dict[str, str],
    ) -> None:
        """Test that list projects requests follow the correct schema."""
        list_request = {
            "query": "Show me all projects",
            "session_id": None,
        }

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/v1/query",
                json=list_request,
                headers=valid_auth_headers,
            )

            # Verify response status
            assert response.status_code == status.HTTP_200_OK

            # Verify response schema
            data = response.json()

            # Metadata should indicate list projects intent
            metadata = data["metadata"]
            assert metadata["intent"] == "list_projects"

    async def test_add_user_to_project_request_schema(
        self,
        valid_auth_headers: dict[str, str],
    ) -> None:
        """Test that add user to project requests follow the correct schema."""
        add_user_request = {
            "query": "Add user jane.doe@company.com to data-science project",
            "session_id": None,
        }

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/v1/query",
                json=add_user_request,
                headers=valid_auth_headers,
            )

            # Verify response status
            assert response.status_code == status.HTTP_200_OK

            # Verify response schema
            data = response.json()

            # Metadata should indicate add user to project intent
            metadata = data["metadata"]
            assert metadata["intent"] == "add_user_to_project"

    async def test_get_project_resources_request_schema(
        self,
        valid_auth_headers: dict[str, str],
    ) -> None:
        """Test that get project resources requests follow the correct schema."""
        resources_request = {
            "query": "How much memory is data-science using?",
            "session_id": None,
        }

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/v1/query",
                json=resources_request,
                headers=valid_auth_headers,
            )

            # Verify response status
            assert response.status_code == status.HTTP_200_OK

            # Verify response schema
            data = response.json()

            # Metadata should indicate get project resources intent
            metadata = data["metadata"]
            assert metadata["intent"] == "get_project_resources"


@pytest.mark.contract
@pytest.mark.asyncio
class TestMonitoringOperationsContract:
    """Contract tests for model monitoring and troubleshooting operations."""

    async def test_analyze_logs_request_schema(
        self,
        valid_auth_headers: dict[str, str],
    ) -> None:
        """Test that log analysis requests follow the correct schema."""
        analyze_request = {
            "query": "Why is my fraud-detector failing requests?",
            "session_id": None,
        }

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/v1/query",
                json=analyze_request,
                headers=valid_auth_headers,
            )

            # Verify response status
            assert response.status_code == status.HTTP_200_OK

            # Verify response schema
            data = response.json()

            # Required fields
            assert "session_id" in data
            assert "message_id" in data
            assert "response" in data
            assert "requires_confirmation" in data
            assert "metadata" in data

            # Metadata should indicate log analysis intent
            metadata = data["metadata"]
            assert metadata["intent"] == "analyze_logs"

    async def test_compare_metrics_request_schema(
        self,
        valid_auth_headers: dict[str, str],
    ) -> None:
        """Test that metrics comparison requests follow the correct schema."""
        compare_request = {
            "query": "Compare the performance of my sentiment-model today versus last week",
            "session_id": None,
        }

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/v1/query",
                json=compare_request,
                headers=valid_auth_headers,
            )

            # Verify response status
            assert response.status_code == status.HTTP_200_OK

            # Verify response schema
            data = response.json()

            # Metadata should indicate metrics comparison intent
            metadata = data["metadata"]
            assert metadata["intent"] == "compare_metrics"

    async def test_diagnose_performance_request_schema(
        self,
        valid_auth_headers: dict[str, str],
    ) -> None:
        """Test that performance diagnosis requests follow the correct schema."""
        diagnose_request = {
            "query": "Is my recommendation-engine CPU-bound?",
            "session_id": None,
        }

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/v1/query",
                json=diagnose_request,
                headers=valid_auth_headers,
            )

            # Verify response status
            assert response.status_code == status.HTTP_200_OK

            # Verify response schema
            data = response.json()

            # Metadata should indicate performance diagnosis intent
            metadata = data["metadata"]
            assert metadata["intent"] == "diagnose_performance"

    async def test_prediction_distribution_request_schema(
        self,
        valid_auth_headers: dict[str, str],
    ) -> None:
        """Test that prediction distribution requests follow the correct schema."""
        distribution_request = {
            "query": "Show me the prediction distribution for my customer-churn model over the last month",
            "session_id": None,
        }

        async with AsyncClient(app=app, base_url="http://test") as client:
            response = await client.post(
                "/v1/query",
                json=distribution_request,
                headers=valid_auth_headers,
            )

            # Verify response status
            assert response.status_code == status.HTTP_200_OK

            # Verify response schema
            data = response.json()

            # Metadata should indicate prediction distribution intent
            metadata = data["metadata"]
            assert metadata["intent"] == "get_prediction_distribution"
