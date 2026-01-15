# Implementation Plan: OpenShift AI Conversational Agent

**Branch**: `001-openshift-ai-agent` | **Date**: 2026-01-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-openshift-ai-agent/spec.md`

**Note**: This plan builds on the Lightspeed Core lightspeed-stack framework (https://github.com/lightspeed-core/lightspeed-stack/) using Python and the uv package manager. All development will be done in a uv-managed virtual environment.

## Summary

Build a conversational AI agent that allows users to command and control OpenShift AI through natural language instead of the web dashboard. The agent translates user conversations into OpenShift AI API operations, covering model deployment, pipeline configuration, notebook management, project administration, and monitoring. The system uses OpenShift OAuth for authentication and maintains persistent conversation history to enable context-aware interactions across sessions.

## Technical Context

**Language/Version**: Python 3.12 (lightspeed-stack requirement)
**Primary Dependencies**:
- lightspeed-stack >=0.3.0 (Lightspeed Core framework for AI agents)
- OpenShift AI vLLM (Llama 3.3-70B on-cluster LLM deployment)
- openshift >=0.13.0 (OpenShift/Kubernetes REST client)
- kserve >=0.14.0 (Model serving platform integration)
- kfp >=2.8.0 (Kubeflow Pipelines SDK v2 for OpenShift AI 2.16+)
- model-registry >=0.2.0 (Model lifecycle management)
- uv (package manager for dependency and virtual environment management)

**Storage**:
- Conversation persistence: PostgreSQL 15+ with conversation session tables
- Audit logs: PostgreSQL (structured audit logs) + file-based application logging

**Testing**: pytest with pytest-asyncio (Python standard)
**Target Platform**: Linux server (OpenShift-compatible containerized deployment)
**Project Type**: Single project (backend service with conversation interface)
**Performance Goals**:
- <2s response time for queries (per SC-005)
- <10s for multi-step operations excluding deployment time (per SC-006)
- Support 100+ concurrent conversations

**Constraints**:
- <200ms p95 API latency for OpenShift AI operations
- Conversation context retention for 20+ turns (per SC-009)
- 95% intent interpretation accuracy (per SC-002)

**Scale/Scope**:
- Support 100+ concurrent users initially
- Handle 1000+ OpenShift AI resources per user
- Maintain conversation history for 30 days

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Principle I: Code Quality First

**Status**: ✅ PASS

- Single Responsibility: Each component (intent parser, API client, conversation manager) has clear purpose
- DRY Principle: Lightspeed-stack framework provides conversation scaffolding to avoid duplication
- Maintainability: Python with type hints and clear module structure
- **No violations**

### Principle II: Test-First Development (NON-NEGOTIABLE)

**Status**: ✅ PASS - With Planning Requirements

- TDD cycle MUST be followed for all business logic
- Unit test coverage target: ≥80% for intent parsing, API operations, conversation logic
- Integration tests REQUIRED for OpenShift AI API interactions
- Contract tests REQUIRED for conversation interface
- **Action**: Phase 1 design MUST include test strategy and example test cases

### Principle III: User Experience Consistency

**Status**: ✅ PASS

- Consistent conversational patterns across all operations
- Clear feedback for all user actions (confirmations, progress, errors)
- Error messages MUST be actionable per constitutional requirements
- **Action**: Phase 1 MUST define conversation UX patterns and error handling templates

### Principle IV: Performance as a Feature

**Status**: ✅ PASS - Metrics Defined

- Response time targets defined in success criteria (<2s queries, <10s complex operations)
- Performance testing REQUIRED before deployment
- Monitoring MUST track conversation latency, API call performance, context retrieval time
- **Action**: Phase 1 MUST include performance monitoring strategy

### Summary

**Overall Status**: ✅ COMPLIANT

All constitutional principles can be met with this architecture. No violations requiring justification. Key dependencies for compliance:

1. TDD discipline throughout development
2. Performance monitoring from day one
3. Clear UX patterns for conversation design
4. Comprehensive test coverage (unit + integration + contract)

## Project Structure

### Documentation (this feature)

```text
specs/001-openshift-ai-agent/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   ├── conversation-api.yaml    # OpenAPI spec for conversation interface
│   └── openshift-ai-operations.yaml  # Operations supported by agent
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
# Single project structure (Python service)
src/
├── agent/                    # Main agent implementation
│   ├── conversation/         # Conversation management (lightspeed-stack integration)
│   ├── intent/               # Intent parsing and understanding
│   ├── operations/           # OpenShift AI operations
│   └── auth/                 # OpenShift OAuth integration
├── models/                   # Data models (Pydantic schemas)
│   ├── conversation.py       # Conversation session, messages
│   ├── intent.py             # User intent, operations
│   └── openshift.py          # OpenShift AI resource models
├── services/                 # Business logic services
│   ├── openshift_client.py   # OpenShift AI API client
│   ├── intent_parser.py      # Natural language → intent
│   └── operation_executor.py # Intent → API operations
├── api/                      # API layer (if REST/WebSocket interface)
│   ├── routes/               # API endpoints
│   └── middleware/           # Auth, logging, rate limiting
└── cli/                      # CLI interface (uv-managed)
    └── agent_cli.py          # Command-line conversation interface

tests/
├── contract/                 # Contract tests for conversation API
│   └── test_conversation_contract.py
├── integration/              # Integration tests with OpenShift AI
│   ├── test_model_operations.py
│   ├── test_pipeline_operations.py
│   └── test_notebook_operations.py
└── unit/                     # Unit tests (intent, parsing, logic)
    ├── test_intent_parser.py
    ├── test_operation_executor.py
    └── test_conversation_manager.py

# Configuration and deployment
pyproject.toml                # uv project configuration
uv.lock                       # uv lockfile for reproducible builds
.python-version               # Python version specification (3.12)
Dockerfile                    # Container image for deployment
```

**Structure Decision**: Single project structure chosen because this is a unified backend service without separate frontend/backend concerns. The lightspeed-stack framework provides conversation scaffolding, and all logic is Python-based. Project will be managed entirely through uv for dependency management and virtual environment isolation.

## Complexity Tracking

> No constitutional violations - this section is empty.
