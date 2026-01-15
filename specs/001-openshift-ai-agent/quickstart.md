# Quick Start Guide: OpenShift AI Conversational Agent

**Last Updated**: 2026-01-14
**Target Audience**: Developers and data scientists who want to get started quickly

## Prerequisites

Before you begin, ensure you have:

1. **OpenShift Cluster Access**
   - Active OpenShift cluster with OpenShift AI installed
   - User account with at least `edit` role in a project/namespace
   - `oc` CLI tool installed and configured

2. **Development Environment**
   - Python 3.12 installed
   - `uv` package manager installed ([installation guide](https://github.com/astral-sh/uv#installation))
   - Git for cloning the repository

3. **OpenShift AI Resources**
   - At least one project/namespace where you can deploy models
   - Optional: Existing models to test deployment commands

4. **Authentication**
   - OpenShift OAuth token (obtain with: `oc whoami --show-token`)

---

## 5-Minute Setup

### Step 1: Clone and Initialize Project

```bash
# Clone the repository
git clone https://github.com/your-org/openshift-ai-agent.git
cd openshift-ai-agent

# Initialize uv virtual environment with Python 3.12
uv venv --python 3.12
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
uv pip install -e ".[dev]"
```

### Step 2: Configure Agent

Create a configuration file `lightspeed-stack.yaml`:

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

# Rate Limiting
rate_limit:
  requests_per_minute: 10
  burst_size: 5

# Logging
logging:
  level: "INFO"
  format: "json"
  audit_enabled: true
```

Set environment variables:

```bash
export DATABASE_URL="postgresql://user:pass@localhost:5432/openshift_ai_agent"
export OPENSHIFT_API_URL="https://api.your-cluster.example.com:6443"
export OLS_CONFIG_FILE="./lightspeed-stack.yaml"
```

### Step 3: Set Up PostgreSQL Database

```bash
# Using Docker/Podman for local development
podman run -d \
  --name openshift-ai-agent-db \
  -e POSTGRES_USER=agent \
  -e POSTGRES_PASSWORD=devpass \
  -e POSTGRES_DB=openshift_ai_agent \
  -p 5432:5432 \
  postgres:15

# Run database migrations
uv run alembic upgrade head
```

### Step 4: Start the Agent

```bash
# Development mode with auto-reload
uv run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8080

# Production mode
uv run gunicorn src.api.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8080
```

### Step 5: Test the Agent

```bash
# Get your OpenShift OAuth token
export OS_TOKEN=$(oc whoami --show-token)

# Create a conversation session
curl -X POST http://localhost:8080/v1/sessions \
  -H "Authorization: Bearer $OS_TOKEN" \
  -H "Content-Type: application/json"

# Send a query (replace SESSION_ID with response from above)
curl -X POST http://localhost:8080/v1/query \
  -H "Authorization: Bearer $OS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "query": "List all my deployed models"
  }'
```

Expected response:

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "message_id": "123e4567-e89b-12d3-a456-426614174000",
  "response": "You have 3 deployed models:\n\n1. fraud-detection (3 replicas, Status: Running)\n2. sentiment-analysis (2 replicas, Status: Running)\n3. recommendation-engine (5 replicas, Status: Running)\n\nAll models are healthy and accepting traffic.",
  "operations_performed": [
    {
      "operation_type": "list",
      "resource_type": "model_deployment",
      "status": "success",
      "execution_time_ms": 234
    }
  ]
}
```

---

## Common Operations

### Deploy a Model

```bash
curl -X POST http://localhost:8080/v1/query \
  -H "Authorization: Bearer $OS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "query": "Deploy my customer-churn model with 2 replicas in the ml-models namespace"
  }'
```

### Check Model Status

```bash
curl -X POST http://localhost:8080/v1/query \
  -H "Authorization: Bearer $OS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "query": "What's the status of fraud-detection model?"
  }'
```

### Scale a Model

```bash
# This requires confirmation
curl -X POST http://localhost:8080/v1/query \
  -H "Authorization: Bearer $OS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "query": "Scale sentiment-analysis to 5 replicas"
  }'

# Response will include pending_operation_id
# Confirm with:
curl -X POST http://localhost:8080/v1/confirm/{operation_id} \
  -H "Authorization: Bearer $OS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"action": "confirm"}'
```

### Create a Notebook

```bash
curl -X POST http://localhost:8080/v1/query \
  -H "Authorization: Bearer $OS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "query": "Create a Python notebook with TensorFlow and 8GB memory"
  }'
```

### Troubleshoot a Model

```bash
curl -X POST http://localhost:8080/v1/query \
  -H "Authorization: Bearer $OS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "550e8400-e29b-41d4-a716-446655440000",
    "query": "Why is my fraud-detector showing high latency?"
  }'
```

---

## Project Structure

```
openshift-ai-agent/
├── src/
│   ├── agent/                  # Agent implementation
│   │   ├── conversation/       # lightspeed-stack integration
│   │   ├── intent/             # Intent parsing
│   │   └── operations/         # OpenShift AI operations
│   ├── models/                 # Pydantic data models
│   ├── services/               # Business logic
│   ├── api/                    # FastAPI routes
│   └── cli/                    # CLI interface
├── tests/
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   └── contract/               # Contract tests
├── pyproject.toml              # uv project config
├── uv.lock                     # Locked dependencies
├── lightspeed-stack.yaml       # Agent configuration
└── alembic/                    # Database migrations
```

---

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/add-pipeline-support
```

### 2. Write Tests First (TDD)

```bash
# Create failing test
cat > tests/unit/test_pipeline_operations.py <<EOF
def test_create_pipeline_intent():
    """Test parsing create pipeline command"""
    result = parse_intent("Create a pipeline to load data from S3")
    assert result.action_type == ActionType.CREATE_PIPELINE
    assert "S3" in result.parameters
EOF

# Run tests (should fail)
uv run pytest tests/unit/test_pipeline_operations.py -v
```

### 3. Implement Feature

```python
# src/services/intent_parser.py
def parse_pipeline_creation(query: str, llm_client) -> UserIntent:
    # Implementation here
    pass
```

### 4. Run Tests (should pass)

```bash
uv run pytest tests/unit/test_pipeline_operations.py -v
```

### 5. Run All Tests + Coverage

```bash
# Run all tests with coverage
uv run pytest --cov=src --cov-report=term-missing

# Verify coverage ≥80%
uv run pytest --cov=src --cov-fail-under=80
```

### 6. Lint and Format

```bash
# Format code
uv run ruff format src/ tests/

# Lint code
uv run ruff check src/ tests/ --fix

# Type checking
uv run mypy src/
```

### 7. Commit and Push

```bash
git add .
git commit -m "feat: add pipeline creation support"
git push origin feature/add-pipeline-support
```

---

## Deployment to OpenShift

### Option 1: Helm Chart (Recommended)

```bash
# Create helm values file
cat > values.yaml <<EOF
image:
  repository: quay.io/your-org/openshift-ai-agent
  tag: "1.0.0"

env:
  DATABASE_URL: "postgresql://user:pass@postgres:5432/agent"
  OPENSHIFT_API_URL: "https://kubernetes.default.svc"

resources:
  requests:
    memory: "512Mi"
    cpu: "250m"
  limits:
    memory: "2Gi"
    cpu: "1000m"

autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
EOF

# Deploy with Helm
helm install openshift-ai-agent ./helm \
  -f values.yaml \
  --namespace openshift-ai \
  --create-namespace
```

### Option 2: OpenShift Templates

```bash
# Process and apply template
oc process -f openshift/template.yaml \
  -p DATABASE_URL="postgresql://..." \
  -p IMAGE_TAG="1.0.0" \
  | oc apply -f -

# Verify deployment
oc get pods -n openshift-ai
oc logs -f deployment/openshift-ai-agent
```

### Option 3: Kubernetes Manifests

```bash
# Apply manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/route.yaml
```

---

## Configuration Options

### LLM Provider Options

```yaml
# OpenAI (cloud)
providers:
  inference:
    - name: "openai"
      type: "openai"
      api_key: "${env.OPENAI_API_KEY}"
      model: "gpt-4o"

# Azure OpenAI
providers:
  inference:
    - name: "azure"
      type: "azure"
      api_key: "${env.AZURE_OPENAI_KEY}"
      endpoint: "https://your-resource.openai.azure.com"
      model: "gpt-4.1"

# vLLM on OpenShift AI (recommended)
providers:
  inference:
    - name: "rhoai-vllm"
      type: "vllm"
      base_url: "http://vllm-inference:8000"
      model: "meta-llama/Llama-3.3-70B-Instruct"
```

### Database Options

```yaml
# PostgreSQL (production)
chat_history:
  storage_type: "postgresql"
  connection_string: "postgresql://user:pass@host:5432/db"

# SQLite (development only)
chat_history:
  storage_type: "sqlite"
  database_path: "./data/conversations.db"
```

### Rate Limiting

```yaml
rate_limit:
  requests_per_minute: 10  # Per user
  burst_size: 5            # Allow bursts
  cleanup_interval: 60     # Seconds
```

---

## Troubleshooting

### Agent won't start

**Symptom**: `uvicorn` fails to start
**Solution**: Check configuration file and environment variables

```bash
# Validate configuration
uv run python -c "import yaml; yaml.safe_load(open('lightspeed-stack.yaml'))"

# Check environment variables
env | grep -E "(DATABASE_URL|OPENSHIFT_API_URL|OLS_CONFIG_FILE)"
```

### Can't connect to OpenShift API

**Symptom**: "Connection refused" or "Unauthorized" errors
**Solution**: Verify OpenShift authentication

```bash
# Test oc CLI connectivity
oc whoami
oc get projects

# Verify service account token (in-cluster)
cat /var/run/secrets/kubernetes.io/serviceaccount/token
```

### Database connection errors

**Symptom**: "Could not connect to database"
**Solution**: Check PostgreSQL connectivity and credentials

```bash
# Test database connection
psql "$DATABASE_URL" -c "SELECT 1"

# Check if database exists
psql "$DATABASE_URL" -c "\l"

# Run migrations
uv run alembic upgrade head
```

### Low accuracy in intent parsing

**Symptom**: Agent misinterprets commands
**Solution**: Check LLM configuration and prompts

```bash
# Test LLM connectivity
curl http://llm-endpoint:8000/v1/models

# Check system prompts in configuration
cat lightspeed-stack.yaml | grep -A 10 "system_prompt"
```

---

## Next Steps

### For Development

1. **Read the full implementation plan**: `specs/001-openshift-ai-agent/plan.md`
2. **Review data models**: `specs/001-openshift-ai-agent/data-model.md`
3. **Check API contracts**: `specs/001-openshift-ai-agent/contracts/`
4. **Run task breakdown**: `/speckit.tasks` to generate implementation tasks

### For Production Deployment

1. **Security hardening**:
   - Enable TLS for API endpoints
   - Configure proper RBAC for service accounts
   - Enable audit logging
   - Set up network policies

2. **Monitoring**:
   - Configure Prometheus metrics
   - Set up Grafana dashboards
   - Enable alerting for errors and latency

3. **High Availability**:
   - Deploy multiple replicas (minimum 2)
   - Configure pod disruption budgets
   - Set up autoscaling based on load

4. **Backup & Recovery**:
   - Configure PostgreSQL backups
   - Test disaster recovery procedures
   - Document rollback procedures

---

## Additional Resources

- **Lightspeed Stack Documentation**: https://github.com/lightspeed-core/lightspeed-stack/
- **OpenShift AI Documentation**: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_cloud_service/1
- **KServe Documentation**: https://kserve.github.io/website/
- **Kubeflow Pipelines**: https://www.kubeflow.org/docs/components/pipelines/

---

## Support

For issues, questions, or contributions:

- **GitHub Issues**: https://github.com/your-org/openshift-ai-agent/issues
- **Slack**: #openshift-ai-agent
- **Email**: openshift-ai-agent@your-org.com
