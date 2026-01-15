# Tasks: OpenShift AI Conversational Agent

**Input**: Design documents from `/specs/001-openshift-ai-agent/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), data-model.md, contracts/, research.md, quickstart.md

**Tests**: Tests are REQUIRED per Constitution Principle II (Test-First Development is NON-NEGOTIABLE). TDD cycle strictly enforced: Red → User Approval → Green → Refactor.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/`, `tests/` at repository root
- Paths shown below are absolute based on plan.md structure

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create .python-version file specifying Python 3.12
- [X] T002 Create pyproject.toml with uv configuration and core dependencies (lightspeed-stack>=0.3.0, openshift>=0.13.0, kserve>=0.14.0, kfp>=2.8.0, model-registry>=0.2.0)
- [X] T003 [P] Initialize uv virtual environment with Python 3.12
- [X] T004 [P] Create src/ directory structure (agent/, models/, services/, api/, cli/)
- [X] T005 [P] Create tests/ directory structure (unit/, integration/, contract/)
- [X] T006 [P] Create pytest.ini with pytest configuration and asyncio mode
- [X] T007 [P] Create .gitignore for Python project (venv, __pycache__, .pytest_cache, uv.lock)
- [X] T008 Create README.md with project overview and quickstart reference
- [X] T009 [P] Create alembic/ directory for database migrations
- [X] T010 [P] Create lightspeed-stack.yaml configuration file template

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Database Foundation

- [X] T011 Create alembic.ini for database migration configuration
- [X] T012 Create initial Alembic migration for conversation_sessions table in alembic/versions/
- [X] T013 Create Alembic migration for messages table in alembic/versions/
- [X] T014 Create Alembic migration for user_intents table in alembic/versions/
- [X] T015 Create Alembic migration for operation_requests table in alembic/versions/
- [X] T016 Create Alembic migration for execution_results table in alembic/versions/
- [X] T017 Create Alembic migration for audit_logs table in alembic/versions/

### Core Data Models (Pydantic Schemas)

- [X] T018 [P] Create ConversationSession Pydantic model in src/models/conversation.py
- [X] T019 [P] Create Message Pydantic model in src/models/conversation.py
- [X] T020 [P] Create UserIntent and ActionType enum in src/models/intent.py
- [X] T021 [P] Create OperationRequest Pydantic model in src/models/intent.py
- [X] T022 [P] Create ExecutionResult Pydantic model in src/models/intent.py
- [X] T023 [P] Create ResourceReference and ResourceType enum in src/models/openshift.py
- [X] T024 [P] Create AuditLogEntry Pydantic model in src/models/conversation.py

### Core Services Foundation

- [X] T025 Create database connection manager in src/services/database.py
- [X] T026 Create OpenShift API client wrapper in src/services/openshift_client.py
- [X] T027 Create LLM client wrapper (lightspeed-stack integration) in src/agent/conversation/llm_client.py
- [X] T028 Create conversation session manager in src/agent/conversation/session_manager.py
- [X] T029 Create audit logging service in src/services/audit_logger.py

### Authentication & Authorization

- [X] T030 Create OpenShift OAuth token validator in src/agent/auth/oauth_validator.py
- [X] T031 Create RBAC permission checker in src/agent/auth/rbac_checker.py
- [X] T032 Create authentication middleware in src/api/middleware/auth.py

### API Foundation

- [X] T033 Create FastAPI application setup in src/api/main.py
- [X] T034 Create health check endpoints (/v1/readiness, /v1/liveness) in src/api/routes/health.py
- [X] T035 Create error handlers and exception middleware in src/api/middleware/error_handler.py
- [X] T036 Create rate limiting middleware in src/api/middleware/rate_limiter.py
- [X] T037 Create logging middleware with structured JSON logging in src/api/middleware/logging.py

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Model Management via Chat (Priority: P1) 🎯 MVP

**Goal**: Enable users to deploy, manage, and monitor ML models through natural language

**Independent Test**: Deploy a model through chat ("Deploy my sentiment-analysis model with 2 replicas") and verify it appears in OpenShift AI dashboard with correct configuration

### Tests for User Story 1 (TDD - Write First) ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T038 [P] [US1] Write contract test for /v1/query endpoint (model deployment) in tests/contract/test_conversation_contract.py
- [X] T039 [P] [US1] Write contract test for /v1/query endpoint (model status query) in tests/contract/test_conversation_contract.py
- [X] T040 [P] [US1] Write integration test for deploy_model operation in tests/integration/test_model_operations.py
- [X] T041 [P] [US1] Write integration test for get_model_status operation in tests/integration/test_model_operations.py
- [X] T042 [P] [US1] Write integration test for list_models operation in tests/integration/test_model_operations.py
- [X] T043 [P] [US1] Write integration test for scale_model operation in tests/integration/test_model_operations.py
- [X] T044 [P] [US1] Write integration test for delete_model operation in tests/integration/test_model_operations.py
- [X] T045 [P] [US1] Write unit test for model deployment intent parsing in tests/unit/test_intent_parser.py
- [X] T046 [P] [US1] Write unit test for model query intent parsing in tests/unit/test_intent_parser.py
- [X] T047 [P] [US1] Write unit test for model operation executor in tests/unit/test_operation_executor.py

### Implementation for User Story 1

- [X] T048 [P] [US1] Implement intent parser for model deployment commands in src/services/intent_parser.py
- [X] T049 [P] [US1] Implement intent parser for model query commands in src/services/intent_parser.py
- [X] T050 [US1] Implement model deployment operation executor in src/agent/operations/model_operations.py (depends on T048)
- [X] T051 [US1] Implement model query operation executor in src/agent/operations/model_operations.py (depends on T049)
- [X] T052 [US1] Implement model scaling operation executor in src/agent/operations/model_operations.py (depends on T048)
- [X] T053 [US1] Implement model deletion operation executor in src/agent/operations/model_operations.py (depends on T048)
- [X] T054 [US1] Create /v1/query POST endpoint for conversation queries in src/api/routes/query.py
- [X] T055 [US1] Create /v1/sessions POST endpoint for session creation in src/api/routes/sessions.py
- [X] T056 [US1] Add confirmation flow for destructive operations (scale, delete) in src/api/routes/confirm.py
- [X] T057 [US1] Implement user-friendly error message translation for OpenShift API errors in src/services/error_translator.py
- [X] T058 [US1] Add audit logging for all model operations in src/agent/operations/model_operations.py
- [ ] T059 [US1] Run all User Story 1 tests and verify they pass

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently

---

## Phase 4: User Story 2 - Data Pipeline Configuration (Priority: P2)

**Goal**: Enable users to configure and monitor data pipelines through natural language

**Independent Test**: Create a pipeline through chat ("Create a pipeline to preprocess customer reviews from S3") and verify it appears in dashboard

### Tests for User Story 2 (TDD - Write First) ⚠️

- [ ] T060 [P] [US2] Write contract test for pipeline creation in tests/contract/test_conversation_contract.py
- [ ] T061 [P] [US2] Write integration test for create_pipeline operation in tests/integration/test_pipeline_operations.py
- [ ] T062 [P] [US2] Write integration test for get_pipeline_status operation in tests/integration/test_pipeline_operations.py
- [ ] T063 [P] [US2] Write integration test for list_pipelines operation in tests/integration/test_pipeline_operations.py
- [ ] T064 [P] [US2] Write integration test for update_pipeline_schedule operation in tests/integration/test_pipeline_operations.py
- [ ] T065 [P] [US2] Write integration test for get_pipeline_runs operation in tests/integration/test_pipeline_operations.py
- [ ] T066 [P] [US2] Write unit test for pipeline intent parsing in tests/unit/test_intent_parser.py

### Implementation for User Story 2

- [ ] T067 [P] [US2] Implement intent parser for pipeline creation commands in src/services/intent_parser.py
- [ ] T068 [P] [US2] Implement intent parser for pipeline query commands in src/services/intent_parser.py
- [ ] T069 [US2] Implement pipeline creation operation executor in src/agent/operations/pipeline_operations.py (depends on T067)
- [ ] T070 [US2] Implement pipeline query operation executor in src/agent/operations/pipeline_operations.py (depends on T068)
- [ ] T071 [US2] Implement pipeline schedule update operation executor in src/agent/operations/pipeline_operations.py (depends on T067)
- [ ] T072 [US2] Implement pipeline run history retrieval in src/agent/operations/pipeline_operations.py (depends on T068)
- [ ] T073 [US2] Add pipeline operations to /v1/query endpoint in src/api/routes/query.py
- [ ] T074 [US2] Add audit logging for all pipeline operations in src/agent/operations/pipeline_operations.py
- [ ] T075 [US2] Run all User Story 2 tests and verify they pass

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently

---

## Phase 5: User Story 3 - Notebook Environment Management (Priority: P3)

**Goal**: Enable users to create, configure, and manage Jupyter notebooks through natural language

**Independent Test**: Create a notebook through chat ("Create a Python notebook with TensorFlow and 4GB RAM") and verify it launches with correct config

### Tests for User Story 3 (TDD - Write First) ⚠️

- [ ] T076 [P] [US3] Write contract test for notebook creation in tests/contract/test_conversation_contract.py
- [ ] T077 [P] [US3] Write integration test for create_notebook operation in tests/integration/test_notebook_operations.py
- [ ] T078 [P] [US3] Write integration test for list_notebooks operation in tests/integration/test_notebook_operations.py
- [ ] T079 [P] [US3] Write integration test for stop_notebook operation in tests/integration/test_notebook_operations.py
- [ ] T080 [P] [US3] Write integration test for start_notebook operation in tests/integration/test_notebook_operations.py
- [ ] T081 [P] [US3] Write integration test for delete_notebook operation in tests/integration/test_notebook_operations.py
- [ ] T082 [P] [US3] Write unit test for notebook intent parsing in tests/unit/test_intent_parser.py

### Implementation for User Story 3

- [ ] T083 [P] [US3] Implement intent parser for notebook creation commands in src/services/intent_parser.py
- [ ] T084 [P] [US3] Implement intent parser for notebook query commands in src/services/intent_parser.py
- [ ] T085 [US3] Implement notebook creation operation executor in src/agent/operations/notebook_operations.py (depends on T083)
- [ ] T086 [US3] Implement notebook query operation executor in src/agent/operations/notebook_operations.py (depends on T084)
- [ ] T087 [US3] Implement notebook stop/start operation executor in src/agent/operations/notebook_operations.py (depends on T083)
- [ ] T088 [US3] Implement notebook deletion operation executor in src/agent/operations/notebook_operations.py (depends on T083)
- [ ] T089 [US3] Add notebook operations to /v1/query endpoint in src/api/routes/query.py
- [ ] T090 [US3] Add confirmation flow for notebook deletion in src/api/routes/confirm.py
- [ ] T091 [US3] Add audit logging for all notebook operations in src/agent/operations/notebook_operations.py
- [ ] T092 [US3] Run all User Story 3 tests and verify they pass

**Checkpoint**: At this point, User Stories 1, 2, AND 3 should all work independently

---

## Phase 6: User Story 4 - Project and Resource Management (Priority: P4)

**Goal**: Enable team leads to manage projects, permissions, and quotas through natural language

**Independent Test**: Create a project through chat ("Create a project called fraud-detection-team with 32GB memory quota") and verify it exists with correct limits

### Tests for User Story 4 (TDD - Write First) ⚠️

- [ ] T093 [P] [US4] Write contract test for project creation in tests/contract/test_conversation_contract.py
- [ ] T094 [P] [US4] Write integration test for create_project operation in tests/integration/test_project_operations.py
- [ ] T095 [P] [US4] Write integration test for list_projects operation in tests/integration/test_project_operations.py
- [ ] T096 [P] [US4] Write integration test for get_project_resources operation in tests/integration/test_project_operations.py
- [ ] T097 [P] [US4] Write integration test for add_user_to_project operation in tests/integration/test_project_operations.py
- [ ] T098 [P] [US4] Write unit test for project intent parsing in tests/unit/test_intent_parser.py

### Implementation for User Story 4

- [ ] T099 [P] [US4] Implement intent parser for project creation commands in src/services/intent_parser.py
- [ ] T100 [P] [US4] Implement intent parser for project query commands in src/services/intent_parser.py
- [ ] T101 [US4] Implement project creation operation executor in src/agent/operations/project_operations.py (depends on T099)
- [ ] T102 [US4] Implement project query operation executor in src/agent/operations/project_operations.py (depends on T100)
- [ ] T103 [US4] Implement resource quota query operation executor in src/agent/operations/project_operations.py (depends on T100)
- [ ] T104 [US4] Implement add user to project operation executor in src/agent/operations/project_operations.py (depends on T099)
- [ ] T105 [US4] Add project operations to /v1/query endpoint in src/api/routes/query.py
- [ ] T106 [US4] Add confirmation flow for user permission changes in src/api/routes/confirm.py
- [ ] T107 [US4] Add audit logging for all project operations in src/agent/operations/project_operations.py
- [ ] T108 [US4] Run all User Story 4 tests and verify they pass

**Checkpoint**: At this point, User Stories 1-4 should all work independently

---

## Phase 7: User Story 5 - Model Monitoring and Troubleshooting (Priority: P5)

**Goal**: Enable users to investigate issues and analyze performance through conversational troubleshooting

**Independent Test**: Ask diagnostic question ("Why is my sentiment-model showing high latency?") and verify agent provides relevant metrics and insights

### Tests for User Story 5 (TDD - Write First) ⚠️

- [ ] T109 [P] [US5] Write contract test for diagnostic queries in tests/contract/test_conversation_contract.py
- [ ] T110 [P] [US5] Write integration test for analyze_model_logs operation in tests/integration/test_monitoring_operations.py
- [ ] T111 [P] [US5] Write integration test for compare_model_metrics operation in tests/integration/test_monitoring_operations.py
- [ ] T112 [P] [US5] Write integration test for diagnose_performance operation in tests/integration/test_monitoring_operations.py
- [ ] T113 [P] [US5] Write integration test for get_prediction_distribution operation in tests/integration/test_monitoring_operations.py
- [ ] T114 [P] [US5] Write unit test for troubleshooting intent parsing in tests/unit/test_intent_parser.py

### Implementation for User Story 5

- [ ] T115 [P] [US5] Implement intent parser for diagnostic commands in src/services/intent_parser.py
- [ ] T116 [US5] Implement log analysis operation executor in src/agent/operations/monitoring_operations.py (depends on T115)
- [ ] T117 [US5] Implement metrics comparison operation executor in src/agent/operations/monitoring_operations.py (depends on T115)
- [ ] T118 [US5] Implement performance diagnosis operation executor in src/agent/operations/monitoring_operations.py (depends on T115)
- [ ] T119 [US5] Implement prediction distribution analysis in src/agent/operations/monitoring_operations.py (depends on T115)
- [ ] T120 [US5] Add monitoring operations to /v1/query endpoint in src/api/routes/query.py
- [ ] T121 [US5] Add LLM-powered root cause analysis in src/services/diagnostic_analyzer.py
- [ ] T122 [US5] Add audit logging for all monitoring operations in src/agent/operations/monitoring_operations.py
- [ ] T123 [US5] Run all User Story 5 tests and verify they pass

**Checkpoint**: All user stories should now be independently functional

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T124 [P] Add session management endpoints (GET /v1/sessions, GET /v1/sessions/{id}, PATCH /v1/sessions/{id}) in src/api/routes/sessions.py
- [ ] T125 [P] Add conversation history endpoint (GET /v1/sessions/{id}/history) in src/api/routes/sessions.py
- [ ] T126 [P] Add streaming query endpoint (POST /v1/streaming-query) with Server-Sent Events in src/api/routes/query.py
- [ ] T127 [P] Implement conversation context window management (20-turn limit) in src/agent/conversation/session_manager.py
- [ ] T128 [P] Implement session archival for conversations older than 30 days in src/services/session_cleanup.py
- [ ] T129 [P] Add performance monitoring and metrics export in src/api/middleware/metrics.py
- [ ] T130 [P] Create Dockerfile for containerized deployment
- [ ] T131 [P] Create Helm chart for OpenShift deployment in helm/
- [ ] T132 [P] Add comprehensive unit tests for conversation manager in tests/unit/test_conversation_manager.py
- [ ] T133 [P] Add comprehensive unit tests for error translator in tests/unit/test_error_translator.py
- [ ] T134 [P] Add comprehensive unit tests for audit logger in tests/unit/test_audit_logger.py
- [ ] T135 Run full test suite with coverage report (verify ≥80% coverage)
- [ ] T136 Run linting and type checking (ruff, mypy)
- [ ] T137 Performance testing: Verify <2s response time for queries
- [ ] T138 Performance testing: Verify <10s for complex multi-step operations
- [ ] T139 Load testing: Verify system handles 100+ concurrent conversations
- [ ] T140 Security testing: Verify RBAC enforcement and OAuth validation
- [ ] T141 [P] Update README.md with deployment instructions
- [ ] T142 [P] Create CONTRIBUTING.md with development workflow
- [ ] T143 Validate against quickstart.md scenarios

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3 → P4 → P5)
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Independent of US1
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Independent of US1/US2
- **User Story 4 (P4)**: Can start after Foundational (Phase 2) - Independent of US1/US2/US3
- **User Story 5 (P5)**: Can start after Foundational (Phase 2) - May reference US1 models but independently testable

### Within Each User Story

- Tests (TDD) MUST be written and FAIL before implementation
- Models before services (where applicable)
- Services before API endpoints
- Core implementation before integration
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel (T003-T010)
- All Foundational data model tasks (T018-T024) can run in parallel
- All tests for a user story marked [P] can run in parallel
- Once Foundational phase completes, all user stories can start in parallel (if team capacity allows)
- Different user stories can be worked on in parallel by different team members

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together (TDD - write first):
Task T038: "Write contract test for /v1/query endpoint (model deployment)"
Task T039: "Write contract test for /v1/query endpoint (model status query)"
Task T040: "Write integration test for deploy_model operation"
Task T041: "Write integration test for get_model_status operation"
Task T042: "Write integration test for list_models operation"
...

# Launch all intent parsers for User Story 1 together (after tests written):
Task T048: "Implement intent parser for model deployment commands"
Task T049: "Implement intent parser for model query commands"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T010)
2. Complete Phase 2: Foundational (T011-T037) - CRITICAL, blocks all stories
3. Complete Phase 3: User Story 1 (T038-T059)
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/demo if ready

**Estimated MVP Tasks**: 59 tasks (Setup + Foundational + US1)

### Incremental Delivery

1. Complete Setup + Foundational → Foundation ready
2. Add User Story 1 → Test independently → Deploy/Demo (MVP!)
3. Add User Story 2 → Test independently → Deploy/Demo
4. Add User Story 3 → Test independently → Deploy/Demo
5. Add User Story 4 → Test independently → Deploy/Demo
6. Add User Story 5 → Test independently → Deploy/Demo
7. Polish phase → Final production release

Each story adds value without breaking previous stories.

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together
2. Once Foundational is done:
   - Developer A: User Story 1 (T038-T059)
   - Developer B: User Story 2 (T060-T075)
   - Developer C: User Story 3 (T076-T092)
   - Developer D: User Story 4 (T093-T108)
   - Developer E: User Story 5 (T109-T123)
3. Stories complete and integrate independently
4. Team collaborates on Polish phase

---

## Notes

- **[P] tasks**: Different files, no dependencies - can run in parallel
- **[Story] label**: Maps task to specific user story for traceability
- **TDD Discipline**: Tests MUST be written first and fail before implementation (Constitutional requirement)
- **Each user story**: Independently completable and testable (can deploy US1 alone, then add US2, etc.)
- **Verify tests fail**: Before implementing, run tests to ensure they fail for the right reasons
- **Commit strategy**: Commit after each task or logical group
- **Stop at any checkpoint**: Validate story independently before proceeding
- **Avoid**: Vague tasks, same file conflicts, cross-story dependencies that break independence
- **Coverage target**: ≥80% unit test coverage per Constitution Principle II
- **Performance targets**: <2s queries, <10s complex operations per Success Criteria

---

## Task Summary

**Total Tasks**: 143

**Tasks by Phase**:
- Phase 1 (Setup): 10 tasks
- Phase 2 (Foundational): 27 tasks
- Phase 3 (US1 - Model Management): 22 tasks
- Phase 4 (US2 - Pipeline Configuration): 16 tasks
- Phase 5 (US3 - Notebook Management): 17 tasks
- Phase 6 (US4 - Project Management): 16 tasks
- Phase 7 (US5 - Monitoring): 15 tasks
- Phase 8 (Polish): 20 tasks

**Tests Generated**: 49 test tasks (contract + integration + unit) across all user stories

**Parallel Opportunities**: 62 tasks marked [P] (43% of total) can run concurrently

**MVP Scope** (Recommended): 59 tasks (Phase 1 + Phase 2 + Phase 3)

**Independent Test Criteria by Story**:
- US1: Deploy model via chat and verify in OpenShift AI dashboard
- US2: Create pipeline via chat and verify configuration
- US3: Create notebook via chat and verify launch with correct resources
- US4: Create project via chat and verify quotas/permissions
- US5: Ask diagnostic question and verify agent provides relevant insights
