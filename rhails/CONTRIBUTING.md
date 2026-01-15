# Contributing to OpenShift AI Conversational Agent

Thank you for your interest in contributing! This document provides guidelines for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Development Setup](#development-setup)
- [Development Workflow](#development-workflow)
- [Coding Standards](#coding-standards)
- [Testing Requirements](#testing-requirements)
- [Pull Request Process](#pull-request-process)
- [Architecture Guidelines](#architecture-guidelines)

## Code of Conduct

This project adheres to the principles outlined in our [constitution](../.specify/memory/constitution.md):

- **Code Quality First**: Write maintainable, well-documented code following SOLID principles
- **Test-First Development (NON-NEGOTIABLE)**: Follow TDD cycle strictly
- **User Experience Consistency**: Provide clear feedback and actionable error messages
- **Performance as a Feature**: Maintain <2s response times for queries

## Development Setup

### Prerequisites

- Python 3.12+
- `uv` package manager ([installation guide](https://github.com/astral-sh/uv#installation))
- PostgreSQL 15+ (for local testing)
- OpenShift cluster access (optional, for integration tests)
- Git

### Initial Setup

```bash
# Clone the repository
git clone <repository-url>
cd rhails

# Create virtual environment
uv venv --python 3.12
source .venv/bin/activate

# Install dependencies (including dev dependencies)
uv pip install -e ".[dev]"

# Set up pre-commit hooks (optional but recommended)
uv run pre-commit install

# Configure environment variables
cp .env.example .env
# Edit .env with your local configuration

# Run database migrations
uv run alembic upgrade head
```

## Development Workflow

### 1. Branch Strategy

- `main` - Production-ready code
- `develop` - Integration branch for features
- `feature/*` - New features and enhancements
- `bugfix/*` - Bug fixes
- `hotfix/*` - Urgent production fixes

### 2. Feature Development Process

```bash
# Create feature branch from develop
git checkout develop
git pull origin develop
git checkout -b feature/your-feature-name

# Make changes following TDD cycle (see below)
# ...

# Commit changes
git add .
git commit -m "feat: description of feature"

# Push to remote
git push origin feature/your-feature-name

# Create pull request targeting develop
```

### 3. Test-Driven Development (TDD) Cycle

This is **NON-NEGOTIABLE** per our constitution:

```
1. RED: Write failing tests first
   └─> uv run pytest tests/unit/test_your_feature.py -v

2. VERIFY: Confirm tests fail for the right reasons
   └─> Read test output carefully

3. GREEN: Implement minimal code to pass tests
   └─> Write only enough code to make tests pass

4. REFACTOR: Improve code quality
   └─> Maintain test passage while improving design

5. REPEAT: For each new requirement
```

**Example TDD Session**:

```python
# Step 1: Write failing test (RED)
# tests/unit/test_intent_parser.py
async def test_parse_deploy_model_intent():
    parser = IntentParser()
    intent = await parser.parse_intent("Deploy my fraud-detection model")

    assert intent.action_type == ActionType.DEPLOY_MODEL
    assert "fraud-detection" in intent.parameters["model_name"]
    assert intent.confidence >= 0.8

# Step 2: Run test and verify failure
# $ uv run pytest tests/unit/test_intent_parser.py::test_parse_deploy_model_intent -v
# Expected: FAILED (NotImplementedError or assertion failure)

# Step 3: Implement feature (GREEN)
# src/services/intent_parser.py
class IntentParser:
    async def parse_intent(self, query: str) -> UserIntent:
        if "deploy" in query.lower():
            # Extract model name...
            return UserIntent(action_type=ActionType.DEPLOY_MODEL, ...)

# Step 4: Run test and verify passage
# $ uv run pytest tests/unit/test_intent_parser.py::test_parse_deploy_model_intent -v
# Expected: PASSED

# Step 5: Refactor (if needed)
# Improve code quality while maintaining test passage
```

## Coding Standards

### Python Style

Follow PEP 8 with these specifics:

- **Line length**: 120 characters max
- **Imports**: Organized by stdlib, third-party, local
- **Type hints**: Required for all public functions
- **Docstrings**: Google style for all public APIs

### Code Quality Tools

```bash
# Format code (auto-fix)
uv run ruff format src/ tests/

# Lint code (with auto-fixes)
uv run ruff check src/ tests/ --fix

# Type checking
uv run mypy src/

# Run all quality checks
uv run ruff format src/ tests/ && \
uv run ruff check src/ tests/ --fix && \
uv run mypy src/
```

### SOLID Principles

- **Single Responsibility**: Each class/function has one reason to change
- **Open/Closed**: Extend behavior without modifying existing code
- **Liskov Substitution**: Subclasses must be substitutable for base classes
- **Interface Segregation**: No client forced to depend on unused interfaces
- **Dependency Inversion**: Depend on abstractions, not concretions

### Code Organization

```python
# Good: Single responsibility, clear purpose
class IntentParser:
    """Parses natural language into structured intents."""

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm_client = llm_client

    async def parse_intent(self, query: str) -> UserIntent:
        """Parse user query into structured intent."""
        # Implementation...

# Bad: Multiple responsibilities
class IntentParserAndExecutor:  # Violates Single Responsibility
    def parse_and_execute(self, query: str) -> Any:
        # Parsing AND execution in one class
        pass
```

## Testing Requirements

### Test Coverage

- **Minimum**: 80% code coverage (enforced by CI)
- **Target**: 90%+ for critical paths
- **Required**: 100% for public APIs

### Test Types

1. **Unit Tests** (`tests/unit/`)
   - Fast, isolated, no external dependencies
   - Mock external services
   - Test individual functions/classes

2. **Integration Tests** (`tests/integration/`)
   - Test component interactions
   - Use test database
   - Mock external APIs (OpenShift, LLM)

3. **Contract Tests** (`tests/contract/`)
   - Verify API contracts
   - Test request/response schemas
   - Ensure backward compatibility

### Running Tests

```bash
# Run all tests with coverage
uv run pytest --cov=src --cov-report=term-missing

# Run specific test types
uv run pytest -m unit              # Unit tests only
uv run pytest -m integration       # Integration tests only
uv run pytest -m contract          # Contract tests only

# Run tests for specific file
uv run pytest tests/unit/test_intent_parser.py -v

# Run single test
uv run pytest tests/unit/test_intent_parser.py::test_parse_deploy_model_intent -v

# Verify coverage threshold (fails if <80%)
uv run pytest --cov=src --cov-fail-under=80
```

### Writing Good Tests

```python
# Good: Clear, focused, descriptive
@pytest.mark.unit
async def test_parse_deploy_model_intent_extracts_model_name():
    """Test that deploy model intent correctly extracts model name from query."""
    parser = IntentParser()
    intent = await parser.parse_intent("Deploy my fraud-detection model")

    assert intent.parameters["model_name"] == "fraud-detection"

# Bad: Vague, tests multiple things
def test_parser():
    parser = IntentParser()
    result = parser.parse("some query")
    assert result  # What are we testing?
```

## Pull Request Process

### Before Submitting

1. **Run full test suite**: `uv run pytest --cov=src --cov-fail-under=80`
2. **Check code quality**: `uv run ruff check src/ tests/`
3. **Verify type hints**: `uv run mypy src/`
4. **Update documentation**: If you changed public APIs
5. **Add tests**: For all new functionality (TDD)

### PR Title Format

Use conventional commits:

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Test additions/modifications
- `refactor:` - Code refactoring
- `perf:` - Performance improvements
- `chore:` - Maintenance tasks

**Examples**:
- `feat: add support for pipeline scheduling`
- `fix: correct model name extraction in intent parser`
- `docs: update deployment guide with Helm examples`

### PR Description Template

```markdown
## Description
Brief description of changes

## Motivation
Why is this change needed?

## Changes
- Bullet point list of changes
- Include file names for major changes

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Contract tests added/updated
- [ ] Manual testing performed

## Checklist
- [ ] Tests pass locally
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] No breaking changes (or documented if unavoidable)
- [ ] Coverage maintained (≥80%)
```

### Review Process

1. Automated CI checks must pass
2. At least one maintainer approval required
3. No unresolved conversations
4. All tests passing
5. Code coverage maintained

## Architecture Guidelines

### Adding New Features

1. **Plan First**: Update spec.md and plan.md if needed
2. **Design Data Models**: Update data-model.md
3. **Write Tests**: Follow TDD cycle
4. **Implement**: Follow existing patterns
5. **Document**: Update API contracts

### Adding New User Stories

Follow the template in `tasks.md`:

```markdown
## Phase N: User Story Title (Priority: PN)

**Purpose**: Brief description

### Tasks
- [ ] TXX1 [Story] Write contract tests
- [ ] TXX2 [Story] Write integration tests
- [ ] TXX3 [Story] Write unit tests
- [ ] TXX4 [Story] Implement intent parser
- [ ] TXX5 [Story] Implement operation executor
- [ ] TXX6 [Story] Add to /v1/query endpoint
- [ ] TXX7 [Story] Run all tests and verify
```

### Performance Considerations

Per our constitution, performance is a feature:

- **Query response**: <2 seconds
- **Complex operations**: <10 seconds
- **Database queries**: Use indexes, avoid N+1
- **API calls**: Batch when possible, implement caching

### Security Best Practices

- **Never log sensitive data**: Passwords, tokens, PII
- **Validate all inputs**: Type checking, bounds checking
- **Use parameterized queries**: Prevent SQL injection
- **Implement rate limiting**: Prevent abuse
- **Follow principle of least privilege**: Minimize permissions

## Questions?

- Check existing issues: [GitHub Issues](https://github.com/your-org/rhails/issues)
- Read the docs: [Documentation](../specs/001-openshift-ai-agent/)
- Ask the team: [Discussion Forum](https://github.com/your-org/rhails/discussions)

Thank you for contributing! 🎉
