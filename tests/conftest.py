"""
Pytest Configuration

Shared fixtures and configuration for test suite.
"""

import pytest
from datetime import datetime


@pytest.fixture
def sample_user_data():
    """Provide sample user data for testing."""
    return {
        "email": "test@example.com",
        "password": "testpassword123",
        "full_name": "Test User"
    }


@pytest.fixture
def sample_token_data():
    """Provide sample token data for testing."""
    return {
        "sub": "test@example.com",
        "user_id": 1
    }
