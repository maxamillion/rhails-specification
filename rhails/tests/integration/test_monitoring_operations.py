"""Integration tests for monitoring operation execution.

This module contains integration tests for the monitoring operation executor,
which handles log analysis, metrics comparison, performance diagnosis, and prediction distribution.
"""

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.operations.monitoring_operations import MonitoringOperationExecutor
from src.models.intent import OperationRequest
from src.models.openshift import ResourceType


@pytest.fixture
def mock_openshift_client() -> MagicMock:
    """Provide a mocked OpenShift client for testing."""
    client = MagicMock()

    # Mock get_model_logs
    client.get_model_logs = AsyncMock(
        return_value={
            "logs": [
                {"timestamp": "2024-01-15T10:30:00Z", "level": "ERROR", "message": "Connection timeout to database"},
                {"timestamp": "2024-01-15T10:31:00Z", "level": "ERROR", "message": "Failed to load model weights"},
                {"timestamp": "2024-01-15T10:32:00Z", "level": "WARN", "message": "High memory usage detected"},
            ],
            "error_count": 2,
            "warning_count": 1,
        }
    )

    # Mock get_model_metrics
    client.get_model_metrics = AsyncMock(
        return_value={
            "current": {
                "avg_latency_ms": 250,
                "requests_per_second": 45,
                "error_rate": 0.05,
                "cpu_usage_percent": 72,
                "memory_usage_mb": 1024,
            },
            "baseline": {
                "avg_latency_ms": 120,
                "requests_per_second": 50,
                "error_rate": 0.01,
                "cpu_usage_percent": 45,
                "memory_usage_mb": 896,
            },
        }
    )

    # Mock get_resource_metrics
    client.get_resource_metrics = AsyncMock(
        return_value={
            "cpu": {
                "current_usage_percent": 85,
                "average_usage_percent": 78,
                "limit_cores": 4,
            },
            "memory": {
                "current_usage_mb": 1536,
                "average_usage_mb": 1280,
                "limit_mb": 2048,
            },
            "bottleneck": "cpu",
        }
    )

    # Mock get_prediction_statistics
    client.get_prediction_statistics = AsyncMock(
        return_value={
            "total_predictions": 125000,
            "time_range": "last month",
            "distribution": {
                "positive": 62500,
                "negative": 37500,
                "neutral": 25000,
            },
            "distribution_percent": {
                "positive": 50.0,
                "negative": 30.0,
                "neutral": 20.0,
            },
        }
    )

    return client


@pytest.mark.integration
@pytest.mark.asyncio
class TestLogAnalysisOperation:
    """Integration tests for log analysis operations."""

    async def test_analyze_logs_success(
        self,
        async_db_session: AsyncSession,
        mock_openshift_client: MagicMock,
    ) -> None:
        """Test successful log analysis operation."""
        executor = MonitoringOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=async_db_session,
        )

        operation_request = OperationRequest(
            session_id=uuid.uuid4(),
            user_id="test-user",
            operation_type="get",
            target_resource=ResourceType.INFERENCE_SERVICE,
            resource_name="fraud-detector",
            parameters={"model_name": "fraud-detector", "action": "analyze_logs"},
            requires_confirmation=False,
        )

        result = await executor.execute(operation_request)

        # Verify OpenShift client was called
        mock_openshift_client.get_model_logs.assert_called_once()

        # Verify result
        assert result.status == "success"
        assert result.resource_name == "fraud-detector"
        assert result.resource_type == ResourceType.INFERENCE_SERVICE
        assert "error_count" in result.result_data


@pytest.mark.integration
@pytest.mark.asyncio
class TestMetricsComparisonOperation:
    """Integration tests for metrics comparison operations."""

    async def test_compare_metrics_success(
        self,
        async_db_session: AsyncSession,
        mock_openshift_client: MagicMock,
    ) -> None:
        """Test successful metrics comparison operation."""
        executor = MonitoringOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=async_db_session,
        )

        operation_request = OperationRequest(
            session_id=uuid.uuid4(),
            user_id="test-user",
            operation_type="get",
            target_resource=ResourceType.INFERENCE_SERVICE,
            resource_name="sentiment-model",
            parameters={
                "model_name": "sentiment-model",
                "time_range": "last week",
                "action": "compare_metrics",
            },
            requires_confirmation=False,
        )

        result = await executor.execute(operation_request)

        # Verify OpenShift client was called
        mock_openshift_client.get_model_metrics.assert_called_once()

        # Verify result
        assert result.status == "success"
        assert result.resource_name == "sentiment-model"
        assert "current" in result.result_data
        assert "baseline" in result.result_data


@pytest.mark.integration
@pytest.mark.asyncio
class TestPerformanceDiagnosisOperation:
    """Integration tests for performance diagnosis operations."""

    async def test_diagnose_performance_success(
        self,
        async_db_session: AsyncSession,
        mock_openshift_client: MagicMock,
    ) -> None:
        """Test successful performance diagnosis operation."""
        executor = MonitoringOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=async_db_session,
        )

        operation_request = OperationRequest(
            session_id=uuid.uuid4(),
            user_id="test-user",
            operation_type="get",
            target_resource=ResourceType.INFERENCE_SERVICE,
            resource_name="recommendation-engine",
            parameters={"model_name": "recommendation-engine", "action": "diagnose_performance"},
            requires_confirmation=False,
        )

        result = await executor.execute(operation_request)

        # Verify OpenShift client was called
        mock_openshift_client.get_resource_metrics.assert_called_once()

        # Verify result
        assert result.status == "success"
        assert result.resource_name == "recommendation-engine"
        assert "bottleneck" in result.result_data


@pytest.mark.integration
@pytest.mark.asyncio
class TestPredictionDistributionOperation:
    """Integration tests for prediction distribution operations."""

    async def test_get_prediction_distribution_success(
        self,
        async_db_session: AsyncSession,
        mock_openshift_client: MagicMock,
    ) -> None:
        """Test successful prediction distribution retrieval."""
        executor = MonitoringOperationExecutor(
            openshift_client=mock_openshift_client,
            db_session=async_db_session,
        )

        operation_request = OperationRequest(
            session_id=uuid.uuid4(),
            user_id="test-user",
            operation_type="get",
            target_resource=ResourceType.INFERENCE_SERVICE,
            resource_name="customer-churn",
            parameters={
                "model_name": "customer-churn",
                "time_range": "last month",
                "action": "get_prediction_distribution",
            },
            requires_confirmation=False,
        )

        result = await executor.execute(operation_request)

        # Verify OpenShift client was called
        mock_openshift_client.get_prediction_statistics.assert_called_once()

        # Verify result
        assert result.status == "success"
        assert result.resource_name == "customer-churn"
        assert "distribution" in result.result_data
        assert "total_predictions" in result.result_data
