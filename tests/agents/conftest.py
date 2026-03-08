"""
Conftest for Query Agent tests - auto-mock ClickHouse dependencies.
"""

import pytest
from unittest.mock import Mock, AsyncMock


@pytest.fixture(autouse=True)
def mock_clickhouse_schema_loader():
    """
    Automatically mock ClickHouseSchemaLoader for all tests in this directory.
    Prevents real network connections to ClickHouse in CI.
    """
    with pytest.MonkeyPatch.context() as mp:
        # Create a mock schema loader class
        mock_loader_class = Mock()
        mock_loader_instance = Mock()
        mock_loader_instance.connect = Mock()
        mock_loader_instance.disconnect = Mock()
        mock_loader_instance.get_schema = Mock(return_value={
            "tables": {
                "users": {
                    "engine": "MergeTree",
                    "columns": [
                        {"name": "id", "type": "UInt32", "primary_key": True},
                        {"name": "name", "type": "String"},
                        {"name": "email", "type": "String"},
                        {"name": "created_at", "type": "DateTime"}
                    ]
                },
                "orders": {
                    "engine": "MergeTree",
                    "columns": [
                        {"name": "id", "type": "UInt32", "primary_key": True},
                        {"name": "user_id", "type": "UInt32"},
                        {"name": "amount", "type": "Float64"},
                        {"name": "status", "type": "String"}
                    ]
                }
            },
            "views": []
        })
        mock_loader_instance.format_schema_for_prompt = Mock(return_value="Mock schema")
        mock_loader_class.return_value = mock_loader_instance

        # Patch the class in the module where it's used
        mp.setattr('app.agents.query_agent.ClickHouseSchemaLoader', mock_loader_class)

        yield mock_loader_instance
