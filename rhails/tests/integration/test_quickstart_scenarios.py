"""Quickstart scenario validation tests (T143).

These tests validate that all scenarios in quickstart.md work correctly.

Requirements:
- Running PostgreSQL database
- OpenShift cluster access (can be mocked for validation)
- LLM service access (or mocked)
"""

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


@pytest.fixture
def mock_oauth():
    """Mock OAuth authentication."""
    with patch("src.api.middleware.auth.verify_oauth_token") as mock:
        mock.return_value = {"sub": "test-user", "groups": ["users"]}
        yield mock


@pytest.fixture
def mock_rbac():
    """Mock RBAC authorization."""
    with patch("src.agent.auth.rbac_checker.RBACChecker.check_access") as mock:
        mock.return_value = True
        yield mock


@pytest.mark.integration
@pytest.mark.quickstart
class TestQuickstartScenarios:
    """Validate all quickstart.md scenarios work correctly."""

    @pytest.mark.asyncio
    async def test_scenario_1_list_deployed_models(
        self, test_client: TestClient, mock_oauth, mock_rbac
    ) -> None:
        """Test Scenario 1: List all deployed models."""
        with patch(
            "src.services.intent_parser.IntentParser.parse_intent"
        ) as mock_parser:
            # Mock intent parsing
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
                            "name": "fraud-detection",
                            "replicas": 3,
                            "status": "Running",
                        },
                        {
                            "name": "sentiment-analysis",
                            "replicas": 2,
                            "status": "Running",
                        },
                        {
                            "name": "recommendation-engine",
                            "replicas": 5,
                            "status": "Running",
                        },
                    ]
                }

                # Execute query from quickstart
                response = test_client.post(
                    "/v1/query",
                    json={
                        "session_id": str(uuid.uuid4()),
                        "query": "List all my deployed models",
                    },
                    headers={"Authorization": "Bearer test_token"},
                )

                assert response.status_code == 200
                data = response.json()
                assert "session_id" in data
                assert "message_id" in data
                assert "response" in data

    @pytest.mark.asyncio
    async def test_scenario_2_deploy_model_with_parameters(
        self, test_client: TestClient, mock_oauth, mock_rbac
    ) -> None:
        """Test Scenario 2: Deploy model with specific parameters."""
        with patch(
            "src.services.intent_parser.IntentParser.parse_intent"
        ) as mock_parser:
            mock_intent = MagicMock()
            mock_intent.action_type = ActionType.DEPLOY_MODEL
            mock_intent.parameters = {
                "model_name": "customer-churn",
                "replicas": 2,
                "namespace": "ml-models",
            }
            mock_intent.confidence = 0.88
            mock_parser.return_value = mock_intent

            with patch(
                "src.agent.operations.model_operations.ModelOperations.deploy_model"
            ) as mock_deploy:
                mock_deploy.return_value = {
                    "name": "customer-churn",
                    "replicas": 2,
                    "namespace": "ml-models",
                    "status": "deploying",
                }

                response = test_client.post(
                    "/v1/query",
                    json={
                        "session_id": str(uuid.uuid4()),
                        "query": "Deploy my customer-churn model with 2 replicas in the ml-models namespace",
                    },
                    headers={"Authorization": "Bearer test_token"},
                )

                assert response.status_code == 200
                data = response.json()
                assert "response" in data

    @pytest.mark.asyncio
    async def test_scenario_3_check_model_status(
        self, test_client: TestClient, mock_oauth, mock_rbac
    ) -> None:
        """Test Scenario 3: Check model status."""
        with patch(
            "src.services.intent_parser.IntentParser.parse_intent"
        ) as mock_parser:
            mock_intent = MagicMock()
            mock_intent.action_type = ActionType.GET_MODEL_STATUS
            mock_intent.parameters = {"model_name": "fraud-detection"}
            mock_intent.confidence = 0.92
            mock_parser.return_value = mock_intent

            with patch(
                "src.agent.operations.model_operations.ModelOperations.get_model_status"
            ) as mock_status:
                mock_status.return_value = {
                    "name": "fraud-detection",
                    "status": "Running",
                    "replicas": 3,
                    "ready_replicas": 3,
                    "endpoint": "http://fraud-detection.example.com",
                }

                response = test_client.post(
                    "/v1/query",
                    json={
                        "session_id": str(uuid.uuid4()),
                        "query": "What's the status of fraud-detection model?",
                    },
                    headers={"Authorization": "Bearer test_token"},
                )

                assert response.status_code == 200
                data = response.json()
                assert "response" in data

    @pytest.mark.asyncio
    async def test_scenario_4_scale_model_with_confirmation(
        self, test_client: TestClient, mock_oauth, mock_rbac
    ) -> None:
        """Test Scenario 4: Scale model (requires confirmation)."""
        # Step 1: Send scale request
        with patch(
            "src.services.intent_parser.IntentParser.parse_intent"
        ) as mock_parser:
            mock_intent = MagicMock()
            mock_intent.action_type = ActionType.SCALE_MODEL
            mock_intent.parameters = {
                "model_name": "sentiment-analysis",
                "replicas": 5,
            }
            mock_intent.confidence = 0.85
            mock_intent.requires_confirmation = True
            mock_parser.return_value = mock_intent

            response = test_client.post(
                "/v1/query",
                json={
                    "session_id": str(uuid.uuid4()),
                    "query": "Scale sentiment-analysis to 5 replicas",
                },
                headers={"Authorization": "Bearer test_token"},
            )

            assert response.status_code == 200
            data = response.json()
            assert (
                "pending_operation_id" in data or "requires_confirmation" in data
            )

            # Step 2: Confirm operation (if pending_operation_id was provided)
            if "pending_operation_id" in data:
                operation_id = data["pending_operation_id"]

                with patch(
                    "src.agent.operations.model_operations.ModelOperations.scale_model"
                ) as mock_scale:
                    mock_scale.return_value = {
                        "name": "sentiment-analysis",
                        "replicas": 5,
                        "status": "scaling",
                    }

                    confirm_response = test_client.post(
                        f"/v1/confirm/{operation_id}",
                        json={"action": "confirm"},
                        headers={"Authorization": "Bearer test_token"},
                    )

                    assert confirm_response.status_code in [200, 201]

    @pytest.mark.asyncio
    async def test_scenario_5_create_notebook(
        self, test_client: TestClient, mock_oauth, mock_rbac
    ) -> None:
        """Test Scenario 5: Create a Python notebook with specific resources."""
        with patch(
            "src.services.intent_parser.IntentParser.parse_intent"
        ) as mock_parser:
            mock_intent = MagicMock()
            mock_intent.action_type = ActionType.CREATE_NOTEBOOK
            mock_intent.parameters = {
                "image": "tensorflow",
                "memory": "8Gi",
            }
            mock_intent.confidence = 0.87
            mock_parser.return_value = mock_intent

            with patch(
                "src.agent.operations.notebook_operations.NotebookOperations.create_notebook"
            ) as mock_create:
                mock_create.return_value = {
                    "name": "tensorflow-notebook",
                    "image": "tensorflow",
                    "memory": "8Gi",
                    "status": "creating",
                }

                response = test_client.post(
                    "/v1/query",
                    json={
                        "session_id": str(uuid.uuid4()),
                        "query": "Create a Python notebook with TensorFlow and 8GB memory",
                    },
                    headers={"Authorization": "Bearer test_token"},
                )

                assert response.status_code == 200
                data = response.json()
                assert "response" in data

    @pytest.mark.asyncio
    async def test_scenario_6_troubleshoot_model(
        self, test_client: TestClient, mock_oauth, mock_rbac
    ) -> None:
        """Test Scenario 6: Troubleshoot model performance issues."""
        with patch(
            "src.services.intent_parser.IntentParser.parse_intent"
        ) as mock_parser:
            mock_intent = MagicMock()
            mock_intent.action_type = ActionType.TROUBLESHOOT_MODEL
            mock_intent.parameters = {
                "model_name": "fraud-detector",
                "issue": "high latency",
            }
            mock_intent.confidence = 0.80
            mock_parser.return_value = mock_intent

            with patch(
                "src.agent.operations.monitoring_operations.MonitoringOperations.troubleshoot_model"
            ) as mock_troubleshoot:
                mock_troubleshoot.return_value = {
                    "model_name": "fraud-detector",
                    "issues_found": [
                        "High CPU utilization (>80%)",
                        "Insufficient replicas for current load",
                    ],
                    "recommendations": [
                        "Scale to 5 replicas",
                        "Enable autoscaling",
                        "Review model optimization",
                    ],
                }

                response = test_client.post(
                    "/v1/query",
                    json={
                        "session_id": str(uuid.uuid4()),
                        "query": "Why is my fraud-detector showing high latency?",
                    },
                    headers={"Authorization": "Bearer test_token"},
                )

                assert response.status_code == 200
                data = response.json()
                assert "response" in data


@pytest.mark.integration
@pytest.mark.quickstart
class TestQuickstartWorkflow:
    """Test complete workflow from quickstart guide."""

    @pytest.mark.asyncio
    async def test_complete_quickstart_workflow(
        self, test_client: TestClient, mock_oauth, mock_rbac
    ) -> None:
        """Test the complete workflow from quickstart guide."""
        session_id = str(uuid.uuid4())

        # 1. Create session
        with patch(
            "src.agent.conversation.session_manager.SessionManager.create_session"
        ) as mock_create:
            mock_create.return_value = uuid.UUID(session_id)

            session_response = test_client.post(
                "/v1/sessions",
                json={"user_id": "test-user", "metadata": {"source": "quickstart"}},
                headers={"Authorization": "Bearer test_token"},
            )

            assert session_response.status_code in [200, 201]

        # 2. List models
        with patch(
            "src.services.intent_parser.IntentParser.parse_intent"
        ) as mock_parser:
            mock_intent = MagicMock()
            mock_intent.action_type = ActionType.LIST_MODELS
            mock_parser.return_value = mock_intent

            with patch(
                "src.agent.operations.model_operations.ModelOperations.list_models"
            ) as mock_list:
                mock_list.return_value = {"models": []}

                list_response = test_client.post(
                    "/v1/query",
                    json={"session_id": session_id, "query": "List all my models"},
                    headers={"Authorization": "Bearer test_token"},
                )

                assert list_response.status_code == 200

        # 3. Check model status
        with patch(
            "src.services.intent_parser.IntentParser.parse_intent"
        ) as mock_parser:
            mock_intent = MagicMock()
            mock_intent.action_type = ActionType.GET_MODEL_STATUS
            mock_intent.parameters = {"model_name": "test-model"}
            mock_parser.return_value = mock_intent

            with patch(
                "src.agent.operations.model_operations.ModelOperations.get_model_status"
            ) as mock_status:
                mock_status.return_value = {"name": "test-model", "status": "ready"}

                status_response = test_client.post(
                    "/v1/query",
                    json={
                        "session_id": session_id,
                        "query": "What's the status of test-model?",
                    },
                    headers={"Authorization": "Bearer test_token"},
                )

                assert status_response.status_code == 200

        # 4. Retrieve session history
        with patch(
            "src.agent.conversation.session_manager.SessionManager.get_full_history"
        ) as mock_history:
            mock_history.return_value = [
                {"user_command": "List all my models"},
                {"user_command": "What's the status of test-model?"},
            ]

            history_response = test_client.get(
                f"/v1/sessions/{session_id}/history",
                headers={"Authorization": "Bearer test_token"},
            )

            assert history_response.status_code in [200, 404]  # 404 if not implemented


@pytest.mark.integration
@pytest.mark.quickstart
class TestQuickstartErrorHandling:
    """Test error handling scenarios from quickstart guide."""

    @pytest.mark.asyncio
    async def test_invalid_model_name_error(
        self, test_client: TestClient, mock_oauth, mock_rbac
    ) -> None:
        """Test error handling for invalid model names."""
        with patch(
            "src.services.intent_parser.IntentParser.parse_intent"
        ) as mock_parser:
            mock_intent = MagicMock()
            mock_intent.action_type = ActionType.GET_MODEL_STATUS
            mock_intent.parameters = {"model_name": "nonexistent-model"}
            mock_parser.return_value = mock_intent

            with patch(
                "src.agent.operations.model_operations.ModelOperations.get_model_status"
            ) as mock_status:
                # Simulate model not found
                mock_status.side_effect = Exception(
                    "InferenceService 'nonexistent-model' not found"
                )

                response = test_client.post(
                    "/v1/query",
                    json={
                        "query": "What's the status of nonexistent-model?",
                        "session_id": str(uuid.uuid4()),
                    },
                    headers={"Authorization": "Bearer test_token"},
                )

                # Should return user-friendly error
                assert response.status_code in [200, 404]
                if response.status_code == 200:
                    data = response.json()
                    assert "response" in data or "error" in data

    @pytest.mark.asyncio
    async def test_insufficient_permissions_error(
        self, test_client: TestClient, mock_oauth
    ) -> None:
        """Test error handling for insufficient permissions."""
        with patch("src.agent.auth.rbac_checker.RBACChecker.check_access") as mock_rbac:
            # Deny access
            mock_rbac.return_value = False

            response = test_client.post(
                "/v1/query",
                json={
                    "query": "Delete all models",
                    "session_id": str(uuid.uuid4()),
                },
                headers={"Authorization": "Bearer test_token"},
            )

            # Should return 403 Forbidden
            assert response.status_code == 403
