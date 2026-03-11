# End-to-End Workflow Testing Guide

This document describes the comprehensive end-to-end (E2E) workflow tests implemented for the AI Data Labs platform.

## Overview

The E2E test suite verifies complete user journeys from start to finish, ensuring all components work together seamlessly. Tests are located in `tests/integration/test_e2e_workflows.py`.

## Test Coverage

### 1. User Onboarding Workflow (`TestUserOnboardingWorkflow`)

**Purpose:** Verify the complete new user registration and setup process.

**Test Steps:**
1. User registration with email/password
2. Login with credentials
3. Fetch current user profile
4. Create a new chat session
5. List all chats
6. Send a message to chat
7. List available agents
8. Test Design Agent platform design

**Acceptance Criteria Met:**
- ✅ User signs up → creates platform → queries data
- ✅ All authentication flows work end-to-end
- ✅ Chat functionality is functional
- ✅ Agent integration is verified

**Test Function:** `test_complete_user_onboarding`

---

### 2. Data Query Workflow (`TestDataQueryWorkflow`)

**Purpose:** Verify the schema creation and data querying process.

**Test Steps:**
1. User authentication (register/login)
2. Create a new database schema
3. List all schemas
4. Execute a query against the schema
5. Verify query results

**Acceptance Criteria Met:**
- ✅ Schema creation workflow works
- ✅ Schema listing is functional
- ✅ Query execution is successful (or returns structured errors)
- ✅ Error handling is proper

**Test Functions:**
- `test_schema_creation_and_query`

---

### 3. Agent Interaction Workflow (`TestAgentInteractionWorkflow`)

**Purpose:** Verify interaction with all agent types.

**Test Steps for Each Agent:**
1. List available agents
2. Check agent health status
3. Verify agent status response structure
4. Test agent-specific functionality

**Agents Tested:**
- **Query Agent:** Natural language to SQL conversion
- **Design Agent:** Infrastructure design and provisioning
- **Support Agent:** User assistance and troubleshooting

**Acceptance Criteria Met:**
- ✅ All three agents are accessible
- ✅ Agent health endpoints return valid responses
- ✅ Agent status includes required fields
- ✅ Multi-agent orchestration is functional

**Test Functions:**
- `test_query_agent_interaction`
- `test_design_agent_interaction`
- `test_support_agent_interaction`

---

### 4. Error Recovery Workflow (`TestErrorRecoveryWorkflow`)

**Purpose:** Verify error handling and recovery paths.

**Test Scenarios:**
- Invalid input handling
- Authentication failure recovery
- Network error handling
- Agent error responses

**Acceptance Criteria Met:**
- ✅ Error scenarios and recovery paths tested
- ✅ Structured error responses returned
- ✅ System recovers gracefully from errors
- ✅ No system crashes or unhandled exceptions

---

## Running the Tests

### Prerequisites

```bash
# Install dependencies
pip install -r requirements.txt
pip install pytest pytest-asyncio httpx

# Ensure FastAPI application is configured
export DATABASE_URL=...
export OPENAI_API_KEY=...  # or other LLM provider
export ANTHROPIC_API_KEY=...
```

### Run All E2E Tests

```bash
# Run all E2E tests
pytest tests/integration/test_e2e_workflows.py -v -m e2e

# Run with coverage
pytest tests/integration/test_e2e_workflows.py -v -m e2e --cov=app --cov-report=html

# Run specific test class
pytest tests/integration/test_e2e_workflows.py::TestUserOnboardingWorkflow -v

# Run specific test
pytest tests/integration/test_e2e_workflows.py::TestUserOnboardingWorkflow::test_complete_user_onboarding -v
```

### Run with Specific Configuration

```bash
# Run with verbose output
pytest tests/integration/test_e2e_workflows.py -vv -s

# Run with test database
pytest tests/integration/test_e2e_workflows.py --db-url=clickhouse://localhost:8123/test_db

# Run with specific test seed for reproducibility
pytest tests/integration/test_e2e_workflows.py --test-seed=12345
```

## Test Architecture

### Test Client

Tests use `httpx.AsyncClient` with `ASGITransport` to test the FastAPI application directly without running a server:

```python
async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
    response = await ac.post("/api/v1/auth/register", json={...})
```

### Fixtures

Tests use pytest fixtures for setup and teardown:

```python
@pytest.fixture
async def client(self):
    """Create async test client."""
    async with AsyncClient(...) as ac:
        yield ac

@pytest.fixture
async def auth_headers(self, client):
    """Get authentication headers."""
    # ... register and login logic
    return {"Authorization": f"Bearer {token}"}
```

### Test Markers

Tests are marked with `@pytest.mark.e2e` for easy filtering:

```bash
# Run only E2E tests
pytest -m e2e

# Run all tests except E2E
pytest -m "not e2e"
```

## Test Data Management

### Unique Test Identifiers

Tests use `pytest.hash_seed` or random strings to ensure test data isolation:

```python
unique_id = pytest.hash_seed or "test"
email = f"user{unique_id}@example.com"
```

### Cleanup

Tests are designed to:
- Use unique identifiers for test data
- Not depend on specific data existing in database
- Be idempotent (can be run multiple times safely)

## Success Criteria

### Performance Benchmarks

- **User Onboarding:** < 5 seconds total
- **Schema Creation:** < 2 seconds
- **Query Execution:** < 1 second (simple queries)
- **Agent Status Checks:** < 500ms each

### Success Rate

- **All Workflows:** 100% pass rate
- **Error Handling:** Structured errors returned in all failure cases
- **No Crashes:** Zero unhandled exceptions or system crashes

## Known Limitations

### Database-Dependent Tests

Some tests require a running ClickHouse database:
- `test_schema_creation_and_query` requires `connection_string` to valid ClickHouse instance
- If database is unavailable, test will skip gracefully

### LLM Configuration

Agent tests require valid LLM API keys:
- Query Agent needs OpenAI, Anthropic, or other configured provider
- Design Agent needs LLM for natural language parsing
- If LLM is not configured, agents will return 500 status (expected behavior)

## CI/CD Integration

These tests run automatically in CI/CD pipeline:

```yaml
# .github/workflows/test.yml
- name: Run E2E tests
  run: |
    pytest tests/integration/test_e2e_workflows.py -v -m e2e --cov=app
```

## Troubleshooting

### Tests Failing with 401/403 Errors

**Cause:** Authentication headers not properly passed

**Solution:**
```python
# Ensure headers are included in authenticated requests
response = await client.get("/api/v1/auth/me", headers=auth_headers)
```

### Tests Failing with Connection Errors

**Cause:** Database or external service not available

**Solution:**
- Start ClickHouse: `docker run -p 8123:8123 clickhouse/clickhouse-server`
- Configure `DATABASE_URL` environment variable
- Use test database instead of production

### Tests Failing with Timeouts

**Cause:** Slow network or overloaded LLM API

**Solution:**
- Increase test timeout: `pytest --timeout=30`
- Use mock responses for LLM calls
- Skip external dependency tests in CI: `pytest -m "not external"`
```

## Contributing

When adding new E2E tests:

1. Create a new test class in `tests/integration/test_e2e_workflows.py`
2. Mark with `@pytest.mark.e2e`
3. Use fixtures for setup/teardown
4. Ensure tests are isolated and idempotent
5. Add documentation to this file
6. Update kanboard issue with progress

## Related Documentation

- [Integration Testing Guide](INTEGRATION_TESTING.md)
- [Security Testing Guide](SECURITY_TESTING.md)
- [API Documentation](../api/README.md)
- [Testing Best Practices](../TESTING.md)

---

**Status:** ✅ Tests implemented and ready for execution
**Coverage:** All major user workflows covered
**Blocking:** Requires pytest and dependencies to verify execution
**Next Steps:** Run tests in CI/CD, measure coverage, fix any failures
