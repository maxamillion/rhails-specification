# Data Model: OpenShift AI Conversational Agent

**Date**: 2026-01-14
**Feature**: OpenShift AI Conversational Agent
**Purpose**: Define core data structures and their relationships

## Overview

This document defines the data models for the OpenShift AI conversational agent. The models support conversation management, intent parsing, operation execution, and audit logging. All models will be implemented as Pydantic schemas for validation and serialization.

---

## Core Entities

### 1. Conversation Session

**Purpose**: Represents an ongoing chat interaction with full context and history

**Fields**:
- `session_id` (UUID, required): Unique identifier for the conversation
- `user_id` (string, required): OpenShift user identity (from OAuth token)
- `created_at` (datetime, required): Session creation timestamp
- `updated_at` (datetime, required): Last activity timestamp
- `status` (enum, required): `active`, `archived`, `expired`
- `context_window` (list[Message], required): Recent messages for LLM context (max 20 turns)
- `metadata` (dict, optional): Additional session information (user agent, source interface)

**Relationships**:
- One-to-many with `Message` (session has multiple messages)
- One-to-many with `AuditLogEntry` (session generates multiple audit entries)

**Validation Rules**:
- `session_id` must be valid UUID v4
- `user_id` must match OpenShift username format (RFC 1123 subdomain)
- `context_window` cannot exceed 20 messages (40 turns: user + assistant pairs)
- `updated_at` must be >= `created_at`
- Sessions inactive for >30 days automatically archived

**State Transitions**:
```
active → archived (user explicit archive or 30-day inactivity)
active → expired (session timeout or auth token expiration)
archived → active (user resumes archived conversation)
```

---

### 2. Message

**Purpose**: Single message within a conversation (user query or assistant response)

**Fields**:
- `message_id` (UUID, required): Unique message identifier
- `session_id` (UUID, required, foreign key): Parent conversation session
- `role` (enum, required): `user`, `assistant`, `system`
- `content` (string, required): Message text content
- `timestamp` (datetime, required): Message creation time
- `intent` (UserIntent, optional): Parsed intent for user messages
- `operation_results` (list[ExecutionResult], optional): Results for assistant responses

**Relationships**:
- Many-to-one with `ConversationSession` (messages belong to one session)
- One-to-one with `UserIntent` (user messages may have parsed intent)
- One-to-many with `ExecutionResult` (assistant responses may contain multiple operation results)

**Validation Rules**:
- `role='user'` messages must have `intent` if agent processes them
- `role='assistant'` messages must have `operation_results` if operations performed
- `role='system'` messages used for errors, confirmations, clarifications
- `content` length ≤10,000 characters

---

### 3. User Intent

**Purpose**: Extracted meaning from natural language input

**Fields**:
- `intent_id` (UUID, required): Unique intent identifier
- `message_id` (UUID, required, foreign key): Source message
- `action_type` (enum, required): See Action Types below
- `target_resources` (list[ResourceReference], required): Resources to operate on
- `parameters` (dict, required): Operation-specific parameters
- `confidence` (float, required): Confidence score from LLM (0.0-1.0)
- `ambiguities` (list[string], optional): Unclear aspects requiring clarification
- `requires_confirmation` (bool, required): Whether operation needs user approval

**Action Types** (enum):
- **Query**: `list_models`, `get_status`, `show_metrics`, `list_notebooks`, `list_pipelines`
- **Create**: `deploy_model`, `create_pipeline`, `create_notebook`, `create_project`
- **Update**: `scale_model`, `update_pipeline`, `modify_notebook`, `update_quota`
- **Delete**: `delete_model`, `stop_notebook`, `archive_project`
- **Troubleshoot**: `analyze_logs`, `diagnose_issue`, `compare_metrics`

**Relationships**:
- One-to-one with `Message` (each user message generates one intent)
- One-to-many with `ResourceReference` (intent may target multiple resources)
- One-to-many with `OperationRequest` (intent may generate multiple operations)

**Validation Rules**:
- `confidence` must be between 0.0 and 1.0
- `confidence < 0.7` triggers clarification questions
- `action_type` in ('delete', 'update', 'create') sets `requires_confirmation=true`
- `parameters` schema validated against `action_type` requirements

---

### 4. Resource Reference

**Purpose**: Pointer to OpenShift AI resource

**Fields**:
- `resource_id` (string, required): Unique resource identifier
- `resource_type` (enum, required): See Resource Types below
- `name` (string, required): Resource name (user-facing)
- `namespace` (string, required): OpenShift namespace/project
- `current_state` (dict, optional): Cached resource status
- `last_updated` (datetime, optional): Last state check timestamp

**Resource Types** (enum):
- `model_deployment` (InferenceService)
- `data_pipeline` (Pipeline/PipelineRun)
- `notebook` (Notebook workbench)
- `project` (OpenShift Project/Namespace)
- `model_version` (Model Registry entry)

**Relationships**:
- Many-to-one with `UserIntent` (multiple resources in one intent)
- Referenced by `OperationRequest` (operations target resources)

**Validation Rules**:
- `resource_type` + `namespace` + `name` must uniquely identify resource
- `namespace` must match OpenShift project naming rules
- `current_state` TTL = 30 seconds (force refresh if older)

---

### 5. Operation Request

**Purpose**: Validated command ready for execution

**Fields**:
- `operation_id` (UUID, required): Unique operation identifier
- `intent_id` (UUID, required, foreign key): Source intent
- `operation_type` (enum, required): Kubernetes operation type
- `api_group` (string, required): Kubernetes API group
- `api_version` (string, required): API version
- `resource_plural` (string, required): Resource type plural name
- `namespace` (string, required): Target namespace
- `resource_name` (string, optional): Specific resource name (null for list/create)
- `payload` (dict, optional): Request body for create/update operations
- `confirmation_status` (enum, required): `pending`, `confirmed`, `rejected`
- `created_at` (datetime, required): Operation creation time

**Operation Types** (enum):
- `create`: Create new resource
- `get`: Retrieve single resource
- `list`: List multiple resources
- `patch`: Update existing resource
- `delete`: Remove resource

**Relationships**:
- Many-to-one with `UserIntent` (intent generates multiple operations)
- One-to-one with `ExecutionResult` (operation produces one result)

**Validation Rules**:
- Destructive operations (`delete`, `patch` with scale-down) require `confirmation_status='confirmed'`
- `payload` required for `create` and `patch` operations
- `resource_name` required for `get`, `patch`, `delete` operations
- API group/version/resource must be valid OpenShift AI CRD

---

### 6. Execution Result

**Purpose**: Outcome of an operation

**Fields**:
- `result_id` (UUID, required): Unique result identifier
- `operation_id` (UUID, required, foreign key): Executed operation
- `status` (enum, required): `success`, `failure`, `partial`, `pending`
- `output_data` (dict, optional): Structured operation output
- `error_message` (string, optional): Human-readable error (if failure)
- `error_code` (string, optional): Machine-readable error code
- `resource_state` (dict, optional): Resource state after operation
- `execution_time_ms` (int, required): Operation latency in milliseconds
- `retry_count` (int, required): Number of retries attempted (0 = first try)
- `completed_at` (datetime, required): Operation completion timestamp

**Status Values**:
- `success`: Operation completed successfully
- `failure`: Operation failed (non-retryable or max retries exceeded)
- `partial`: Multi-step operation partially completed
- `pending`: Async operation submitted, awaiting completion

**Relationships**:
- One-to-one with `OperationRequest` (result from one operation)
- Many-to-one with `Message` (multiple results in one assistant message)

**Validation Rules**:
- `status='failure'` requires `error_message` and `error_code`
- `status='success'` requires `output_data` or `resource_state`
- `execution_time_ms` triggers warning if >2000ms (query) or >10000ms (command)
- `retry_count` ≤3 (max retries for retryable errors)

---

### 7. Audit Log Entry

**Purpose**: Immutable record of user command and system action

**Fields**:
- `log_id` (UUID, required): Unique log entry identifier
- `timestamp` (datetime, required): Event timestamp (indexed)
- `user_id` (string, required, indexed): OpenShift user identity
- `session_id` (UUID, required, indexed): Conversation session
- `user_command` (string, required): Original natural language input
- `parsed_intent` (dict, required): JSON representation of UserIntent
- `openshift_operation` (string, required): Kubernetes API operation performed
- `operation_result` (dict, required): Structured result data
- `operation_error` (string, optional): Error message if failed
- `duration_ms` (int, required): Total operation duration
- `ip_address` (string, optional): User's IP address
- `user_agent` (string, optional): Client user agent

**Relationships**:
- Many-to-one with `ConversationSession` (audit entries from one session)
- No foreign key constraints (append-only log, never delete sessions referenced here)

**Validation Rules**:
- Append-only table (no updates or deletes allowed)
- `timestamp` auto-generated by database (cannot be specified by application)
- All fields required except `operation_error`, `ip_address`, `user_agent`
- Retention policy: 90 days minimum, auto-archive to cold storage after 1 year

**Indexes**:
- Primary index on `log_id`
- Composite index on (`user_id`, `timestamp`) for user activity queries
- Index on `session_id` for conversation audit trails
- Index on `timestamp` for time-range queries

---

## Entity Relationships Diagram

```
┌──────────────────────┐
│ ConversationSession  │
│ - session_id (PK)    │
│ - user_id            │
│ - created_at         │
│ - updated_at         │
│ - status             │
│ - context_window     │
└──────────────────────┘
           │
           │ 1:N
           ▼
┌──────────────────────┐
│ Message              │
│ - message_id (PK)    │
│ - session_id (FK)    │
│ - role               │
│ - content            │
│ - timestamp          │
└──────────────────────┘
           │
           │ 1:1 (user messages)
           ▼
┌──────────────────────┐
│ UserIntent           │
│ - intent_id (PK)     │
│ - message_id (FK)    │
│ - action_type        │
│ - target_resources   │
│ - parameters         │
│ - confidence         │
└──────────────────────┘
           │
           │ 1:N
           ▼
┌──────────────────────┐          ┌──────────────────────┐
│ OperationRequest     │  1:N     │ ResourceReference    │
│ - operation_id (PK)  │◄─────────│ - resource_id (PK)   │
│ - intent_id (FK)     │          │ - resource_type      │
│ - operation_type     │          │ - name               │
│ - api_group          │          │ - namespace          │
│ - confirmation_status│          │ - current_state      │
└──────────────────────┘          └──────────────────────┘
           │
           │ 1:1
           ▼
┌──────────────────────┐
│ ExecutionResult      │
│ - result_id (PK)     │
│ - operation_id (FK)  │
│ - status             │
│ - output_data        │
│ - error_message      │
│ - execution_time_ms  │
└──────────────────────┘


Audit Trail (separate, append-only):

┌──────────────────────┐
│ AuditLogEntry        │
│ - log_id (PK)        │
│ - timestamp          │
│ - user_id            │
│ - session_id         │
│ - user_command       │
│ - parsed_intent      │
│ - openshift_operation│
│ - operation_result   │
│ - operation_error    │
└──────────────────────┘
```

---

## Pydantic Schema Examples

### ConversationSession

```python
from pydantic import BaseModel, Field, validator
from typing import List, Optional
from datetime import datetime
from enum import Enum
import uuid

class SessionStatus(str, Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    EXPIRED = "expired"

class ConversationSession(BaseModel):
    session_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    user_id: str = Field(..., regex=r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    status: SessionStatus = SessionStatus.ACTIVE
    context_window: List['Message'] = Field(default_factory=list, max_items=20)
    metadata: Optional[dict] = None

    @validator('context_window')
    def validate_context_window(cls, v):
        if len(v) > 20:
            # Auto-prune oldest messages to maintain 20-message limit
            return v[-20:]
        return v

    class Config:
        orm_mode = True
```

### UserIntent

```python
class ActionType(str, Enum):
    # Query operations
    LIST_MODELS = "list_models"
    GET_STATUS = "get_status"
    SHOW_METRICS = "show_metrics"
    # Create operations
    DEPLOY_MODEL = "deploy_model"
    CREATE_PIPELINE = "create_pipeline"
    CREATE_NOTEBOOK = "create_notebook"
    # Update operations
    SCALE_MODEL = "scale_model"
    UPDATE_PIPELINE = "update_pipeline"
    # Delete operations
    DELETE_MODEL = "delete_model"
    STOP_NOTEBOOK = "stop_notebook"

class UserIntent(BaseModel):
    intent_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    message_id: uuid.UUID
    action_type: ActionType
    target_resources: List['ResourceReference']
    parameters: dict = Field(default_factory=dict)
    confidence: float = Field(..., ge=0.0, le=1.0)
    ambiguities: Optional[List[str]] = None
    requires_confirmation: bool = False

    @validator('requires_confirmation', always=True)
    def set_confirmation_requirement(cls, v, values):
        # Auto-set based on action type
        destructive_actions = {
            ActionType.DELETE_MODEL,
            ActionType.STOP_NOTEBOOK,
            ActionType.SCALE_MODEL
        }
        if values.get('action_type') in destructive_actions:
            return True
        return v

    class Config:
        orm_mode = True
```

---

## Database Schema (PostgreSQL)

### Tables

```sql
-- Conversation sessions
CREATE TABLE conversation_sessions (
    session_id UUID PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status VARCHAR(20) NOT NULL CHECK (status IN ('active', 'archived', 'expired')),
    metadata JSONB,
    INDEX idx_user_sessions (user_id, updated_at DESC)
);

-- Messages (conversation history)
CREATE TABLE messages (
    message_id UUID PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES conversation_sessions(session_id),
    role VARCHAR(20) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content TEXT NOT NULL CHECK (length(content) <= 10000),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    INDEX idx_session_messages (session_id, timestamp ASC)
);

-- User intents
CREATE TABLE user_intents (
    intent_id UUID PRIMARY KEY,
    message_id UUID NOT NULL REFERENCES messages(message_id),
    action_type VARCHAR(50) NOT NULL,
    target_resources JSONB NOT NULL,
    parameters JSONB NOT NULL DEFAULT '{}',
    confidence DECIMAL(3, 2) NOT NULL CHECK (confidence >= 0.0 AND confidence <= 1.0),
    ambiguities JSONB,
    requires_confirmation BOOLEAN NOT NULL DEFAULT FALSE
);

-- Operation requests
CREATE TABLE operation_requests (
    operation_id UUID PRIMARY KEY,
    intent_id UUID NOT NULL REFERENCES user_intents(intent_id),
    operation_type VARCHAR(20) NOT NULL CHECK (operation_type IN ('create', 'get', 'list', 'patch', 'delete')),
    api_group VARCHAR(100) NOT NULL,
    api_version VARCHAR(20) NOT NULL,
    resource_plural VARCHAR(50) NOT NULL,
    namespace VARCHAR(255) NOT NULL,
    resource_name VARCHAR(255),
    payload JSONB,
    confirmation_status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (confirmation_status IN ('pending', 'confirmed', 'rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Execution results
CREATE TABLE execution_results (
    result_id UUID PRIMARY KEY,
    operation_id UUID NOT NULL REFERENCES operation_requests(operation_id),
    status VARCHAR(20) NOT NULL CHECK (status IN ('success', 'failure', 'partial', 'pending')),
    output_data JSONB,
    error_message TEXT,
    error_code VARCHAR(50),
    resource_state JSONB,
    execution_time_ms INTEGER NOT NULL,
    retry_count INTEGER NOT NULL DEFAULT 0 CHECK (retry_count <= 3),
    completed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Audit logs (append-only)
CREATE TABLE audit_logs (
    log_id UUID PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    user_id VARCHAR(255) NOT NULL,
    session_id UUID NOT NULL,
    user_command TEXT NOT NULL,
    parsed_intent JSONB NOT NULL,
    openshift_operation VARCHAR(100) NOT NULL,
    operation_result JSONB NOT NULL,
    operation_error TEXT,
    duration_ms INTEGER NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    INDEX idx_user_audit (user_id, timestamp DESC),
    INDEX idx_session_audit (session_id),
    INDEX idx_timestamp (timestamp DESC)
);

-- Prevent updates/deletes on audit_logs
CREATE RULE prevent_audit_update AS ON UPDATE TO audit_logs DO INSTEAD NOTHING;
CREATE RULE prevent_audit_delete AS ON DELETE TO audit_logs DO INSTEAD NOTHING;
```

---

## Data Lifecycle

### Conversation Retention

- **Active Conversations**: Retained indefinitely while user active
- **Archived Conversations**: 30-day retention, then moved to cold storage
- **Expired Conversations**: Deleted after 7 days

### Audit Log Retention

- **Primary Storage**: 90 days (hot storage, fast queries)
- **Archive Storage**: 1 year (cold storage, slower queries)
- **Long-term Retention**: Depends on compliance requirements (2-7 years typical)

### Cleanup Policies

```sql
-- Archive old conversations (scheduled job, daily)
UPDATE conversation_sessions
SET status = 'archived'
WHERE updated_at < NOW() - INTERVAL '30 days'
  AND status = 'active';

-- Delete expired conversations (scheduled job, daily)
DELETE FROM conversation_sessions
WHERE status = 'expired'
  AND updated_at < NOW() - INTERVAL '7 days';

-- Archive old audit logs (scheduled job, monthly)
-- Move to separate archive table or export to object storage
```

---

## Migration Strategy

### Phase 1: Core Conversation Support

- Implement ConversationSession, Message models
- Basic intent parsing (limited action types)
- In-memory context window (no persistence)

### Phase 2: Full Intent & Operations

- Add UserIntent, OperationRequest, ExecutionResult models
- Persistent conversation storage (PostgreSQL)
- Full action type coverage

### Phase 3: Audit & Compliance

- Implement AuditLogEntry model
- Audit log retention policies
- Compliance reporting queries

This phased approach allows MVP delivery without full data model complexity.
