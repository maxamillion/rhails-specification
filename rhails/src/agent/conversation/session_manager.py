"""Conversation session management with persistent storage."""

import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.conversation import (
    ConversationSessionDB,
    MessageDB,
    MessageRole,
    SessionStatus,
)


class SessionManager:
    """Manages conversation sessions with persistent storage.

    Handles session lifecycle, message history, and context window management
    for maintaining coherent conversations across multiple turns.
    """

    def __init__(self, db_session: AsyncSession, max_context_length: int = 20):
        """Initialize session manager.

        Args:
            db_session: Database session for persistence
            max_context_length: Maximum messages in context window
        """
        self.db_session = db_session
        self.max_context_length = max_context_length

    async def create_session(
        self, user_id: str, metadata: dict | None = None
    ) -> uuid.UUID:
        """Create a new conversation session.

        Args:
            user_id: OpenShift user identity
            metadata: Additional session metadata (user_agent, source, etc.)

        Returns:
            Session ID
        """
        session_id = uuid.uuid4()

        session = ConversationSessionDB(
            session_id=session_id,
            user_id=user_id,
            status=SessionStatus.ACTIVE.value,
            metadata=metadata,
        )

        self.db_session.add(session)
        await self.db_session.commit()

        return session_id

    async def get_session(self, session_id: uuid.UUID) -> dict | None:
        """Get session details.

        Args:
            session_id: Session ID

        Returns:
            Session data or None if not found
        """
        query = select(ConversationSessionDB).where(
            ConversationSessionDB.session_id == session_id
        )
        result = await self.db_session.execute(query)
        session = result.scalar_one_or_none()

        if session is None:
            return None

        return {
            "session_id": str(session.session_id),
            "user_id": session.user_id,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "status": session.status,
            "metadata": session.metadata,
        }

    async def list_user_sessions(
        self, user_id: str, status: SessionStatus | None = None, limit: int = 50
    ) -> list[dict]:
        """List sessions for a user.

        Args:
            user_id: OpenShift user identity
            status: Filter by status (optional)
            limit: Maximum sessions to return

        Returns:
            List of session summaries
        """
        query = select(ConversationSessionDB).where(
            ConversationSessionDB.user_id == user_id
        )

        if status:
            query = query.where(ConversationSessionDB.status == status.value)

        query = query.order_by(ConversationSessionDB.updated_at.desc()).limit(limit)

        result = await self.db_session.execute(query)
        sessions = result.scalars().all()

        return [
            {
                "session_id": str(session.session_id),
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "status": session.status,
            }
            for session in sessions
        ]

    async def add_message(
        self,
        session_id: uuid.UUID,
        role: MessageRole,
        content: str,
        intent: dict | None = None,
        operation_results: list[dict] | None = None,
    ) -> uuid.UUID:
        """Add message to conversation session.

        Args:
            session_id: Session ID
            role: Message role (user, assistant, system)
            content: Message content
            intent: Parsed intent (for user messages)
            operation_results: Operation results (for assistant messages)

        Returns:
            Message ID
        """
        message_id = uuid.uuid4()

        message = MessageDB(
            message_id=message_id,
            session_id=session_id,
            role=role.value,
            content=content,
        )

        self.db_session.add(message)

        # Update session updated_at timestamp
        update_stmt = (
            update(ConversationSessionDB)
            .where(ConversationSessionDB.session_id == session_id)
            .values(updated_at=datetime.utcnow())
        )
        await self.db_session.execute(update_stmt)

        await self.db_session.commit()

        return message_id

    async def get_context_window(
        self, session_id: uuid.UUID, limit: int | None = None
    ) -> list[dict]:
        """Get conversation context window for session.

        Args:
            session_id: Session ID
            limit: Maximum messages to return (defaults to max_context_length)

        Returns:
            List of recent messages ordered chronologically
        """
        if limit is None:
            limit = self.max_context_length

        query = (
            select(MessageDB)
            .where(MessageDB.session_id == session_id)
            .order_by(MessageDB.timestamp.desc())
            .limit(limit)
        )

        result = await self.db_session.execute(query)
        messages = result.scalars().all()

        # Reverse to get chronological order
        messages.reverse()

        return [
            {
                "message_id": str(msg.message_id),
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
            }
            for msg in messages
        ]

    async def get_full_history(self, session_id: uuid.UUID) -> list[dict]:
        """Get complete conversation history for session.

        Args:
            session_id: Session ID

        Returns:
            All messages in chronological order
        """
        query = (
            select(MessageDB)
            .where(MessageDB.session_id == session_id)
            .order_by(MessageDB.timestamp.asc())
        )

        result = await self.db_session.execute(query)
        messages = result.scalars().all()

        return [
            {
                "message_id": str(msg.message_id),
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
            }
            for msg in messages
        ]

    async def archive_session(self, session_id: uuid.UUID) -> None:
        """Archive a conversation session.

        Args:
            session_id: Session ID
        """
        update_stmt = (
            update(ConversationSessionDB)
            .where(ConversationSessionDB.session_id == session_id)
            .values(
                status=SessionStatus.ARCHIVED.value,
                updated_at=datetime.utcnow(),
            )
        )

        await self.db_session.execute(update_stmt)
        await self.db_session.commit()

    async def delete_session(self, session_id: uuid.UUID) -> None:
        """Delete a conversation session and all its messages.

        Args:
            session_id: Session ID

        Note:
            This is a hard delete. For compliance, use archive_session() instead.
        """
        from sqlalchemy import delete

        # Delete messages first (foreign key constraint)
        delete_messages = delete(MessageDB).where(MessageDB.session_id == session_id)
        await self.db_session.execute(delete_messages)

        # Delete session
        delete_session = delete(ConversationSessionDB).where(
            ConversationSessionDB.session_id == session_id
        )
        await self.db_session.execute(delete_session)

        await self.db_session.commit()

    async def cleanup_expired_sessions(self, days: int = 30) -> int:
        """Clean up expired inactive sessions.

        Args:
            days: Sessions inactive for this many days will be archived

        Returns:
            Number of sessions archived
        """
        from datetime import timedelta

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        update_stmt = (
            update(ConversationSessionDB)
            .where(
                ConversationSessionDB.status == SessionStatus.ACTIVE.value,
                ConversationSessionDB.updated_at < cutoff_date,
            )
            .values(
                status=SessionStatus.EXPIRED.value,
                updated_at=datetime.utcnow(),
            )
        )

        result = await self.db_session.execute(update_stmt)
        await self.db_session.commit()

        return result.rowcount
