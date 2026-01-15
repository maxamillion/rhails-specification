"""Intent parsing and operation execution data models."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator
from sqlalchemy import (
    JSON,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from src.models.base import Base
from src.models.openshift import ResourceType


class ActionType(str, Enum):
    """User intent action types."""

    # Query operations
    LIST_MODELS = "list_models"
    GET_STATUS = "get_status"
    SHOW_METRICS = "show_metrics"
    LIST_NOTEBOOKS = "list_notebooks"
    LIST_PIPELINES = "list_pipelines"
    LIST_PROJECTS = "list_projects"
    GET_PROJECT_RESOURCES = "get_project_resources"

    # Create operations
    DEPLOY_MODEL = "deploy_model"
    CREATE_PIPELINE = "create_pipeline"
    CREATE_NOTEBOOK = "create_notebook"
    CREATE_PROJECT = "create_project"

    # Update operations
    SCALE_MODEL = "scale_model"
    UPDATE_PIPELINE = "update_pipeline"
    MODIFY_NOTEBOOK = "modify_notebook"
    UPDATE_QUOTA = "update_quota"
    ADD_USER_TO_PROJECT = "add_user_to_project"

    # Control operations
    START_NOTEBOOK = "start_notebook"

    # Delete operations
    DELETE_MODEL = "delete_model"
    STOP_NOTEBOOK = "stop_notebook"
    DELETE_NOTEBOOK = "delete_notebook"
    ARCHIVE_PROJECT = "archive_project"

    # Troubleshoot operations
    ANALYZE_LOGS = "analyze_logs"
    DIAGNOSE_ISSUE = "diagnose_issue"
    DIAGNOSE_PERFORMANCE = "diagnose_performance"
    COMPARE_METRICS = "compare_metrics"
    GET_PREDICTION_DISTRIBUTION = "get_prediction_distribution"


class OperationType(str, Enum):
    """Kubernetes operation types."""

    CREATE = "create"
    GET = "get"
    LIST = "list"
    PATCH = "patch"
    DELETE = "delete"


class ExecutionStatus(str, Enum):
    """Operation execution status."""

    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    PENDING = "pending"


class ConfirmationStatus(str, Enum):
    """Operation confirmation status."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    REJECTED = "rejected"


# ========== SQLAlchemy ORM Models ==========


class UserIntentDB(Base):
    """SQLAlchemy model for user_intents table."""

    __tablename__ = "user_intents"

    intent_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.message_id"), nullable=False)
    action_type = Column(String(50), nullable=False)
    target_resources = Column(JSON, nullable=False)
    parameters = Column(JSON, nullable=False, server_default="{}")
    confidence = Column(Numeric(3, 2), nullable=False)
    ambiguities = Column(JSON, nullable=True)
    requires_confirmation = Column(String(10), nullable=False, server_default="false")

    __table_args__ = (
        CheckConstraint("confidence >= 0.0 AND confidence <= 1.0", name="user_intents_confidence_check"),
    )


class OperationRequestDB(Base):
    """SQLAlchemy model for operation_requests table."""

    __tablename__ = "operation_requests"

    operation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    intent_id = Column(UUID(as_uuid=True), ForeignKey("user_intents.intent_id"), nullable=False)
    operation_type = Column(String(20), nullable=False)
    api_group = Column(String(100), nullable=False)
    api_version = Column(String(20), nullable=False)
    resource_plural = Column(String(50), nullable=False)
    namespace = Column(String(255), nullable=False)
    resource_name = Column(String(255), nullable=True)
    payload = Column(JSON, nullable=True)
    confirmation_status = Column(
        String(20),
        nullable=False,
        default=ConfirmationStatus.PENDING.value,
        server_default=ConfirmationStatus.PENDING.value,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            f"operation_type IN ('{OperationType.CREATE.value}', '{OperationType.GET.value}', '{OperationType.LIST.value}', '{OperationType.PATCH.value}', '{OperationType.DELETE.value}')",
            name="operation_requests_operation_type_check",
        ),
        CheckConstraint(
            f"confirmation_status IN ('{ConfirmationStatus.PENDING.value}', '{ConfirmationStatus.CONFIRMED.value}', '{ConfirmationStatus.REJECTED.value}')",
            name="operation_requests_confirmation_status_check",
        ),
    )


class ExecutionResultDB(Base):
    """SQLAlchemy model for execution_results table."""

    __tablename__ = "execution_results"

    result_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    operation_id = Column(
        UUID(as_uuid=True), ForeignKey("operation_requests.operation_id"), nullable=False
    )
    status = Column(String(20), nullable=False)
    output_data = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    error_code = Column(String(50), nullable=True)
    resource_state = Column(JSON, nullable=True)
    execution_time_ms = Column(Integer, nullable=False)
    retry_count = Column(Integer, nullable=False, default=0, server_default="0")
    completed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        CheckConstraint(
            f"status IN ('{ExecutionStatus.SUCCESS.value}', '{ExecutionStatus.FAILURE.value}', '{ExecutionStatus.PARTIAL.value}', '{ExecutionStatus.PENDING.value}')",
            name="execution_results_status_check",
        ),
        CheckConstraint("retry_count <= 3", name="execution_results_retry_count_check"),
    )


# ========== Pydantic Models ==========


class UserIntent(BaseModel):
    """Extracted meaning from natural language input.

    Represents the parsed intent from a user message including action,
    target resources, parameters, and confidence.
    """

    intent_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    message_id: uuid.UUID
    action_type: ActionType
    target_resources: list[dict]  # ResourceReference as dicts
    parameters: dict = Field(default_factory=dict)
    confidence: float = Field(..., ge=0.0, le=1.0)
    ambiguities: list[str] | None = None
    requires_confirmation: bool = False

    @field_validator("requires_confirmation")
    @classmethod
    def set_confirmation_requirement(cls, v: bool, info) -> bool:
        """Auto-set confirmation requirement based on action type."""
        destructive_actions = {
            ActionType.DELETE_MODEL,
            ActionType.STOP_NOTEBOOK,
            ActionType.DELETE_NOTEBOOK,
            ActionType.SCALE_MODEL,
            ActionType.ARCHIVE_PROJECT,
        }
        # Use get with default to handle cases where action_type might not be set yet
        action_type = info.data.get("action_type")
        if action_type in destructive_actions:
            return True
        return v

    class Config:
        """Pydantic configuration."""

        from_attributes = True
        use_enum_values = True


class OperationRequest(BaseModel):
    """Validated command ready for execution.

    Represents a Kubernetes API operation that will be executed
    against OpenShift AI resources.
    """

    operation_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    session_id: uuid.UUID
    user_id: str
    operation_type: str  # create, get, list, patch, delete
    target_resource: "ResourceType"  # Forward reference
    resource_name: str | None = None
    parameters: dict = Field(default_factory=dict)
    requires_confirmation: bool = False
    confirmation_token: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        """Pydantic configuration."""

        from_attributes = True
        use_enum_values = True


class ExecutionResult(BaseModel):
    """Outcome of an operation execution.

    Contains the result of executing a Kubernetes API operation,
    including success/failure status and output data.
    """

    execution_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    operation_id: uuid.UUID
    status: str  # success, error, pending_confirmation
    resource_type: "ResourceType"  # Forward reference
    resource_name: str
    result_data: Any = None
    error_message: str | None = None
    retry_count: int = Field(default=0, ge=0, le=3)
    completed_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        """Pydantic configuration."""

        from_attributes = True
        use_enum_values = True
        arbitrary_types_allowed = True


# Rebuild models with forward references after all types are defined
UserIntent.model_rebuild()
OperationRequest.model_rebuild()
ExecutionResult.model_rebuild()
