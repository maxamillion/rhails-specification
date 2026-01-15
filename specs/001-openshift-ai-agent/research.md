# Research: OpenShift AI Conversational Agent

**Date**: 2026-01-14
**Feature**: OpenShift AI Conversational Agent
**Purpose**: Resolve technical unknowns and establish architectural decisions

## Executive Summary

This research resolves all NEEDS CLARIFICATION items from the Technical Context section of plan.md. The findings establish concrete technology choices for building a conversational AI agent using the Lightspeed Core lightspeed-stack framework to control OpenShift AI.

---

## Decision 1: LLM Provider Selection

**Question**: Which LLM provider should we use (OpenAI, Anthropic, or local model)?

**Decision**: Use **OpenShift AI (RHOAI) with vLLM** for on-cluster deployment

**Rationale**:
1. **On-Cluster Deployment**: Keeps data within the OpenShift cluster, avoiding external API dependencies
2. **Air-Gapped Support**: Enables deployment in secure/regulated environments with hermetic builds
3. **Framework Compatibility**: Lightspeed-stack explicitly supports RHOAI and RHEL AI with vLLM-based Llama models
4. **Cost Efficiency**: No per-token API costs for cloud providers
5. **Consistency**: Uses the same OpenShift AI platform the agent is controlling
6. **Red Hat Ecosystem**: Native integration with Red Hat's support and tooling

**Alternatives Considered**:
- **OpenAI GPT-4o**: Better performance but requires external API, costs per-token, cannot run air-gapped
- **Azure OpenAI**: Similar to OpenAI but with Azure dependencies, still external
- **IBM WatsonX**: Supported by lightspeed-stack but adds external dependency

**Implementation Details**:
- Deploy Llama 3.3-70B model via OpenShift AI model serving
- Use vLLM inference runtime for high-performance serving
- Enable tool calling capabilities for agentic operations
- Configure lightspeed-stack to connect to on-cluster LLM endpoint

---

## Decision 2: OpenShift AI Client Library

**Question**: Which OpenShift AI client library version should we use?

**Decision**: Use **openshift>=0.13.0, kserve>=0.14.0, kfp>=2.8.0, model-registry>=0.2.0**

**Rationale**:
1. **No Unified SDK**: OpenShift AI uses Kubernetes Custom Resources (CRDs), not a single SDK
2. **Multi-Library Approach**: Different libraries handle different OpenShift AI capabilities:
   - `openshift`: Core Kubernetes/OpenShift REST client for CRD management
   - `kserve`: Model deployment via InferenceService resources
   - `kfp`: Pipeline orchestration (v2.x for OpenShift AI 2.16+)
   - `model-registry`: Model lifecycle management

**Critical Version Note**:
- **Pipeline API Breaking Change**: OpenShift AI 2.16+ moved from kfp-tekton (v1.5.x) to kfp v2.x
- Must use kfp v2.x for modern OpenShift AI deployments
- Resources from DSP 1.0 (kfp-tekton) cannot be managed in DSP 2.0 (kfp v2.x)

**Stable APIs to Use**:
- ✅ `Notebook` (kubeflow.org/v1) - Workbench/notebook management
- ✅ `InferenceService` (serving.kserve.io/v1beta1) - Model deployment
- ✅ `DataScienceCluster` (datasciencecluster.opendatahub.io/v1) - Platform config
- ⚠️ `Pipeline runs` (KFP API v2.x) - Beta but recommended

**Authentication Pattern**:
- Use **Service Account Tokens** for programmatic access
- Create service account in target namespace with edit/admin RBAC role
- Retrieve token with: `oc sa get-token <sa-name>`
- Include in Authorization header: `Bearer <token>`

---

## Decision 3: Conversation Persistence Storage

**Question**: What storage should we use for conversation persistence (PostgreSQL, Redis, or file-based)?

**Decision**: Use **PostgreSQL** for conversation history and audit logs

**Rationale**:
1. **Framework Support**: Lightspeed-stack has native PostgreSQL integration for conversation history
2. **Relational Model**: Conversation sessions, messages, and audit logs fit relational schema well
3. **ACID Guarantees**: Ensures data consistency for audit compliance
4. **Scalability**: PostgreSQL handles 100+ concurrent users easily
5. **OpenShift Integration**: Easy to deploy via OpenShift Templates or Operators

**Conversation Data Model**:
- Compound key: (user_id, conversation_id)
- Support for multiple concurrent conversations per user
- Maximum conversation length configurable
- Automatic pruning of conversations older than retention period (30 days)

**Audit Log Storage**:
- Same PostgreSQL database, separate table
- Immutable append-only log of all operations
- Fields: timestamp, user_id, command, interpretation, operation, result, error

**Alternatives Considered**:
- **Redis**: Better for high-frequency caching but limited relational query capabilities
- **SQLite**: Lightspeed-stack default but not suitable for production (single-file, no concurrency)
- **File-based**: No transactional guarantees, difficult to query

**Deployment**:
- Use PostgreSQL Operator for OpenShift deployment
- Configure persistent volume for data durability
- Enable connection pooling via PgBouncer for high concurrency

---

## Decision 4: Audit Logging Approach

**Question**: Database or file-based logging for audit trails?

**Decision**: **PostgreSQL for structured audit logs** + **File-based logging for application logs**

**Rationale**:
1. **Separation of Concerns**:
   - Audit logs (PostgreSQL): Queryable business events requiring compliance
   - Application logs (files): Debug/diagnostic information
2. **Compliance**: Audit logs in PostgreSQL enable:
   - Querying by user, operation, timeframe
   - Retention policy enforcement
   - Tamper-evident append-only writes
3. **Performance**: File-based app logs avoid database overhead for high-volume debug logging

**Audit Log Schema** (PostgreSQL):
```sql
CREATE TABLE audit_logs (
  id SERIAL PRIMARY KEY,
  timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  user_id VARCHAR(255) NOT NULL,
  conversation_id UUID NOT NULL,
  user_command TEXT NOT NULL,
  parsed_intent JSONB NOT NULL,
  openshift_operation VARCHAR(100) NOT NULL,
  operation_result TEXT,
  operation_error TEXT,
  duration_ms INTEGER,
  INDEX idx_user_time (user_id, timestamp),
  INDEX idx_conversation (conversation_id)
);
```

**Application Logging**:
- Use Python `logging` module with structured JSON output
- Log to stdout (captured by OpenShift/Kubernetes logging infrastructure)
- Log levels: DEBUG (development), INFO (production), WARNING, ERROR
- Include correlation IDs (conversation_id) in all log entries

**Data Collection Export**:
- Configure lightspeed-stack's user data collection paths
- Export conversation transcripts and feedback to Red Hat Dataverse for analysis
- Separate from audit logs (optional analytics vs. required compliance)

---

## Architecture Summary

### Technology Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Language | Python | 3.12 |
| Package Manager | uv | latest |
| Framework | lightspeed-stack | >=0.3.0 |
| LLM Provider | OpenShift AI (RHOAI) vLLM | Llama 3.3-70B |
| OpenShift Client | openshift | >=0.13.0 |
| Model Serving | kserve | >=0.14.0 |
| Pipelines | kfp | >=2.8.0 |
| Model Registry | model-registry | >=0.2.0 |
| Database | PostgreSQL | 15+ |
| Testing | pytest, pytest-asyncio | latest |

### Deployment Architecture

```
┌─────────────────────────────────────────────────┐
│ OpenShift Cluster                               │
│                                                 │
│  ┌────────────────────────────────────────┐    │
│  │ Lightspeed Agent Service               │    │
│  │ (lightspeed-stack)                     │    │
│  │                                        │    │
│  │  ┌──────────────────┐                  │    │
│  │  │ Intent Parser    │                  │    │
│  │  │ (LLM-powered)    │                  │    │
│  │  └──────────────────┘                  │    │
│  │           │                            │    │
│  │           ▼                            │    │
│  │  ┌──────────────────┐                  │    │
│  │  │ Operation        │───────┐          │    │
│  │  │ Executor         │       │          │    │
│  │  └──────────────────┘       │          │    │
│  │                             │          │    │
│  │  ┌──────────────────┐       │          │    │
│  │  │ Conversation     │       │          │    │
│  │  │ Manager          │       │          │    │
│  │  └──────────────────┘       │          │    │
│  └────────────────────────────────────────┘    │
│                │                │               │
│                ▼                ▼               │
│  ┌──────────────────┐  ┌──────────────────┐    │
│  │ PostgreSQL       │  │ OpenShift AI API │    │
│  │ (Conversations   │  │ (Kubernetes CRDs)│    │
│  │  + Audit Logs)   │  │                  │    │
│  └──────────────────┘  └──────────────────┘    │
│                                                 │
│  ┌──────────────────────────────────────────┐  │
│  │ OpenShift AI vLLM Inference Service      │  │
│  │ (Llama 3.3-70B)                          │  │
│  └──────────────────────────────────────────┘  │
└─────────────────────────────────────────────────┘
```

### Key Design Patterns

1. **Intent → Operation Pattern**:
   - Natural language → LLM → Intent object
   - Intent → Operation executor → Kubernetes API call
   - Clear separation of concerns, testable components

2. **Context Management**:
   - Persistent conversation history in PostgreSQL
   - 20-turn context window for LLM
   - Automatic context pruning for token efficiency

3. **Error Handling**:
   - OpenShift API errors → User-friendly explanations
   - Retryable errors (rate limits, transient failures) → Auto-retry with backoff
   - Non-retryable errors (auth, permissions) → Clear error message + suggested fix

4. **Security**:
   - Service account authentication for API access
   - User identity from OpenShift OAuth token
   - RBAC enforcement (agent respects user permissions)
   - Audit logging for all operations

---

## Performance Considerations

### Latency Budget

Target: <2s total latency for simple queries

| Component | Budget | Optimization |
|-----------|--------|--------------|
| LLM inference | <1s | Local vLLM deployment, batching |
| Intent parsing | <200ms | Caching common intents |
| OpenShift API call | <200ms | Connection pooling |
| PostgreSQL query | <100ms | Indexed queries, connection pool |
| Network overhead | <500ms | On-cluster deployment |

### Scalability

- **Concurrent Users**: 100+ (target), PostgreSQL connection pooling
- **Conversations per User**: Unlimited (30-day retention)
- **Context Window**: 20 turns = ~8K tokens (Llama 3.3 supports 128K context)
- **API Rate Limiting**: 10 req/min per user to prevent runaway loops

---

## Security & Compliance

### Authentication Flow

```
User → OpenShift Web Console → OAuth Login
       ↓
User obtains OAuth token (valid for session)
       ↓
User sends token to Lightspeed Agent
       ↓
Agent validates token with OpenShift OAuth
       ↓
Agent uses Service Account Token for OpenShift AI API calls
       ↓
Agent respects User's RBAC permissions
```

### Audit Requirements

- **Immutable Logs**: Audit table append-only, no updates/deletes
- **Retention**: 90 days minimum (configurable)
- **Fields Logged**: user_id, command, intent, operation, result, errors, timestamp
- **Access Control**: Audit logs readable only by admins

---

## Testing Strategy

### Unit Tests (≥80% coverage)

- Intent parser: Natural language → Intent object mapping
- Operation executor: Intent → API call translation
- Conversation manager: Context window management
- Error handlers: API error → User message transformation

### Integration Tests

- OpenShift AI API calls with test cluster
- PostgreSQL conversation persistence
- LLM intent parsing with test prompts
- OAuth authentication flow

### Contract Tests

- Conversation API request/response schemas
- OpenShift AI operation contracts
- Webhook contracts (if async operations)

---

## Open Questions for Phase 1

1. **Conversation Interface**: REST API, WebSocket, or both?
   - Decision needed for quickstart.md and contracts/

2. **Async Operation Handling**: Polling, webhooks, or server-sent events?
   - Required for long-running operations (model deployment takes minutes)

3. **Multi-tenancy**: Per-namespace or cluster-wide deployment?
   - Impacts RBAC configuration and resource isolation

These will be resolved during Phase 1 design.

---

## References

- [Lightspeed Core Stack GitHub](https://github.com/lightspeed-core/lightspeed-stack/)
- [OpenShift REST Client Python](https://github.com/openshift/openshift-restclient-python)
- [KServe Python SDK](https://pypi.org/project/kserve/)
- [Kubeflow Pipelines SDK v2](https://pypi.org/project/kfp/)
- [Model Registry Python Client](https://pypi.org/project/model-registry/)
- [Red Hat OpenShift AI Documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_cloud_service/1)
- [OpenShift OAuth Documentation](https://docs.openshift.com/container-platform/4.9/authentication/using-service-accounts-as-oauth-client.html)
