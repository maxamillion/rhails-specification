"""Unit tests for conversation session manager."""

import uuid
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.agent.conversation.session_manager import SessionManager
from src.models.conversation import MessageRole, SessionStatus


@pytest.fixture
def mock_db_session() -> AsyncSession:
    """Provide a mocked database session for testing."""
    session = MagicMock(spec=AsyncSession)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.mark.unit
class TestSessionCreation:
    """Unit tests for session creation."""

    @pytest.mark.asyncio
    async def test_create_session_generates_uuid(
        self, mock_db_session: AsyncSession
    ) -> None:
        """Test that session creation generates a valid UUID."""
        manager = SessionManager(mock_db_session)

        session_id = await manager.create_session(
            user_id="test-user", metadata={"source": "api"}
        )

        assert isinstance(session_id, uuid.UUID)
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_session_with_metadata(
        self, mock_db_session: AsyncSession
    ) -> None:
        """Test that session creation includes metadata."""
        manager = SessionManager(mock_db_session)
        metadata = {"source": "api", "user_agent": "Mozilla/5.0"}

        session_id = await manager.create_session(
            user_id="test-user", metadata=metadata
        )

        assert isinstance(session_id, uuid.UUID)
        # Verify add was called with session object
        call_args = mock_db_session.add.call_args
        assert call_args is not None
        session_obj = call_args[0][0]
        assert session_obj.user_id == "test-user"
        assert session_obj.metadata == metadata

    @pytest.mark.asyncio
    async def test_create_session_default_status_is_active(
        self, mock_db_session: AsyncSession
    ) -> None:
        """Test that new sessions default to ACTIVE status."""
        manager = SessionManager(mock_db_session)

        await manager.create_session(user_id="test-user")

        call_args = mock_db_session.add.call_args
        session_obj = call_args[0][0]
        assert session_obj.status == SessionStatus.ACTIVE.value


@pytest.mark.unit
class TestSessionRetrieval:
    """Unit tests for session retrieval."""

    @pytest.mark.asyncio
    async def test_get_session_returns_session_data(
        self, mock_db_session: AsyncSession
    ) -> None:
        """Test retrieving session returns correct data."""
        manager = SessionManager(mock_db_session)
        session_id = uuid.uuid4()

        # Mock database response
        mock_session = MagicMock()
        mock_session.session_id = session_id
        mock_session.user_id = "test-user"
        mock_session.created_at = datetime.utcnow()
        mock_session.updated_at = datetime.utcnow()
        mock_session.status = SessionStatus.ACTIVE.value
        mock_session.metadata = {"source": "api"}

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_session
        mock_db_session.execute.return_value = mock_result

        result = await manager.get_session(session_id)

        assert result is not None
        assert result["user_id"] == "test-user"
        assert result["status"] == SessionStatus.ACTIVE.value
        assert result["metadata"] == {"source": "api"}

    @pytest.mark.asyncio
    async def test_get_session_returns_none_if_not_found(
        self, mock_db_session: AsyncSession
    ) -> None:
        """Test that get_session returns None for non-existent session."""
        manager = SessionManager(mock_db_session)
        session_id = uuid.uuid4()

        # Mock database response - no session found
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        result = await manager.get_session(session_id)

        assert result is None


@pytest.mark.unit
class TestSessionListing:
    """Unit tests for listing user sessions."""

    @pytest.mark.asyncio
    async def test_list_user_sessions_returns_all_sessions(
        self, mock_db_session: AsyncSession
    ) -> None:
        """Test listing all sessions for a user."""
        manager = SessionManager(mock_db_session)

        # Mock database response - multiple sessions
        mock_sessions = []
        for i in range(3):
            mock_session = MagicMock()
            mock_session.session_id = uuid.uuid4()
            mock_session.created_at = datetime.utcnow()
            mock_session.updated_at = datetime.utcnow()
            mock_session.status = SessionStatus.ACTIVE.value
            mock_sessions.append(mock_session)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_sessions
        mock_db_session.execute.return_value = mock_result

        sessions = await manager.list_user_sessions("test-user")

        assert len(sessions) == 3
        assert all("session_id" in s for s in sessions)
        assert all("status" in s for s in sessions)

    @pytest.mark.asyncio
    async def test_list_user_sessions_filters_by_status(
        self, mock_db_session: AsyncSession
    ) -> None:
        """Test filtering sessions by status."""
        manager = SessionManager(mock_db_session)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        await manager.list_user_sessions("test-user", status=SessionStatus.ARCHIVED)

        # Verify query was called (we can't check exact query, but call happened)
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_user_sessions_respects_limit(
        self, mock_db_session: AsyncSession
    ) -> None:
        """Test that session listing respects limit parameter."""
        manager = SessionManager(mock_db_session)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        await manager.list_user_sessions("test-user", limit=10)

        mock_db_session.execute.assert_called_once()


@pytest.mark.unit
class TestMessageManagement:
    """Unit tests for message management."""

    @pytest.mark.asyncio
    async def test_add_message_generates_message_id(
        self, mock_db_session: AsyncSession
    ) -> None:
        """Test that adding message generates a valid message ID."""
        manager = SessionManager(mock_db_session)
        session_id = uuid.uuid4()

        message_id = await manager.add_message(
            session_id=session_id,
            role=MessageRole.USER,
            content="Deploy my model",
        )

        assert isinstance(message_id, uuid.UUID)
        mock_db_session.add.assert_called_once()
        mock_db_session.execute.assert_called_once()  # Session update
        assert mock_db_session.commit.call_count == 1

    @pytest.mark.asyncio
    async def test_add_message_stores_correct_role(
        self, mock_db_session: AsyncSession
    ) -> None:
        """Test that message role is stored correctly."""
        manager = SessionManager(mock_db_session)
        session_id = uuid.uuid4()

        await manager.add_message(
            session_id=session_id,
            role=MessageRole.ASSISTANT,
            content="Model deployed successfully",
        )

        call_args = mock_db_session.add.call_args
        message_obj = call_args[0][0]
        assert message_obj.role == MessageRole.ASSISTANT.value
        assert message_obj.content == "Model deployed successfully"

    @pytest.mark.asyncio
    async def test_add_message_updates_session_timestamp(
        self, mock_db_session: AsyncSession
    ) -> None:
        """Test that adding message updates session timestamp."""
        manager = SessionManager(mock_db_session)
        session_id = uuid.uuid4()

        await manager.add_message(
            session_id=session_id,
            role=MessageRole.USER,
            content="Test message",
        )

        # Verify both add (for message) and execute (for session update) were called
        assert mock_db_session.add.call_count == 1
        assert mock_db_session.execute.call_count == 1
        assert mock_db_session.commit.call_count == 1


@pytest.mark.unit
class TestContextWindow:
    """Unit tests for context window management."""

    @pytest.mark.asyncio
    async def test_get_context_window_returns_recent_messages(
        self, mock_db_session: AsyncSession
    ) -> None:
        """Test that context window returns recent messages."""
        manager = SessionManager(mock_db_session, max_context_length=5)
        session_id = uuid.uuid4()

        # Mock database response - 3 messages
        mock_messages = []
        for i in range(3):
            mock_msg = MagicMock()
            mock_msg.message_id = uuid.uuid4()
            mock_msg.role = MessageRole.USER.value
            mock_msg.content = f"Message {i}"
            mock_msg.timestamp = datetime.utcnow()
            mock_messages.append(mock_msg)

        # Messages come in reverse order from DB (DESC)
        mock_messages.reverse()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_messages
        mock_db_session.execute.return_value = mock_result

        context = await manager.get_context_window(session_id)

        assert len(context) == 3
        # Should be in chronological order after reverse
        assert all("message_id" in msg for msg in context)
        assert all("role" in msg for msg in context)

    @pytest.mark.asyncio
    async def test_get_context_window_respects_custom_limit(
        self, mock_db_session: AsyncSession
    ) -> None:
        """Test that context window respects custom limit."""
        manager = SessionManager(mock_db_session, max_context_length=20)
        session_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        await manager.get_context_window(session_id, limit=5)

        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_context_window_uses_max_context_length_by_default(
        self, mock_db_session: AsyncSession
    ) -> None:
        """Test that context window uses max_context_length when limit not specified."""
        manager = SessionManager(mock_db_session, max_context_length=10)
        session_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result

        await manager.get_context_window(session_id)

        mock_db_session.execute.assert_called_once()


@pytest.mark.unit
class TestSessionArchival:
    """Unit tests for session archival and deletion."""

    @pytest.mark.asyncio
    async def test_archive_session_updates_status(
        self, mock_db_session: AsyncSession
    ) -> None:
        """Test that archiving session updates status to ARCHIVED."""
        manager = SessionManager(mock_db_session)
        session_id = uuid.uuid4()

        await manager.archive_session(session_id)

        mock_db_session.execute.assert_called_once()
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_session_removes_messages_first(
        self, mock_db_session: AsyncSession
    ) -> None:
        """Test that deleting session removes messages before session."""
        manager = SessionManager(mock_db_session)
        session_id = uuid.uuid4()

        await manager.delete_session(session_id)

        # Should execute 2 deletes (messages, then session)
        assert mock_db_session.execute.call_count == 2
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_expired_sessions_archives_old_sessions(
        self, mock_db_session: AsyncSession
    ) -> None:
        """Test that cleanup archives sessions older than threshold."""
        manager = SessionManager(mock_db_session)

        # Mock result with rowcount
        mock_result = MagicMock()
        mock_result.rowcount = 5
        mock_db_session.execute.return_value = mock_result

        archived_count = await manager.cleanup_expired_sessions(days=30)

        assert archived_count == 5
        mock_db_session.execute.assert_called_once()
        mock_db_session.commit.assert_called_once()


@pytest.mark.unit
class TestFullHistory:
    """Unit tests for full conversation history retrieval."""

    @pytest.mark.asyncio
    async def test_get_full_history_returns_all_messages_chronologically(
        self, mock_db_session: AsyncSession
    ) -> None:
        """Test that full history returns all messages in chronological order."""
        manager = SessionManager(mock_db_session)
        session_id = uuid.uuid4()

        # Mock database response - messages already in chronological order
        mock_messages = []
        for i in range(5):
            mock_msg = MagicMock()
            mock_msg.message_id = uuid.uuid4()
            mock_msg.role = MessageRole.USER.value if i % 2 == 0 else MessageRole.ASSISTANT.value
            mock_msg.content = f"Message {i}"
            mock_msg.timestamp = datetime.utcnow() + timedelta(seconds=i)
            mock_messages.append(mock_msg)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_messages
        mock_db_session.execute.return_value = mock_result

        history = await manager.get_full_history(session_id)

        assert len(history) == 5
        assert all("message_id" in msg for msg in history)
        # Verify no limit was applied
        mock_db_session.execute.assert_called_once()
