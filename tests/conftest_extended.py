"""
Pytest Configuration for Backend Testing

Defines markers for different test types and configuration for test execution.
"""

import pytest


def pytest_configure(config):
    """Configure custom pytest markers."""
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests (fast, isolated)"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests (require external services)"
    )
    config.addinivalue_line(
        "markers", "e2e: marks tests as end-to-end tests (complete user workflows)"
    )
    config.addinivalue_line(
        "markers", "security: marks tests as security tests (vulnerability scanning)"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance tests (benchmarking)"
    )
    config.addinivalue_line(
        "markers", "load: marks tests as load tests (stress testing)"
    )
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (skip by default in CI)"
    )


# Fixtures for test configuration

@pytest.fixture(scope="session")
def test_config():
    """Provide test configuration."""
    return {
        "test_database_url": "postgresql://test:test@localhost:5432/test_db",
        "test_clickhouse_url": "clickhouse://localhost:8123/test_db",
        "test_redis_url": "redis://localhost:6379/1",
        "enable_slow_tests": False,  # Set to True to run slow tests
        "enable_integration_tests": True,
    }


@pytest.fixture
def mock_llm_response():
    """Mock LLM response for agent tests."""
    return {
        "content": "This is a mock response from the LLM.",
        "model": "mock-model",
        "tokens": 50
    }


@pytest.fixture
def mock_database_schema():
    """Mock database schema for testing."""
    return {
        "name": "test_schema",
        "tables": [
            {
                "name": "users",
                "columns": [
                    {"name": "id", "type": "Int32"},
                    {"name": "name", "type": "String"},
                    {"name": "email", "type": "String"},
                ]
            },
            {
                "name": "orders",
                "columns": [
                    {"name": "id", "type": "Int32"},
                    {"name": "user_id", "type": "Int32"},
                    {"name": "amount", "type": "Float64"},
                ]
            }
        ]
    }
