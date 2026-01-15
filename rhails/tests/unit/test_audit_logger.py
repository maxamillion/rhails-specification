"""Unit tests for audit logging service."""

import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.services.audit_logger import AuditLogger


@pytest.fixture
def mock_db_session() -> AsyncSession:
    """Provide a mocked database session for testing."""
    session = MagicMock(spec=AsyncSession)
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.mark.unit
class TestOperationLogging:
    """Unit tests for operation logging."""

    @pytest.mark.asyncio
    async def test_log_operation_generates_uuid(
        self, mock_db_session: AsyncSession
    ) -> None:
        """Test that log_operation generates a valid UUID."""
        logger = AuditLogger(mock_db_session)
        session_id = uuid.uuid4()

        log_id = await logger.log_operation(
            user_id="test-user",
            session_id=session_id,
            user_command="Deploy my model",
            parsed_intent={"action": "deploy_model", "model_name": "fraud-detector"},
            openshift_operation="POST /apis/serving.kserve.io/v1beta1/namespaces/default/inferenceservices",
            operation_result={"status": "success"},
            duration_ms=1500,
        )

        assert isinstance(log_id, uuid.UUID)
        mock_db_session.execute.assert_called_once()
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_operation_with_all_fields(
        self, mock_db_session: AsyncSession
    ) -> None:
        """Test logging operation with all optional fields."""
        logger = AuditLogger(mock_db_session)
        session_id = uuid.uuid4()

        log_id = await logger.log_operation(
            user_id="test-user",
            session_id=session_id,
            user_command="Scale up my model",
            parsed_intent={"action": "scale_model", "replicas": 3},
            openshift_operation="PATCH /apis/serving.kserve.io/v1beta1/namespaces/default/inferenceservices/my-model",
            operation_result={"status": "success", "replicas": 3},
            duration_ms=2500,
            operation_error=None,
            ip_address="192.168.1.100",
            user_agent="Mozilla/5.0",
        )

        assert isinstance(log_id, uuid.UUID)
        mock_db_session.execute.assert_called_once()
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_log_operation_with_error(
        self, mock_db_session: AsyncSession
    ) -> None:
        """Test logging failed operation with error message."""
        logger = AuditLogger(mock_db_session)
        session_id = uuid.uuid4()

        log_id = await logger.log_operation(
            user_id="test-user",
            session_id=session_id,
            user_command="Delete nonexistent model",
            parsed_intent={"action": "delete_model", "model_name": "missing-model"},
            openshift_operation="DELETE /apis/serving.kserve.io/v1beta1/namespaces/default/inferenceservices/missing-model",
            operation_result={"status": "failed"},
            duration_ms=500,
            operation_error="Model 'missing-model' not found",
        )

        assert isinstance(log_id, uuid.UUID)
        mock_db_session.execute.assert_called_once()
        mock_db_session.commit.assert_called_once()


@pytest.mark.unit
class TestUserActivityRetrieval:
    """Unit tests for user activity retrieval."""

    @pytest.mark.asyncio
    async def test_get_user_activity_returns_entries(
        self, mock_db_session: AsyncSession
    ) -> None:
        """Test retrieving user activity returns audit entries."""
        logger = AuditLogger(mock_db_session)

        # Mock database response
        mock_entries = []
        for i in range(3):
            mock_entry = MagicMock()
            mock_entry.log_id = uuid.uuid4()
            mock_entry.timestamp = datetime.utcnow() - timedelta(hours=i)
            mock_entry.user_id = "test-user"
            mock_entry.session_id = uuid.uuid4()
            mock_entry.user_command = f"Command {i}"
            mock_entry.parsed_intent = {"action": f"action_{i}"}
            mock_entry.openshift_operation = f"GET /api/v1/operation{i}"
            mock_entry.operation_result = {"status": "success"}
            mock_entry.operation_error = None
            mock_entry.duration_ms = 1000 + (i * 100)
            mock_entries.append(mock_entry)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_entries
        mock_db_session.execute.return_value = mock_result

        activity = await logger.get_user_activity("test-user")

        assert len(activity) == 3
        assert all("log_id" in entry for entry in activity)
        assert all("user_command" in entry for entry in activity)
        assert all("duration_ms" in entry for entry in activity)

    @pytest.mark.asyncio
    async def test_get_user_activity_with_time_range(
        self, mock_db_session: AsyncSession
    ) -> None:
        """Test retrieving user activity with time range filter."""
        logger = AuditLogger(mock_db_session)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        start_time = datetime.utcnow() - timedelta(days=7)
        end_time = datetime.utcnow()

        await logger.get_user_activity(
            "test-user", start_time=start_time, end_time=end_time
        )

        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_user_activity_respects_limit(
        self, mock_db_session: AsyncSession
    ) -> None:
        """Test that user activity retrieval respects limit parameter."""
        logger = AuditLogger(mock_db_session)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        await logger.get_user_activity("test-user", limit=50)

        mock_db_session.execute.assert_called_once()


@pytest.mark.unit
class TestSessionAuditTrail:
    """Unit tests for session audit trail retrieval."""

    @pytest.mark.asyncio
    async def test_get_session_audit_trail_returns_entries(
        self, mock_db_session: AsyncSession
    ) -> None:
        """Test retrieving session audit trail returns entries in chronological order."""
        logger = AuditLogger(mock_db_session)
        session_id = uuid.uuid4()

        # Mock database response
        mock_entries = []
        for i in range(5):
            mock_entry = MagicMock()
            mock_entry.log_id = uuid.uuid4()
            mock_entry.timestamp = datetime.utcnow() + timedelta(minutes=i)
            mock_entry.user_command = f"Command {i}"
            mock_entry.openshift_operation = f"GET /api/v1/operation{i}"
            mock_entry.operation_result = {"status": "success"}
            mock_entry.operation_error = None
            mock_entry.duration_ms = 1000 + (i * 100)
            mock_entries.append(mock_entry)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_entries
        mock_db_session.execute.return_value = mock_result

        trail = await logger.get_session_audit_trail(session_id)

        assert len(trail) == 5
        assert all("log_id" in entry for entry in trail)
        assert all("user_command" in entry for entry in trail)
        # Should not include user_id in session trail
        assert all("user_id" not in entry for entry in trail)

    @pytest.mark.asyncio
    async def test_get_session_audit_trail_empty_session(
        self, mock_db_session: AsyncSession
    ) -> None:
        """Test retrieving audit trail for session with no entries."""
        logger = AuditLogger(mock_db_session)
        session_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        trail = await logger.get_session_audit_trail(session_id)

        assert len(trail) == 0
        assert isinstance(trail, list)


@pytest.mark.unit
class TestFailedOperations:
    """Unit tests for failed operations retrieval."""

    @pytest.mark.asyncio
    async def test_get_failed_operations_returns_only_failures(
        self, mock_db_session: AsyncSession
    ) -> None:
        """Test that get_failed_operations returns only failed operations."""
        logger = AuditLogger(mock_db_session)

        # Mock database response - all entries should have errors
        mock_entries = []
        for i in range(3):
            mock_entry = MagicMock()
            mock_entry.log_id = uuid.uuid4()
            mock_entry.timestamp = datetime.utcnow() - timedelta(hours=i)
            mock_entry.user_id = f"user-{i}"
            mock_entry.user_command = f"Failed command {i}"
            mock_entry.openshift_operation = f"POST /api/v1/operation{i}"
            mock_entry.operation_error = f"Error: operation failed {i}"
            mock_entry.duration_ms = 1000 + (i * 100)
            mock_entries.append(mock_entry)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_entries
        mock_db_session.execute.return_value = mock_result

        failures = await logger.get_failed_operations()

        assert len(failures) == 3
        assert all("operation_error" in entry for entry in failures)
        assert all(entry["operation_error"] is not None for entry in failures)

    @pytest.mark.asyncio
    async def test_get_failed_operations_with_time_range(
        self, mock_db_session: AsyncSession
    ) -> None:
        """Test retrieving failed operations with time range filter."""
        logger = AuditLogger(mock_db_session)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        start_time = datetime.utcnow() - timedelta(hours=24)
        end_time = datetime.utcnow()

        await logger.get_failed_operations(start_time=start_time, end_time=end_time)

        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_failed_operations_respects_limit(
        self, mock_db_session: AsyncSession
    ) -> None:
        """Test that failed operations retrieval respects limit parameter."""
        logger = AuditLogger(mock_db_session)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        await logger.get_failed_operations(limit=25)

        mock_db_session.execute.assert_called_once()


@pytest.mark.unit
class TestOperationStatistics:
    """Unit tests for operation statistics."""

    @pytest.mark.asyncio
    async def test_get_operation_statistics_calculates_correctly(
        self, mock_db_session: AsyncSession
    ) -> None:
        """Test that operation statistics are calculated correctly."""
        logger = AuditLogger(mock_db_session)

        # Mock total operations count
        total_result = MagicMock()
        total_result.scalar.return_value = 100

        # Mock failed operations count
        failed_result = MagicMock()
        failed_result.scalar.return_value = 10

        # Mock average duration
        avg_result = MagicMock()
        avg_result.scalar.return_value = 1500.5

        # Return different results for each query
        mock_db_session.execute.side_effect = [
            total_result,
            failed_result,
            avg_result,
        ]

        stats = await logger.get_operation_statistics()

        assert stats["total_operations"] == 100
        assert stats["successful_operations"] == 90
        assert stats["failed_operations"] == 10
        assert stats["success_rate_percent"] == 90.0
        assert stats["average_duration_ms"] == 1500.5

    @pytest.mark.asyncio
    async def test_get_operation_statistics_with_user_filter(
        self, mock_db_session: AsyncSession
    ) -> None:
        """Test operation statistics with user filter."""
        logger = AuditLogger(mock_db_session)

        # Mock results for user-specific query
        total_result = MagicMock()
        total_result.scalar.return_value = 50
        failed_result = MagicMock()
        failed_result.scalar.return_value = 5
        avg_result = MagicMock()
        avg_result.scalar.return_value = 1200.0

        mock_db_session.execute.side_effect = [
            total_result,
            failed_result,
            avg_result,
        ]

        stats = await logger.get_operation_statistics(user_id="test-user")

        assert stats["total_operations"] == 50
        assert stats["successful_operations"] == 45
        assert stats["success_rate_percent"] == 90.0

    @pytest.mark.asyncio
    async def test_get_operation_statistics_with_time_range(
        self, mock_db_session: AsyncSession
    ) -> None:
        """Test operation statistics with time range filter."""
        logger = AuditLogger(mock_db_session)

        total_result = MagicMock()
        total_result.scalar.return_value = 25
        failed_result = MagicMock()
        failed_result.scalar.return_value = 2
        avg_result = MagicMock()
        avg_result.scalar.return_value = 1800.0

        mock_db_session.execute.side_effect = [
            total_result,
            failed_result,
            avg_result,
        ]

        start_time = datetime.utcnow() - timedelta(days=7)
        end_time = datetime.utcnow()

        stats = await logger.get_operation_statistics(
            start_time=start_time, end_time=end_time
        )

        assert stats["total_operations"] == 25
        assert stats["success_rate_percent"] == 92.0

    @pytest.mark.asyncio
    async def test_get_operation_statistics_handles_zero_operations(
        self, mock_db_session: AsyncSession
    ) -> None:
        """Test that statistics handle zero operations correctly."""
        logger = AuditLogger(mock_db_session)

        total_result = MagicMock()
        total_result.scalar.return_value = 0
        failed_result = MagicMock()
        failed_result.scalar.return_value = 0
        avg_result = MagicMock()
        avg_result.scalar.return_value = 0

        mock_db_session.execute.side_effect = [
            total_result,
            failed_result,
            avg_result,
        ]

        stats = await logger.get_operation_statistics()

        assert stats["total_operations"] == 0
        assert stats["successful_operations"] == 0
        assert stats["failed_operations"] == 0
        assert stats["success_rate_percent"] == 0
        assert stats["average_duration_ms"] == 0

    @pytest.mark.asyncio
    async def test_get_operation_statistics_handles_all_failures(
        self, mock_db_session: AsyncSession
    ) -> None:
        """Test that statistics handle 100% failure rate correctly."""
        logger = AuditLogger(mock_db_session)

        total_result = MagicMock()
        total_result.scalar.return_value = 10
        failed_result = MagicMock()
        failed_result.scalar.return_value = 10
        avg_result = MagicMock()
        avg_result.scalar.return_value = 800.0

        mock_db_session.execute.side_effect = [
            total_result,
            failed_result,
            avg_result,
        ]

        stats = await logger.get_operation_statistics()

        assert stats["total_operations"] == 10
        assert stats["successful_operations"] == 0
        assert stats["failed_operations"] == 10
        assert stats["success_rate_percent"] == 0.0
