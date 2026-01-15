"""Performance tests for OpenShift AI Conversational Agent.

These tests verify that the system meets performance requirements:
- T137: <2s response time for simple queries
- T138: <10s response time for complex multi-step operations

Requirements:
- Running PostgreSQL database
- OpenShift cluster access (can be mocked for basic testing)
- LLM service access (or mocked)
"""

import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.models.intent import ActionType


@pytest.fixture
def test_client():
    """Provide FastAPI test client."""
    return TestClient(app)


@pytest.mark.integration
@pytest.mark.performance
class TestSimpleQueryPerformance:
    """Performance tests for simple queries (T137: <2s target)."""

    @pytest.mark.asyncio
    async def test_query_response_time_under_2_seconds(
        self, test_client: TestClient
    ) -> None:
        """Test that simple query responses complete in under 2 seconds."""
        # Mock external dependencies
        with patch(
            "src.services.intent_parser.IntentParser.parse_intent"
        ) as mock_parser:
            # Mock intent parsing to return quickly
            mock_intent = MagicMock()
            mock_intent.action_type = ActionType.LIST_MODELS
            mock_intent.parameters = {}
            mock_intent.confidence = 0.95
            mock_parser.return_value = mock_intent

            with patch(
                "src.agent.operations.model_operations.ModelOperations.list_models"
            ) as mock_list:
                # Mock OpenShift operation
                mock_list.return_value = {
                    "models": [
                        {
                            "name": "fraud-detector",
                            "status": "ready",
                            "replicas": 2,
                        }
                    ]
                }

                # Measure query execution time
                start_time = time.time()

                response = test_client.post(
                    "/v1/query",
                    json={
                        "query": "List all my deployed models",
                        "user_id": "test-user",
                    },
                )

                elapsed_time = time.time() - start_time

                assert response.status_code == 200
                assert (
                    elapsed_time < 2.0
                ), f"Query took {elapsed_time:.2f}s, expected <2s"

    @pytest.mark.asyncio
    async def test_model_status_query_performance(
        self, test_client: TestClient
    ) -> None:
        """Test model status query completes in under 2 seconds."""
        with patch(
            "src.services.intent_parser.IntentParser.parse_intent"
        ) as mock_parser:
            mock_intent = MagicMock()
            mock_intent.action_type = ActionType.GET_MODEL_STATUS
            mock_intent.parameters = {"model_name": "fraud-detector"}
            mock_intent.confidence = 0.92
            mock_parser.return_value = mock_intent

            with patch(
                "src.agent.operations.model_operations.ModelOperations.get_model_status"
            ) as mock_status:
                mock_status.return_value = {
                    "name": "fraud-detector",
                    "status": "ready",
                    "replicas": 2,
                    "latency_p95_ms": 45,
                }

                start_time = time.time()

                response = test_client.post(
                    "/v1/query",
                    json={
                        "query": "What's the status of my fraud-detector model?",
                        "user_id": "test-user",
                    },
                )

                elapsed_time = time.time() - start_time

                assert response.status_code == 200
                assert (
                    elapsed_time < 2.0
                ), f"Status query took {elapsed_time:.2f}s, expected <2s"

    @pytest.mark.asyncio
    async def test_list_notebooks_query_performance(
        self, test_client: TestClient
    ) -> None:
        """Test listing notebooks completes in under 2 seconds."""
        with patch(
            "src.services.intent_parser.IntentParser.parse_intent"
        ) as mock_parser:
            mock_intent = MagicMock()
            mock_intent.action_type = ActionType.LIST_NOTEBOOKS
            mock_intent.parameters = {}
            mock_intent.confidence = 0.90
            mock_parser.return_value = mock_intent

            with patch(
                "src.agent.operations.notebook_operations.NotebookOperations.list_notebooks"
            ) as mock_list:
                mock_list.return_value = {
                    "notebooks": [
                        {"name": "experiment-1", "status": "running"},
                        {"name": "experiment-2", "status": "stopped"},
                    ]
                }

                start_time = time.time()

                response = test_client.post(
                    "/v1/query",
                    json={
                        "query": "Show me all my notebooks",
                        "user_id": "test-user",
                    },
                )

                elapsed_time = time.time() - start_time

                assert response.status_code == 200
                assert (
                    elapsed_time < 2.0
                ), f"List notebooks took {elapsed_time:.2f}s, expected <2s"


@pytest.mark.integration
@pytest.mark.performance
class TestComplexOperationPerformance:
    """Performance tests for complex operations (T138: <10s target)."""

    @pytest.mark.asyncio
    async def test_deploy_model_operation_under_10_seconds(
        self, test_client: TestClient
    ) -> None:
        """Test that model deployment completes in under 10 seconds."""
        with patch(
            "src.services.intent_parser.IntentParser.parse_intent"
        ) as mock_parser:
            mock_intent = MagicMock()
            mock_intent.action_type = ActionType.DEPLOY_MODEL
            mock_intent.parameters = {
                "model_name": "new-model",
                "storage_uri": "s3://models/new-model",
                "framework": "pytorch",
            }
            mock_intent.confidence = 0.88
            mock_parser.return_value = mock_intent

            with patch(
                "src.agent.operations.model_operations.ModelOperations.deploy_model"
            ) as mock_deploy:
                # Simulate realistic deployment time (2-3 seconds)
                async def slow_deploy(*args, **kwargs):
                    await asyncio.sleep(2.5)
                    return {
                        "name": "new-model",
                        "status": "deploying",
                        "endpoint": "http://new-model.example.com",
                    }

                mock_deploy.side_effect = slow_deploy

                start_time = time.time()

                response = test_client.post(
                    "/v1/query",
                    json={
                        "query": "Deploy my new PyTorch model from s3://models/new-model",
                        "user_id": "test-user",
                    },
                )

                elapsed_time = time.time() - start_time

                assert response.status_code == 200
                assert (
                    elapsed_time < 10.0
                ), f"Deploy operation took {elapsed_time:.2f}s, expected <10s"

    @pytest.mark.asyncio
    async def test_pipeline_creation_performance(
        self, test_client: TestClient
    ) -> None:
        """Test that pipeline creation completes in under 10 seconds."""
        with patch(
            "src.services.intent_parser.IntentParser.parse_intent"
        ) as mock_parser:
            mock_intent = MagicMock()
            mock_intent.action_type = ActionType.CREATE_PIPELINE
            mock_intent.parameters = {
                "pipeline_name": "data-prep-pipeline",
                "steps": ["ingest", "transform", "validate"],
            }
            mock_intent.confidence = 0.85
            mock_parser.return_value = mock_intent

            with patch(
                "src.agent.operations.pipeline_operations.PipelineOperations.create_pipeline"
            ) as mock_create:
                # Simulate realistic pipeline creation (3-4 seconds)
                async def slow_create(*args, **kwargs):
                    await asyncio.sleep(3.5)
                    return {
                        "name": "data-prep-pipeline",
                        "status": "created",
                        "steps": 3,
                    }

                mock_create.side_effect = slow_create

                start_time = time.time()

                response = test_client.post(
                    "/v1/query",
                    json={
                        "query": "Create a data preparation pipeline with ingest, transform, and validate steps",
                        "user_id": "test-user",
                    },
                )

                elapsed_time = time.time() - start_time

                assert response.status_code == 200
                assert (
                    elapsed_time < 10.0
                ), f"Pipeline creation took {elapsed_time:.2f}s, expected <10s"

    @pytest.mark.asyncio
    async def test_multi_model_deployment_performance(
        self, test_client: TestClient
    ) -> None:
        """Test deploying multiple models completes in under 10 seconds."""
        with patch(
            "src.services.intent_parser.IntentParser.parse_intent"
        ) as mock_parser:
            mock_intent = MagicMock()
            mock_intent.action_type = ActionType.DEPLOY_MODEL
            mock_intent.parameters = {
                "model_names": [
                    "model-1",
                    "model-2",
                    "model-3",
                ],  # Multiple models
            }
            mock_intent.confidence = 0.82
            mock_parser.return_value = mock_intent

            with patch(
                "src.agent.operations.model_operations.ModelOperations.deploy_model"
            ) as mock_deploy:
                # Simulate parallel deployment (should be faster than sequential)
                async def batch_deploy(*args, **kwargs):
                    await asyncio.sleep(4.0)  # Parallel deployment time
                    return {
                        "deployed": ["model-1", "model-2", "model-3"],
                        "status": "deploying",
                    }

                mock_deploy.side_effect = batch_deploy

                start_time = time.time()

                response = test_client.post(
                    "/v1/query",
                    json={
                        "query": "Deploy model-1, model-2, and model-3",
                        "user_id": "test-user",
                    },
                )

                elapsed_time = time.time() - start_time

                assert response.status_code == 200
                assert (
                    elapsed_time < 10.0
                ), f"Multi-model deployment took {elapsed_time:.2f}s, expected <10s"


@pytest.mark.integration
@pytest.mark.performance
class TestEndToEndPerformance:
    """End-to-end performance tests for complete workflows."""

    @pytest.mark.asyncio
    async def test_conversation_flow_performance(
        self, test_client: TestClient
    ) -> None:
        """Test complete conversation flow meets performance targets."""
        session_id = str(uuid.uuid4())

        # Query 1: List models (<2s)
        start = time.time()
        response1 = test_client.post(
            "/v1/query",
            json={"query": "List my models", "session_id": session_id},
        )
        time1 = time.time() - start
        assert response1.status_code == 200
        assert time1 < 2.0, f"Query 1 took {time1:.2f}s"

        # Query 2: Get status (<2s)
        start = time.time()
        response2 = test_client.post(
            "/v1/query",
            json={
                "query": "What's the status of fraud-detector?",
                "session_id": session_id,
            },
        )
        time2 = time.time() - start
        assert response2.status_code == 200
        assert time2 < 2.0, f"Query 2 took {time2:.2f}s"

        # Total conversation time should be reasonable
        total_time = time1 + time2
        assert (
            total_time < 5.0
        ), f"Total conversation took {total_time:.2f}s, expected <5s"


# Import asyncio for async sleep in tests
import asyncio
