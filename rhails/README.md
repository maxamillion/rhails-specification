# OpenShift AI Conversational Agent

A conversational AI agent that enables users to command and control OpenShift AI through natural language instead of the web dashboard. Built on the [Lightspeed Core lightspeed-stack](https://github.com/lightspeed-core/lightspeed-stack/) framework.

## Overview

This agent translates natural language conversations into OpenShift AI API operations, covering:
- **Model Management**: Deploy, scale, monitor ML models
- **Pipeline Configuration**: Create and manage data pipelines
- **Notebook Management**: Provision Jupyter environments
- **Project Administration**: Manage resources, permissions, quotas
- **Monitoring & Troubleshooting**: Diagnose performance issues

## Quick Start

See [quickstart.md](../specs/001-openshift-ai-agent/quickstart.md) for detailed setup instructions.

### Prerequisites

- Python 3.12
- `uv` package manager ([installation guide](https://github.com/astral-sh/uv#installation))
- OpenShift cluster with OpenShift AI installed
- `oc` CLI tool configured
- PostgreSQL 15+ database

### Installation

```bash
# Clone repository
git clone <repository-url>
cd rhails

# Initialize uv virtual environment
uv venv --python 3.12
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
uv pip install -e ".[dev]"
```

### Configuration

1. Create `lightspeed-stack.yaml` configuration file:

```yaml
# LLM Provider Configuration
providers:
  inference:
    - name: "openshift-ai-llm"
      type: "vllm"
      base_url: "https://llama-inference.openshift-ai.svc.cluster.local:8000"
      model: "meta-llama/Llama-3.3-70B-Instruct"
      tool_calling: true

# Conversation Storage
chat_history:
  storage_type: "postgresql"
  connection_string: "${env.DATABASE_URL}"
  max_conversation_length: 20

# OpenShift Integration
openshift:
  api_url: "${env.OPENSHIFT_API_URL}"
  auth:
    type: "service_account"
    token_path: "/var/run/secrets/kubernetes.io/serviceaccount/token"
```

2. Set environment variables:

```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/openshift_ai_agent"
export OPENSHIFT_API_URL="https://api.your-cluster.example.com:6443"
export OLS_CONFIG_FILE="./lightspeed-stack.yaml"
```

3. Run database migrations:

```bash
uv run alembic upgrade head
```

### Running the Agent

```bash
# Development mode with auto-reload
uv run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8080

# Production mode
uv run gunicorn src.api.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8080
```

## Development

### Test-Driven Development (TDD)

This project follows strict TDD per our [constitution](../.specify/memory/constitution.md):

1. **Red**: Write failing tests first
2. **User Approval**: Present tests for validation
3. **Verify Failure**: Confirm tests fail for the right reasons
4. **Green**: Implement minimal code to pass tests
5. **Refactor**: Improve code quality while maintaining test passage

### Running Tests

```bash
# Run all tests with coverage
uv run pytest --cov=src --cov-report=term-missing

# Run specific test types
uv run pytest -m unit              # Unit tests only
uv run pytest -m integration       # Integration tests only
uv run pytest -m contract          # Contract tests only

# Verify coverage threshold (≥80%)
uv run pytest --cov=src --cov-fail-under=80
```

### Code Quality

```bash
# Format code
uv run ruff format src/ tests/

# Lint code
uv run ruff check src/ tests/ --fix

# Type checking
uv run mypy src/
```

## Deployment

### Container Deployment

Build and run the containerized application:

```bash
# Build Docker image
docker build -t openshift-ai-agent:0.1.0 .

# Run container
docker run -d \
  --name openshift-ai-agent \
  -p 8000:8000 \
  -e DATABASE_URL="postgresql+asyncpg://user:pass@db:5432/openshift_ai_agent" \
  -e OAUTH_PROVIDER_URL="https://oauth-openshift.apps.cluster.example.com" \
  -e OAUTH_CLIENT_ID="openshift-ai-agent" \
  -e OAUTH_CLIENT_SECRET="your-secret" \
  -e OPENSHIFT_AI_API_URL="https://api.openshift.com" \
  -e LLM_PROVIDER="openai" \
  -e LLM_API_KEY="your-api-key" \
  openshift-ai-agent:0.1.0
```

### OpenShift Deployment with Helm

Deploy to OpenShift using the Helm chart:

```bash
# Add required secrets
kubectl create secret generic postgresql-credentials \
  --from-literal=username=dbuser \
  --from-literal=password=dbpassword

kubectl create secret generic oauth-credentials \
  --from-literal=client-secret=your-oauth-secret

kubectl create secret generic llm-credentials \
  --from-literal=api-key=your-llm-api-key

# Install the Helm chart
helm install openshift-ai-agent ./helm/openshift-ai-agent \
  --namespace openshift-ai \
  --create-namespace \
  --set image.repository=quay.io/your-org/openshift-ai-agent \
  --set image.tag=0.1.0 \
  --set oauth.providerUrl=https://oauth-openshift.apps.cluster.example.com \
  --set openshiftAI.apiUrl=https://api.openshift.com

# Verify deployment
kubectl get pods -n openshift-ai
kubectl get route -n openshift-ai
```

### Configuration Options

Key Helm chart values:

| Parameter | Description | Default |
|-----------|-------------|---------|
| `replicaCount` | Number of pod replicas | `2` |
| `image.repository` | Container image repository | `quay.io/openshift-ai/conversational-agent` |
| `image.tag` | Container image tag | `0.1.0` |
| `resources.limits.cpu` | CPU resource limit | `1000m` |
| `resources.limits.memory` | Memory resource limit | `1Gi` |
| `autoscaling.enabled` | Enable horizontal pod autoscaling | `true` |
| `autoscaling.minReplicas` | Minimum number of replicas | `2` |
| `autoscaling.maxReplicas` | Maximum number of replicas | `10` |
| `database.host` | PostgreSQL database host | `postgresql` |
| `oauth.clientId` | OAuth client ID | `openshift-ai-agent` |
| `llm.provider` | LLM provider (openai/azure/anthropic) | `openai` |
| `app.logLevel` | Application log level | `INFO` |

See [values.yaml](helm/openshift-ai-agent/values.yaml) for complete configuration options.

### Health Monitoring

The application exposes health check endpoints:

```bash
# Liveness probe
curl http://localhost:8000/health

# Readiness probe
curl http://localhost:8000/health/ready
```

Expected response: `{"status": "healthy", "timestamp": "2026-01-15T12:00:00Z"}`

## Architecture

See [plan.md](../specs/001-openshift-ai-agent/plan.md) for complete architecture details.

### Project Structure

```
rhails/
├── src/
│   ├── agent/               # Main agent implementation
│   │   ├── conversation/    # Conversation management
│   │   ├── intent/          # Intent parsing
│   │   ├── operations/      # OpenShift AI operations
│   │   └── auth/            # Authentication
│   ├── models/              # Pydantic data models
│   ├── services/            # Business logic services
│   ├── api/                 # FastAPI routes and middleware
│   └── cli/                 # CLI interface
├── tests/
│   ├── unit/                # Unit tests
│   ├── integration/         # Integration tests
│   └── contract/            # Contract tests
├── alembic/                 # Database migrations
├── pyproject.toml           # Project configuration
├── lightspeed-stack.yaml    # Agent configuration
└── README.md                # This file
```

## Documentation

- [Feature Specification](../specs/001-openshift-ai-agent/spec.md) - User stories and requirements
- [Implementation Plan](../specs/001-openshift-ai-agent/plan.md) - Technical architecture
- [Data Model](../specs/001-openshift-ai-agent/data-model.md) - Entity relationships
- [API Contracts](../specs/001-openshift-ai-agent/contracts/) - API specifications
- [Research](../specs/001-openshift-ai-agent/research.md) - Technical decisions
- [Quickstart Guide](../specs/001-openshift-ai-agent/quickstart.md) - Developer onboarding

## License

Apache-2.0

## Contributing

This project follows strict quality standards defined in our [constitution](../.specify/memory/constitution.md):

1. **Code Quality First**: SOLID principles, DRY, maintainability
2. **Test-First Development (NON-NEGOTIABLE)**: TDD cycle strictly enforced
3. **User Experience Consistency**: Clear feedback, actionable errors
4. **Performance as a Feature**: <2s queries, <10s complex operations

See [tasks.md](../specs/001-openshift-ai-agent/tasks.md) for implementation roadmap.
