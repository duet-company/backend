"""
Unit Tests for Query Model
"""

import pytest
from datetime import datetime, timedelta
from app.models.query import Query, QueryStatus, QueryType


class TestQueryModel:
    """Test suite for Query model."""

    def test_query_creation(self):
        """Test creating a new query."""
        query = Query(
            user_id=1,
            natural_language="Show me all users from the last month",
            query_type=QueryType.NATURAL_LANGUAGE,
            status=QueryStatus.PENDING
        )
        assert query.id is None  # Not saved yet
        assert query.user_id == 1
        assert query.natural_language == "Show me all users from the last month"
        assert query.query_type == QueryType.NATURAL_LANGUAGE
        assert query.status == QueryStatus.PENDING
        assert query.generated_sql is None
        assert query.result_data is None
        assert query.row_count is None
        assert query.execution_time_ms is None
        assert query.error_message is None
        assert query.completed_at is None

    def test_query_to_dict(self):
        """Test converting query to dictionary."""
        query = Query(
            id=1,
            user_id=1,
            natural_language="Test query",
            query_type=QueryType.NATURAL_LANGUAGE,
            status=QueryStatus.PENDING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        result = query.to_dict()
        assert result["id"] == 1
        assert result["user_id"] == 1
        assert result["natural_language"] == "Test query"
        assert result["status"] == "pending"
        assert result["query_type"] == "natural_language"

    def test_query_mark_completed(self):
        """Test marking query as completed."""
        query = Query(
            id=1,
            user_id=1,
            natural_language="Test query",
            query_type=QueryType.NATURAL_LANGUAGE,
            status=QueryStatus.RUNNING
        )
        result_data = [{"col1": "val1", "col2": "val2"}]
        query.mark_completed(result_data=result_data, row_count=1, execution_time_ms=100)

        assert query.status == QueryStatus.COMPLETED
        assert query.completed_at is not None
        assert query.result_data == result_data
        assert query.row_count == 1
        assert query.execution_time_ms == 100

    def test_query_mark_failed(self):
        """Test marking query as failed."""
        query = Query(
            id=1,
            user_id=1,
            natural_language="Test query",
            query_type=QueryType.NATURAL_LANGUAGE,
            status=QueryStatus.RUNNING
        )
        error_msg = "Connection timeout"
        query.mark_failed(error_msg)

        assert query.status == QueryStatus.FAILED
        assert query.completed_at is not None
        assert query.error_message == error_msg

    def test_query_repr(self):
        """Test query string representation."""
        query = Query(id=1, user_id=1, status=QueryStatus.PENDING)
        repr_str = repr(query)
        assert "Query(id=1" in repr_str
        assert "user_id=1" in repr_str
        assert "status=pending" in repr_str

    def test_query_status_enum(self):
        """Test QueryStatus enum values."""
        assert QueryStatus.PENDING.value == "pending"
        assert QueryStatus.RUNNING.value == "running"
        assert QueryStatus.COMPLETED.value == "completed"
        assert QueryStatus.FAILED.value == "failed"
        assert QueryStatus.CANCELLED.value == "cancelled"

    def test_query_type_enum(self):
        """Test QueryType enum values."""
        assert QueryType.NATURAL_LANGUAGE.value == "natural_language"
        assert QueryType.SQL.value == "sql"
        assert QueryType.METADATA.value == "metadata"
        assert QueryType.SCHEMA_EXPLORATION.value == "schema_exploration"

    def test_query_default_values(self):
        """Test query default values."""
        query = Query(
            user_id=1,
            natural_language="Test"
        )
        assert query.query_type == QueryType.NATURAL_LANGUAGE
        assert query.status == QueryStatus.PENDING
        assert query.row_count is None
        assert query.execution_time_ms is None
