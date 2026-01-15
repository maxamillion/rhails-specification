"""Conversation and audit log data models."""

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from src.models.base import Base


class SessionStatus(str, Enum):
    """Conversation session status."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    EXPIRED = "expired"


class MessageRole(str, Enum):
    """Message role in conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


# ========== SQLAlchemy ORM Models ==========


class ConversationSessionDB(Base):
    """SQLAlchemy model for conversation sessions table."""

    __tablename__ = "conversation_sessions"

    session_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String(255), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    status = Column(
        String(20),
        nullable=False,
        default=SessionStatus.ACTIVE.value,
        server_default=SessionStatus.ACTIVE.value,
    )
    session_metadata = Column("metadata", JSON, nullable=True)  # Use column mapping to avoid SQLAlchemy reserved name

    __table_args__ = (
        CheckConstraint(
            f"status IN ('{SessionStatus.ACTIVE.value}', '{SessionStatus.ARCHIVED.value}', '{SessionStatus.EXPIRED.value}')",
            name="conversation_sessions_status_check",
        ),
        Index("idx_user_sessions", "user_id", "updated_at"),
    )


class MessageDB(Base):
    """SQLAlchemy model for messages table."""

    __tablename__ = "messages"

    message_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(
        UUID(as_uuid=True), ForeignKey("conversation_sessions.session_id"), nullable=False
    )
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            f"role IN ('{MessageRole.USER.value}', '{MessageRole.ASSISTANT.value}', '{MessageRole.SYSTEM.value}')",
            name="messages_role_check",
        ),
        CheckConstraint("length(content) <= 10000", name="messages_content_length_check"),
        Index("idx_session_messages", "session_id", "timestamp"),
    )


class AuditLogEntryDB(Base):
    """SQLAlchemy model for audit_logs table (append-only)."""

    __tablename__ = "audit_logs"

    log_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    user_id = Column(String(255), nullable=False, index=True)
    session_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    user_command = Column(Text, nullable=False)
    parsed_intent = Column(JSON, nullable=False)
    openshift_operation = Column(String(100), nullable=False)
    operation_result = Column(JSON, nullable=False)
    operation_error = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_user_audit", "user_id", "timestamp"),
        Index("idx_session_audit", "session_id"),
        Index("idx_timestamp", "timestamp"),
    )


# ========== Pydantic Models ==========


class ConversationSession(BaseModel):
    """Conversation session with context and metadata.

    Represents an ongoing chat interaction with full context and history.
    """

    session_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user_id: str = Field(..., pattern=r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    status: SessionStatus = SessionStatus.ACTIVE
    context_window: list["Message"] = Field(default_factory=list, max_length=20)
    metadata: dict | None = None

    @field_validator("context_window")
    @classmethod
    def validate_context_window(cls, v: list["Message"]) -> list["Message"]:
        """Auto-prune context window to maintain 20-message limit."""
        if len(v) > 20:
            # Keep most recent 20 messages
            return v[-20:]
        return v

    class Config:
        """Pydantic configuration."""

        from_attributes = True
        use_enum_values = True


class Message(BaseModel):
    """Single message within a conversation.

    Represents user query, assistant response, or system notification.
    """

    message_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    session_id: uuid.UUID
    role: MessageRole
    content: str = Field(..., max_length=10000)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    intent: dict | None = None  # UserIntent as dict (optional for user messages)
    operation_results: list[dict] | None = None  # ExecutionResults as dicts (optional for assistant)

    class Config:
        """Pydantic configuration."""

        from_attributes = True
        use_enum_values = True


class AuditLogEntry(BaseModel):
    """Immutable audit log record.

    Records all user commands and system actions for compliance and troubleshooting.
    """

    log_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    user_id: str
    session_id: uuid.UUID
    user_command: str
    parsed_intent: dict
    openshift_operation: str
    operation_result: dict
    operation_error: str | None = None
    duration_ms: int
    ip_address: str | None = None
    user_agent: str | None = None

    class Config:
        """Pydantic configuration."""

        from_attributes = True


# Forward reference resolution
ConversationSession.model_rebuild()
Message.model_rebuild()
