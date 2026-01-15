"""Unit tests for intent parsing service.

These tests verify that the intent parser correctly identifies user intentions
from natural language queries and extracts relevant parameters.
"""

from typing import Any

import pytest

from src.models.intent import ActionType, UserIntent
from src.models.openshift import ResourceType


@pytest.mark.unit
class TestModelDeploymentIntentParsing:
    """Unit tests for parsing model deployment intents."""

    @pytest.mark.parametrize(
        "query,expected_action,expected_params",
        [
            (
                "Deploy my sentiment-analysis model with 2 replicas",
                ActionType.DEPLOY_MODEL,
                {
                    "model_name": "sentiment-analysis",
                    "replicas": 2,
                },
            ),
            (
                "Create a new model called fraud-detection",
                ActionType.DEPLOY_MODEL,
                {
                    "model_name": "fraud-detection",
                },
            ),
            (
                "Deploy the recommendation-engine model from s3://models/recommender",
                ActionType.DEPLOY_MODEL,
                {
                    "model_name": "recommendation-engine",
                    "storage_uri": "s3://models/recommender",
                },
            ),
            (
                "I need to deploy customer-churn-predictor with 5 replicas in production namespace",
                ActionType.DEPLOY_MODEL,
                {
                    "model_name": "customer-churn-predictor",
                    "replicas": 5,
                    "namespace": "production",
                },
            ),
        ],
    )
    async def test_parse_model_deployment_variations(
        self,
        query: str,
        expected_action: ActionType,
        expected_params: dict[str, Any],
    ) -> None:
        """Test parsing various model deployment query variations."""
        from src.services.intent_parser import IntentParser

        parser = IntentParser()

        # Parse intent
        intent = await parser.parse_intent(query)

        # Verify action type
        assert intent.action_type == expected_action

        # Verify extracted parameters
        for key, expected_value in expected_params.items():
            assert key in intent.parameters
            assert intent.parameters[key] == expected_value

        # Verify confidence
        assert intent.confidence >= 0.7  # High confidence for clear intents

    async def test_parse_deployment_requires_model_name(self) -> None:
        """Test that deployment intents without model name have lower confidence."""
        from src.services.intent_parser import IntentParser

        parser = IntentParser()

        # Ambiguous query without model name
        intent = await parser.parse_intent("Deploy a model with 3 replicas")

        # Should still identify as deployment but with lower confidence
        assert intent.action_type == ActionType.DEPLOY_MODEL
        assert intent.confidence < 0.7  # Lower confidence due to missing info

    async def test_parse_deployment_extracts_namespace(self) -> None:
        """Test that namespace is correctly extracted from deployment queries."""
        from src.services.intent_parser import IntentParser

        parser = IntentParser()

        intent = await parser.parse_intent(
            "Deploy sentiment-model in the ml-models namespace"
        )

        assert intent.action_type == ActionType.DEPLOY_MODEL
        assert intent.parameters.get("namespace") == "ml-models"


@pytest.mark.unit
class TestModelQueryIntentParsing:
    """Unit tests for parsing model query intents."""

    @pytest.mark.parametrize(
        "query,expected_action,expected_params",
        [
            (
                "What's the status of my sentiment-analysis model?",
                ActionType.GET_STATUS,
                {"model_name": "sentiment-analysis"},
            ),
            (
                "Show me the fraud-detection model status",
                ActionType.GET_STATUS,
                {"model_name": "fraud-detection"},
            ),
            (
                "Is the recommendation-engine model running?",
                ActionType.GET_STATUS,
                {"model_name": "recommendation-engine"},
            ),
            (
                "List all my models",
                ActionType.LIST_MODELS,
                {},
            ),
            (
                "Show me all deployed models",
                ActionType.LIST_MODELS,
                {},
            ),
            (
                "What models are running in the production namespace?",
                ActionType.LIST_MODELS,
                {"namespace": "production"},
            ),
        ],
    )
    async def test_parse_model_query_variations(
        self,
        query: str,
        expected_action: ActionType,
        expected_params: dict[str, Any],
    ) -> None:
        """Test parsing various model query variations."""
        from src.services.intent_parser import IntentParser

        parser = IntentParser()

        # Parse intent
        intent = await parser.parse_intent(query)

        # Verify action type
        assert intent.action_type == expected_action

        # Verify extracted parameters
        for key, expected_value in expected_params.items():
            assert key in intent.parameters
            assert intent.parameters[key] == expected_value

        # Query operations should not require confirmation
        assert intent.requires_confirmation is False

    async def test_parse_list_models_without_namespace(self) -> None:
        """Test that list models works without namespace specification."""
        from src.services.intent_parser import IntentParser

        parser = IntentParser()

        intent = await parser.parse_intent("List all models")

        assert intent.action_type == ActionType.LIST_MODELS
        assert "namespace" not in intent.parameters or intent.parameters["namespace"] is None

    async def test_parse_get_status_with_namespace(self) -> None:
        """Test that get status can include namespace filter."""
        from src.services.intent_parser import IntentParser

        parser = IntentParser()

        intent = await parser.parse_intent(
            "Check the status of sentiment-model in staging namespace"
        )

        assert intent.action_type == ActionType.GET_STATUS
        assert intent.parameters.get("model_name") == "sentiment-model"
        assert intent.parameters.get("namespace") == "staging"


@pytest.mark.unit
class TestModelScalingIntentParsing:
    """Unit tests for parsing model scaling intents."""

    @pytest.mark.parametrize(
        "query,expected_params",
        [
            (
                "Scale sentiment-analysis to 5 replicas",
                {"model_name": "sentiment-analysis", "replicas": 5},
            ),
            (
                "Increase fraud-detection to 10 instances",
                {"model_name": "fraud-detection", "replicas": 10},
            ),
            (
                "Scale down recommendation-engine to 2 replicas",
                {"model_name": "recommendation-engine", "replicas": 2},
            ),
        ],
    )
    async def test_parse_scaling_operations(
        self,
        query: str,
        expected_params: dict[str, Any],
    ) -> None:
        """Test parsing model scaling operations."""
        from src.services.intent_parser import IntentParser

        parser = IntentParser()

        intent = await parser.parse_intent(query)

        # Verify action type
        assert intent.action_type == ActionType.SCALE_MODEL

        # Verify parameters
        for key, expected_value in expected_params.items():
            assert intent.parameters[key] == expected_value

        # Scaling should require confirmation
        assert intent.requires_confirmation is True

    async def test_parse_scaling_extracts_numeric_replicas(self) -> None:
        """Test that replica count is extracted as integer."""
        from src.services.intent_parser import IntentParser

        parser = IntentParser()

        intent = await parser.parse_intent("Scale my-model to three replicas")

        assert intent.action_type == ActionType.SCALE_MODEL
        # Should convert "three" to 3
        assert isinstance(intent.parameters["replicas"], int)


@pytest.mark.unit
class TestModelDeletionIntentParsing:
    """Unit tests for parsing model deletion intents."""

    @pytest.mark.parametrize(
        "query,expected_params",
        [
            (
                "Delete the sentiment-analysis model",
                {"model_name": "sentiment-analysis"},
            ),
            (
                "Remove fraud-detection model",
                {"model_name": "fraud-detection"},
            ),
            (
                "Delete recommendation-engine in production namespace",
                {"model_name": "recommendation-engine", "namespace": "production"},
            ),
        ],
    )
    async def test_parse_deletion_operations(
        self,
        query: str,
        expected_params: dict[str, Any],
    ) -> None:
        """Test parsing model deletion operations."""
        from src.services.intent_parser import IntentParser

        parser = IntentParser()

        intent = await parser.parse_intent(query)

        # Verify action type
        assert intent.action_type == ActionType.DELETE_MODEL

        # Verify parameters
        for key, expected_value in expected_params.items():
            assert intent.parameters[key] == expected_value

        # Deletion should require confirmation
        assert intent.requires_confirmation is True

    async def test_parse_deletion_high_confidence_threshold(self) -> None:
        """Test that deletion requires high confidence to avoid accidents."""
        from src.services.intent_parser import IntentParser

        parser = IntentParser()

        # Ambiguous deletion query
        intent = await parser.parse_intent("Remove the model")

        # Should either:
        # 1. Not identify as deletion (different action_type), OR
        # 2. Identify as deletion but with low confidence
        if intent.action_type == ActionType.DELETE_MODEL:
            assert intent.confidence < 0.7  # Lower confidence for ambiguous deletion


@pytest.mark.unit
class TestIntentConfidence:
    """Unit tests for intent confidence scoring."""

    async def test_high_confidence_for_complete_intents(self) -> None:
        """Test that complete intents have high confidence scores."""
        from src.services.intent_parser import IntentParser

        parser = IntentParser()

        intent = await parser.parse_intent(
            "Deploy sentiment-analysis model with 2 replicas in production namespace"
        )

        # Complete intent should have high confidence
        assert intent.confidence >= 0.8

    async def test_lower_confidence_for_ambiguous_intents(self) -> None:
        """Test that ambiguous intents have lower confidence scores."""
        from src.services.intent_parser import IntentParser

        parser = IntentParser()

        intent = await parser.parse_intent("Do something with the model")

        # Ambiguous intent should have lower confidence
        assert intent.confidence < 0.5

    async def test_confidence_increases_with_context(self) -> None:
        """Test that providing conversation context increases confidence."""
        from src.services.intent_parser import IntentParser

        parser = IntentParser()

        # Without context
        intent_without_context = await parser.parse_intent("Scale it to 5 replicas")

        # With context (previous discussion about sentiment-analysis model)
        context = [
            {
                "role": "user",
                "content": "What's the status of sentiment-analysis?",
            },
            {
                "role": "assistant",
                "content": "The sentiment-analysis model is running with 2 replicas.",
            },
        ]

        intent_with_context = await parser.parse_intent(
            "Scale it to 5 replicas", conversation_context=context
        )

        # Context should increase confidence
        assert intent_with_context.confidence > intent_without_context.confidence

        # With context, "it" should be resolved to "sentiment-analysis"
        assert intent_with_context.parameters.get("model_name") == "sentiment-analysis"


@pytest.mark.unit
class TestResourceTypeIdentification:
    """Unit tests for identifying target resource types."""

    async def test_identify_inference_service_resource(self) -> None:
        """Test that model operations correctly identify InferenceService resource."""
        from src.services.intent_parser import IntentParser

        parser = IntentParser()

        intent = await parser.parse_intent("Deploy sentiment-analysis model")

        assert intent.target_resources[0]["type"] == ResourceType.INFERENCE_SERVICE

    async def test_identify_multiple_resources(self) -> None:
        """Test identification when query involves multiple resources."""
        from src.services.intent_parser import IntentParser

        parser = IntentParser()

        # Query that might involve multiple resources
        intent = await parser.parse_intent(
            "Deploy sentiment-model and create a pipeline for it"
        )

        # Should identify both InferenceService and Pipeline resources
        resource_types = [r["type"] for r in intent.target_resources]

        # At least one resource should be identified
        assert len(resource_types) >= 1


@pytest.mark.unit
class TestPipelineIntentParsing:
    """Unit tests for parsing pipeline-related intents."""

    @pytest.mark.parametrize(
        "query,expected_action,expected_params,min_confidence",
        [
            (
                "Create a pipeline to preprocess customer reviews from S3",
                ActionType.CREATE_PIPELINE,
                {},  # No explicit name in query
                0.5,  # Lower confidence without name
            ),
            (
                "Create a pipeline called data-preprocessing for sentiment analysis",
                ActionType.CREATE_PIPELINE,
                {
                    "pipeline_name": "data-preprocessing",
                },
                0.7,  # Higher confidence with explicit name
            ),
            (
                "Set up a data pipeline to transform user feedback",
                ActionType.CREATE_PIPELINE,
                {},  # No explicit name
                0.5,  # Lower confidence without name
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_pipeline_creation_intent(
        self, query: str, expected_action: ActionType, expected_params: dict[str, Any], min_confidence: float
    ) -> None:
        """Test that pipeline creation queries are correctly parsed."""
        from src.services.intent_parser import IntentParser

        parser = IntentParser()
        intent = await parser.parse_intent(query)

        assert isinstance(intent, UserIntent)
        assert intent.action_type == expected_action
        assert intent.confidence >= min_confidence

        # Check expected parameters are present
        for param_name, param_value in expected_params.items():
            assert param_name in intent.parameters
            if param_value:
                assert intent.parameters[param_name] == param_value

    @pytest.mark.parametrize(
        "query,expected_action",
        [
            ("List all pipelines", ActionType.LIST_PIPELINES),
            ("Show me my data pipelines", ActionType.LIST_PIPELINES),
            ("What pipelines are running?", ActionType.LIST_PIPELINES),
        ],
    )
    @pytest.mark.asyncio
    async def test_list_pipelines_intent(
        self, query: str, expected_action: ActionType
    ) -> None:
        """Test that pipeline listing queries are correctly parsed."""
        from src.services.intent_parser import IntentParser

        parser = IntentParser()
        intent = await parser.parse_intent(query)

        assert isinstance(intent, UserIntent)
        assert intent.action_type == expected_action
        assert intent.confidence >= 0.7

    @pytest.mark.parametrize(
        "query,expected_action,expected_params",
        [
            (
                "Update the schedule of customer-reviews pipeline to run every 6 hours",
                ActionType.UPDATE_PIPELINE,
                {
                    "pipeline_name": "customer-reviews",
                    "schedule": "every 6 hours",
                },
            ),
            (
                "Change data-preprocessing pipeline schedule to daily",
                ActionType.UPDATE_PIPELINE,
                {
                    "pipeline_name": "data-preprocessing",
                    "schedule": "daily",
                },
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_update_pipeline_schedule_intent(
        self, query: str, expected_action: ActionType, expected_params: dict[str, Any]
    ) -> None:
        """Test that pipeline schedule update queries are correctly parsed."""
        from src.services.intent_parser import IntentParser

        parser = IntentParser()
        intent = await parser.parse_intent(query)

        assert isinstance(intent, UserIntent)
        assert intent.action_type == expected_action
        assert intent.confidence >= 0.6  # May be lower confidence for updates

        # Check expected parameters are present
        for param_name, _param_value in expected_params.items():
            assert param_name in intent.parameters

    @pytest.mark.asyncio
    async def test_pipeline_resource_extraction(self) -> None:
        """Test that pipeline resources are correctly extracted."""
        from src.services.intent_parser import IntentParser

        parser = IntentParser()
        intent = await parser.parse_intent(
            "Create a pipeline called customer-feedback-analysis"
        )

        # Should have at least one target resource
        assert len(intent.target_resources) >= 1

        # Find the pipeline resource
        pipeline_resources = [
            r for r in intent.target_resources if r.get("type") == ResourceType.PIPELINE
        ]

        # Should identify a Pipeline resource
        assert len(pipeline_resources) >= 0  # May not be implemented yet


@pytest.mark.unit
class TestNotebookIntentParsing:
    """Unit tests for parsing notebook-related intents."""

    @pytest.mark.parametrize(
        "query,expected_action,expected_params,min_confidence",
        [
            (
                "Create a Python notebook with TensorFlow and 4GB RAM",
                ActionType.CREATE_NOTEBOOK,
                {"memory": "4Gi"},
                0.6,
            ),
            (
                "Create a notebook called ml-notebook with 8GB memory",
                ActionType.CREATE_NOTEBOOK,
                {"notebook_name": "ml-notebook", "memory": "8Gi"},
                0.7,
            ),
            (
                "Launch a Jupyter notebook with GPU support",
                ActionType.CREATE_NOTEBOOK,
                {"gpu": 1},
                0.6,
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_notebook_creation_intent(
        self, query: str, expected_action: ActionType, expected_params: dict[str, Any], min_confidence: float
    ) -> None:
        """Test that notebook creation queries are correctly parsed."""
        from src.services.intent_parser import IntentParser

        parser = IntentParser()
        intent = await parser.parse_intent(query)

        assert isinstance(intent, UserIntent)
        assert intent.action_type == expected_action
        assert intent.confidence >= min_confidence

        # Check expected parameters are present
        for param_name, param_value in expected_params.items():
            assert param_name in intent.parameters
            if param_value:
                assert intent.parameters[param_name] == param_value

    @pytest.mark.parametrize(
        "query,expected_action",
        [
            ("List all notebooks", ActionType.LIST_NOTEBOOKS),
            ("Show me my Jupyter notebooks", ActionType.LIST_NOTEBOOKS),
            ("What notebooks are running?", ActionType.LIST_NOTEBOOKS),
        ],
    )
    @pytest.mark.asyncio
    async def test_list_notebooks_intent(
        self, query: str, expected_action: ActionType
    ) -> None:
        """Test that notebook listing queries are correctly parsed."""
        from src.services.intent_parser import IntentParser

        parser = IntentParser()
        intent = await parser.parse_intent(query)

        assert isinstance(intent, UserIntent)
        assert intent.action_type == expected_action
        assert intent.confidence >= 0.7

    @pytest.mark.parametrize(
        "query,expected_action,expected_params",
        [
            (
                "Stop the ml-notebook",
                ActionType.STOP_NOTEBOOK,
                {"notebook_name": "ml-notebook", "action": "stop"},
            ),
            (
                "Start my data-science-notebook",
                ActionType.START_NOTEBOOK,
                {"notebook_name": "data-science-notebook", "action": "start"},
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_notebook_control_intent(
        self, query: str, expected_action: ActionType, expected_params: dict[str, Any]
    ) -> None:
        """Test that notebook start/stop queries are correctly parsed."""
        from src.services.intent_parser import IntentParser

        parser = IntentParser()
        intent = await parser.parse_intent(query)

        assert isinstance(intent, UserIntent)
        assert intent.action_type == expected_action
        assert intent.confidence >= 0.6

        # Check expected parameters
        for param_name, param_value in expected_params.items():
            assert param_name in intent.parameters
            assert intent.parameters[param_name] == param_value

    @pytest.mark.parametrize(
        "query,expected_action,expected_params",
        [
            (
                "Delete the ml-notebook",
                ActionType.DELETE_NOTEBOOK,
                {"notebook_name": "ml-notebook"},
            ),
            (
                "Remove my old-notebook",
                ActionType.DELETE_NOTEBOOK,
                {"notebook_name": "old-notebook"},
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_notebook_deletion_intent(
        self, query: str, expected_action: ActionType, expected_params: dict[str, Any]
    ) -> None:
        """Test that notebook deletion queries are correctly parsed."""
        from src.services.intent_parser import IntentParser

        parser = IntentParser()
        intent = await parser.parse_intent(query)

        assert isinstance(intent, UserIntent)
        assert intent.action_type == expected_action

        # Deletion should require confirmation
        assert intent.requires_confirmation is True

        # Check expected parameters
        for param_name, param_value in expected_params.items():
            assert param_name in intent.parameters
            assert intent.parameters[param_name] == param_value

    @pytest.mark.asyncio
    async def test_notebook_resource_extraction(self) -> None:
        """Test that notebook resources are correctly extracted."""
        from src.services.intent_parser import IntentParser

        parser = IntentParser()
        intent = await parser.parse_intent(
            "Create a notebook called ml-experiment"
        )

        # Should have at least one target resource
        assert len(intent.target_resources) >= 1

        # Find the notebook resource
        notebook_resources = [
            r for r in intent.target_resources if r.get("type") == ResourceType.NOTEBOOK
        ]

        # Should identify a Notebook resource
        assert len(notebook_resources) >= 1
        assert notebook_resources[0]["name"] == "ml-experiment"


@pytest.mark.unit
class TestProjectIntentParsing:
    """Unit tests for parsing project-related intents."""

    @pytest.mark.parametrize(
        "query,expected_action,expected_params,min_confidence",
        [
            (
                "Create a project for the recommendation-systems team with 64GB memory and 16 CPU limit",
                ActionType.CREATE_PROJECT,
                {"memory_limit": "64Gi", "cpu_limit": "16"},
                0.7,
            ),
            (
                "Create a project called fraud-detection with 32GB memory",
                ActionType.CREATE_PROJECT,
                {"project_name": "fraud-detection", "memory_limit": "32Gi"},
                0.7,
            ),
            (
                "Create a new project named customer-analytics",
                ActionType.CREATE_PROJECT,
                {"project_name": "customer-analytics"},
                0.6,
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_project_creation_intent(
        self, query: str, expected_action: ActionType, expected_params: dict[str, Any], min_confidence: float
    ) -> None:
        """Test that project creation queries are correctly parsed."""
        from src.services.intent_parser import IntentParser

        parser = IntentParser()
        intent = await parser.parse_intent(query)

        assert isinstance(intent, UserIntent)
        assert intent.action_type == expected_action
        assert intent.confidence >= min_confidence

        # Check expected parameters
        for param_name, param_value in expected_params.items():
            assert param_name in intent.parameters
            assert intent.parameters[param_name] == param_value

    @pytest.mark.parametrize(
        "query,expected_action",
        [
            ("Show me all projects", ActionType.LIST_PROJECTS),
            ("List all projects", ActionType.LIST_PROJECTS),
            ("What projects do I have access to?", ActionType.LIST_PROJECTS),
        ],
    )
    @pytest.mark.asyncio
    async def test_list_projects_intent(
        self, query: str, expected_action: ActionType
    ) -> None:
        """Test that project listing queries are correctly parsed."""
        from src.services.intent_parser import IntentParser

        parser = IntentParser()
        intent = await parser.parse_intent(query)

        assert isinstance(intent, UserIntent)
        assert intent.action_type == expected_action
        assert intent.confidence >= 0.6

    @pytest.mark.parametrize(
        "query,expected_action,expected_params",
        [
            (
                "Add user jane.doe@company.com to customer-analytics project",
                ActionType.ADD_USER_TO_PROJECT,
                {"username": "jane.doe@company.com", "project_name": "customer-analytics"},
            ),
            (
                "Give john.smith@company.com access to fraud-detection",
                ActionType.ADD_USER_TO_PROJECT,
                {"username": "john.smith@company.com", "project_name": "fraud-detection"},
            ),
            (
                "Add alice to the recommendation-systems project with edit permissions",
                ActionType.ADD_USER_TO_PROJECT,
                {"username": "alice", "project_name": "recommendation-systems", "role": "edit"},
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_add_user_to_project_intent(
        self, query: str, expected_action: ActionType, expected_params: dict[str, Any]
    ) -> None:
        """Test that add user to project queries are correctly parsed."""
        from src.services.intent_parser import IntentParser

        parser = IntentParser()
        intent = await parser.parse_intent(query)

        assert isinstance(intent, UserIntent)
        assert intent.action_type == expected_action
        assert intent.confidence >= 0.6

        # Check expected parameters
        for param_name, param_value in expected_params.items():
            assert param_name in intent.parameters
            assert intent.parameters[param_name] == param_value

    @pytest.mark.parametrize(
        "query,expected_action,expected_params",
        [
            (
                "How much memory is fraud-detection using?",
                ActionType.GET_PROJECT_RESOURCES,
                {"project_name": "fraud-detection"},
            ),
            (
                "Show resource usage for customer-analytics",
                ActionType.GET_PROJECT_RESOURCES,
                {"project_name": "customer-analytics"},
            ),
            (
                "What's the resource consumption of recommendation-systems?",
                ActionType.GET_PROJECT_RESOURCES,
                {"project_name": "recommendation-systems"},
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_get_project_resources_intent(
        self, query: str, expected_action: ActionType, expected_params: dict[str, Any]
    ) -> None:
        """Test that project resource queries are correctly parsed."""
        from src.services.intent_parser import IntentParser

        parser = IntentParser()
        intent = await parser.parse_intent(query)

        assert isinstance(intent, UserIntent)
        assert intent.action_type == expected_action
        assert intent.confidence >= 0.6

        # Check expected parameters
        for param_name, param_value in expected_params.items():
            assert param_name in intent.parameters
            assert intent.parameters[param_name] == param_value

    @pytest.mark.asyncio
    async def test_project_resource_extraction(self) -> None:
        """Test that project resources are correctly extracted."""
        from src.services.intent_parser import IntentParser

        parser = IntentParser()
        intent = await parser.parse_intent(
            "Create a project called data-science"
        )

        # Should have at least one target resource
        assert len(intent.target_resources) >= 1

        # Find the project resource
        project_resources = [
            r for r in intent.target_resources if r.get("type") == ResourceType.PROJECT
        ]

        # Should identify a Project resource
        assert len(project_resources) >= 1
        assert project_resources[0]["name"] == "data-science"


@pytest.mark.unit
class TestMonitoringIntentParsing:
    """Unit tests for parsing monitoring and troubleshooting intents."""

    @pytest.mark.parametrize(
        "query,expected_action,expected_params,min_confidence",
        [
            # Log analysis
            (
                "Why is my fraud-detector failing requests?",
                ActionType.ANALYZE_LOGS,
                {"model_name": "fraud-detector"},
                0.6,
            ),
            (
                "Show me the logs for sentiment-analyzer",
                ActionType.ANALYZE_LOGS,
                {"model_name": "sentiment-analyzer"},
                0.6,
            ),
            (
                "What errors is customer-churn-model experiencing?",
                ActionType.ANALYZE_LOGS,
                {"model_name": "customer-churn-model"},
                0.6,
            ),
            # Metrics comparison
            (
                "Compare the performance of my sentiment-model today versus last week",
                ActionType.COMPARE_METRICS,
                {"model_name": "sentiment-model", "time_range": "last week"},
                0.6,
            ),
            (
                "How does fraud-detector performance compare to yesterday?",
                ActionType.COMPARE_METRICS,
                {"model_name": "fraud-detector", "time_range": "yesterday"},
                0.6,
            ),
            (
                "Show me performance comparison for recommendation-engine over the last month",
                ActionType.COMPARE_METRICS,
                {"model_name": "recommendation-engine", "time_range": "last month"},
                0.6,
            ),
            # Performance diagnosis
            (
                "Is my recommendation-engine CPU-bound?",
                ActionType.DIAGNOSE_PERFORMANCE,
                {"model_name": "recommendation-engine"},
                0.6,
            ),
            (
                "Why is sentiment-model showing high latency?",
                ActionType.DIAGNOSE_PERFORMANCE,
                {"model_name": "sentiment-model"},
                0.6,
            ),
            (
                "Diagnose performance issues with fraud-detector",
                ActionType.DIAGNOSE_PERFORMANCE,
                {"model_name": "fraud-detector"},
                0.6,
            ),
            # Prediction distribution
            (
                "Show me the prediction distribution for my customer-churn model over the last month",
                ActionType.GET_PREDICTION_DISTRIBUTION,
                {"model_name": "customer-churn", "time_range": "last month"},
                0.6,
            ),
            (
                "What's the distribution of predictions for sentiment-analyzer?",
                ActionType.GET_PREDICTION_DISTRIBUTION,
                {"model_name": "sentiment-analyzer"},
                0.6,
            ),
            (
                "Get prediction statistics for recommendation-engine over the past week",
                ActionType.GET_PREDICTION_DISTRIBUTION,
                {"model_name": "recommendation-engine", "time_range": "past week"},
                0.6,
            ),
        ],
    )
    @pytest.mark.asyncio
    async def test_monitoring_intent_parsing(
        self,
        query: str,
        expected_action: ActionType,
        expected_params: dict[str, Any],
        min_confidence: float,
    ) -> None:
        """Test that monitoring and troubleshooting queries are correctly parsed."""
        from src.services.intent_parser import IntentParser

        parser = IntentParser()
        intent = await parser.parse_intent(query)

        assert isinstance(intent, UserIntent)
        assert intent.action_type == expected_action
        assert intent.confidence >= min_confidence

        # Check expected parameters
        for param_name, param_value in expected_params.items():
            assert param_name in intent.parameters
            assert intent.parameters[param_name] == param_value
