"""Pydantic data models for OpenShift AI Conversational Agent."""

# Import Pydantic models
# Import SQLAlchemy ORM models to register them with Base.metadata
# This ensures all tables are known when create_tables() is called
from src.models.conversation import (  # noqa: F401
    AuditLogEntry,
    AuditLogEntryDB,
    ConversationSession,
    ConversationSessionDB,
    Message,
    MessageDB,
    SessionStatus,
)
from src.models.intent import (  # noqa: F401
    ActionType,
    ExecutionResult,
    ExecutionResultDB,
    ExecutionStatus,
    OperationRequest,
    OperationRequestDB,
    OperationType,
    UserIntent,
    UserIntentDB,
)
from src.models.openshift import ResourceReference, ResourceType

__all__ = [
    # Conversation models
    "ConversationSession",
    "Message",
    "SessionStatus",
    "AuditLogEntry",
    # Intent models
    "UserIntent",
    "ActionType",
    "OperationRequest",
    "OperationType",
    "ExecutionResult",
    "ExecutionStatus",
    # OpenShift models
    "ResourceReference",
    "ResourceType",
]
