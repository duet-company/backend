# Backend Test Suite

Comprehensive testing suite for AI Data Labs backend platform.

## Test Coverage

This test suite includes multiple types of tests to ensure platform quality:

- **Unit Tests**: Fast, isolated tests for individual components
- **Integration Tests**: Tests API endpoints with real dependencies
- **End-to-End Tests**: Complete user workflows from start to finish
- **Security Tests**: Vulnerability scanning and security validation
- **Performance Tests**: Benchmarking and response time validation
- **Load Tests**: Stress testing and capacity planning

## Test Structure

```
tests/
├── conftest.py                              # Main pytest configuration
├── conftest_extended.py                     # Extended fixtures and markers
├── test_report_generator.py                 # Test report generation
├── agents/                                  # Agent framework tests
│   ├── test_agent_framework.py              # Base agent, lifecycle, registry
│   └── test_query_agent.py                  # Query agent implementation
├── integration/                             # Integration and e2e tests
│   ├── test_api_integration.py              # API endpoint integration tests
│   ├── test_e2e_workflows.py                # End-to-end workflow tests
│   └── test_security.py                     # Security vulnerability tests
└── performance/                             # Performance and load tests
    └── test_load_performance.py             # Load testing and performance metrics
```

## Running Tests

### Run All Tests

```bash
pytest tests/ -v
```

### Run Specific Test Types

```bash
# Unit tests only (fast)
pytest tests/ -v -m unit

# Integration tests only
pytest tests/ -v -m integration

# End-to-end tests only
pytest tests/ -v -m e2e

# Security tests only
pytest tests/ -v -m security

# Performance tests only
pytest tests/ -v -m performance

# Load tests only (may take longer)
pytest tests/ -v -m load
```

### Run Specific Test Files

```bash
# Agent framework tests
pytest tests/agents/ -v

# Integration tests
pytest tests/integration/ -v

# Performance tests
pytest tests/performance/ -v
```

### Run Specific Test Class or Function

```bash
# Run specific test class
pytest tests/integration/test_api_integration.py::TestAPIEndpointsIntegration -v

# Run specific test
pytest tests/integration/test_api_integration.py::TestAPIEndpointsIntegration::test_health_check -v
```

### Run Tests with Coverage Report

```bash
# Generate coverage report
pytest tests/ --cov=app --cov-report=html

# Open coverage report
open htmlcov/index.html
```

### Run Tests with Detailed Output

```bash
# Very verbose output
pytest tests/ -vv -s

# Show local variables in tracebacks
pytest tests/ -vv -l
```

### Run Tests in Parallel

```bash
# Install pytest-xdist first
pip install pytest-xdist

# Run tests in parallel (use all CPU cores)
pytest tests/ -n auto

# Run tests in parallel with 4 workers
pytest tests/ -n 4
```

## Test Markers

This test suite uses pytest markers to categorize tests:

- `@pytest.mark.unit`: Fast, isolated unit tests
- `@pytest.mark.integration`: Tests requiring external services (database, APIs)
- `@pytest.mark.e2e`: End-to-end workflow tests
- `@pytest.mark.security`: Security vulnerability tests
- `@pytest.mark.performance`: Performance benchmarking tests
- `@pytest.mark.load`: Load and stress tests
- `@pytest.mark.slow`: Tests that take longer to run

### Listing Tests by Marker

```bash
# List all unit tests
pytest tests/ -m unit --collect-only

# List all integration tests
pytest tests/ -m integration --collect-only
```

## Test Reports

After running tests, comprehensive reports are generated:

### Console Report

A human-readable summary printed to console:

```
================================================================================
TEST REPORT SUMMARY
================================================================================

📊 Overall Results:
   Total Tests: 150
   ✅ Passed: 145 (96.7%)
   ❌ Failed: 3 (2.0%)
   ⏭️  Skipped: 2 (1.3%)
   💥 Errors: 0 (0.0%)
   ⏱️  Duration: 45.23s
```

### JSON Report

Machine-readable JSON report saved to `test-report.json`:

```bash
# View JSON report
cat test-report.json

# Use with CI/CD pipelines
jq '.summary.success_rate' test-report.json
```

### Markdown Report

Human-readable Markdown report saved to `test-report.md`:

```bash
# View Markdown report
cat test-report.md

# Convert to HTML
pandoc test-report.md -o test-report.html
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: test_db
        ports:
          - 5432:5432
    
      clickhouse:
        image: clickhouse/clickhouse-server
        ports:
          - 8123:8123
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest pytest-cov pytest-asyncio pytest-xdist httpx
      
      - name: Run unit tests
        run: pytest tests/ -m unit -v
      
      - name: Run integration tests
        run: pytest tests/ -m integration -v
        env:
          DATABASE_URL: postgresql://postgres:test@localhost:5432/test_db
          CLICKHOUSE_URL: clickhouse://localhost:8123/default
      
      - name: Run security tests
        run: pytest tests/ -m security -v
      
      - name: Generate coverage report
        run: pytest tests/ --cov=app --cov-report=xml --cov-report=html
      
      - name: Upload coverage to Codecov
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
      
      - name: Upload test reports
        uses: actions/upload-artifact@v3
        with:
          name: test-reports
          path: |
            test-report.json
            test-report.md
            htmlcov/
```

## Test Data

### Fixtures

Test fixtures are defined in `conftest.py` and `conftest_extended.py`:

- `sample_user_data`: Sample user registration data
- `sample_token_data`: Sample JWT token data
- `test_config`: Test configuration object
- `mock_llm_response`: Mock LLM API response
- `mock_database_schema`: Mock database schema structure

### Mock Services

Tests use mocking to avoid dependencies on external services:

- Mock LLM providers (OpenAI, Anthropic, Zhipu AI)
- Mock database connections
- Mock external APIs

## Performance Benchmarks

Performance tests establish baseline metrics:

- **Health Check**: < 50ms average, < 100ms P95
- **Authentication (login)**: < 300ms average
- **API Response Time**: < 100ms average for common endpoints
- **Throughput**: > 100 requests/second for health checks
- **Success Rate Under Load**: > 99% sustained

## Security Tests

Security tests check for common vulnerabilities:

- SQL injection prevention
- XSS (Cross-Site Scripting) prevention
- Weak password rejection
- Brute force protection
- Token expiration handling
- Authorization enforcement
- Input validation
- Rate limiting

## Continuous Monitoring

### Coverage Goals

- **Overall Coverage**: > 80%
- **Core Modules**: > 90%
- **API Endpoints**: > 85%
- **Agent Framework**: > 85%

### Performance Monitoring

Key metrics tracked in CI/CD:

- Average response time
- P95/P99 response times
- Error rate
- Test duration
- Memory usage

## Debugging Tests

### Running Tests with pdb

```bash
# Drop into debugger on failure
pytest tests/ -x --pdb

# Drop into debugger on error
pytest tests/ -x --pdb --tb=long
```

### Capturing Output

```bash
# Capture print statements
pytest tests/ -s

# Show local variables
pytest tests/ -vv -l
```

### Selective Test Running

```bash
# Run only failed tests from last run
pytest tests/ --lf

# Run tests in order of failure from last run
pytest tests/ --ff
```

## Best Practices

### Writing Tests

1. **Arrange-Act-Assert Pattern**:
   ```python
   def test_example():
       # Arrange
       client = create_test_client()
       
       # Act
       response = client.get("/health")
       
       # Assert
       assert response.status_code == 200
   ```

2. **Descriptive Test Names**:
   ```python
   def test_health_check_returns_200():
       # Good
       pass
   
   def test_health():
       # Too vague
       pass
   ```

3. **Independent Tests**:
   - Tests should not depend on each other
   - Each test should clean up after itself
   - Use fixtures for shared setup

4. **Fast Tests**:
   - Unit tests should complete in < 1 second
   - Integration tests in < 5 seconds
   - Avoid unnecessary delays

### Test Organization

- Group related tests in test classes
- Use appropriate markers (unit, integration, e2e)
- Keep test files focused on one area
- Document complex test scenarios

## Troubleshooting

### Tests Failing Due to Database Connection

```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Start PostgreSQL
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=test \
  -e POSTGRES_DB=test_db postgres:15

# Check if ClickHouse is running
docker ps | grep clickhouse

# Start ClickHouse
docker run -d -p 8123:8123 clickhouse/clickhouse-server
```

### Tests Failing Due to Missing Dependencies

```bash
# Install test dependencies
pip install pytest pytest-asyncio pytest-cov pytest-xdist httpx

# Install development dependencies
pip install -r requirements.txt
```

### Tests Timing Out

```bash
# Increase timeout for specific tests
pytest tests/ --timeout=60

# Skip slow tests
pytest tests/ -m "not slow"
```

## Contributing

When adding new features:

1. Write tests first (TDD) or alongside implementation
2. Aim for > 80% test coverage
3. Include integration tests for API endpoints
4. Add security tests for user input handling
5. Update this README if adding new test types

## References

- [Pytest Documentation](https://docs.pytest.org/)
- [FastAPI Testing Guide](https://fastapi.tiangolo.com/tutorial/testing/)
- [OWASP Testing Guide](https://owasp.org/www-project-web-security-testing-guide/)
- [Performance Testing Best Practices](https://www.blazemeter.com/blog/ultimate-guide-performance-testing)

## License

Copyright © 2026 Duet Company
