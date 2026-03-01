"""
Unit Tests for DataSource Model
"""

import pytest
from datetime import datetime
from app.models.data_source import DataSource, DataSourceType, DataSourceStatus


class TestDataSourceModel:
    """Test suite for DataSource model."""

    def test_data_source_creation(self):
        """Test creating a new data source."""
        data_source = DataSource(
            user_id=1,
            name="Production ClickHouse",
            description="Main analytics database",
            source_type=DataSourceType.CLICKHOUSE,
            connection_config={
                "host": "localhost",
                "port": 9000,
                "database": "analytics",
                "username": "admin",
                "password": "secret"
            }
        )
        assert data_source.id is None
        assert data_source.user_id == 1
        assert data_source.name == "Production ClickHouse"
        assert data_source.description == "Main analytics database"
        assert data_source.source_type == DataSourceType.CLICKHOUSE
        assert data_source.status == DataSourceStatus.ACTIVE
        assert data_source.is_default is False

    def test_data_source_to_dict(self):
        """Test converting data source to dictionary."""
        data_source = DataSource(
            id=1,
            user_id=1,
            name="Test DB",
            source_type=DataSourceType.POSTGRESQL,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        result = data_source.to_dict()
        assert result["id"] == 1
        assert result["user_id"] == 1
        assert result["name"] == "Test DB"
        assert result["source_type"] == "postgresql"
        assert result["status"] == "active"

    def test_data_source_repr(self):
        """Test data source string representation."""
        data_source = DataSource(id=1, name="Test DB", source_type=DataSourceType.POSTGRESQL)
        repr_str = repr(data_source)
        assert "DataSource(id=1" in repr_str
        assert "name=Test DB" in repr_str
        assert "type=postgresql" in repr_str

    def test_data_source_update_status_success(self):
        """Test updating data source status to success."""
        data_source = DataSource(
            id=1,
            user_id=1,
            name="Test DB",
            source_type=DataSourceType.POSTGRESQL,
            status=DataSourceStatus.CONNECTING
        )
        data_source.update_status(DataSourceStatus.ACTIVE)

        assert data_source.status == DataSourceStatus.ACTIVE
        assert data_source.last_tested_at is not None
        assert data_source.last_error_message is None

    def test_data_source_update_status_error(self):
        """Test updating data source status to error."""
        data_source = DataSource(
            id=1,
            user_id=1,
            name="Test DB",
            source_type=DataSourceType.POSTGRESQL,
            status=DataSourceStatus.CONNECTING
        )
        error_msg = "Connection refused"
        data_source.update_status(DataSourceStatus.ERROR, error_message=error_msg)

        assert data_source.status == DataSourceStatus.ERROR
        assert data_source.last_tested_at is not None
        assert data_source.last_error_message == error_msg

    def test_data_source_type_enum(self):
        """Test DataSourceType enum values."""
        assert DataSourceType.CLICKHOUSE.value == "clickhouse"
        assert DataSourceType.POSTGRESQL.value == "postgresql"
        assert DataSourceType.MYSQL.value == "mysql"
        assert DataSourceType.SNOWFLAKE.value == "snowflake"
        assert DataSourceType.BIGQUERY.value == "bigquery"
        assert DataSourceType.REDSHIFT.value == "redshift"
        assert DataSourceType.MONGODB.value == "mongodb"
        assert DataSourceType.ELASTICSEARCH.value == "elasticsearch"

    def test_data_source_status_enum(self):
        """Test DataSourceStatus enum values."""
        assert DataSourceStatus.ACTIVE.value == "active"
        assert DataSourceStatus.INACTIVE.value == "inactive"
        assert DataSourceStatus.ERROR.value == "error"
        assert DataSourceStatus.CONNECTING.value == "connecting"

    def test_data_source_defaults(self):
        """Test data source default values."""
        data_source = DataSource(
            user_id=1,
            name="Test",
            source_type=DataSourceType.POSTGRESQL
        )
        assert data_source.status == DataSourceStatus.ACTIVE
        assert data_source.is_default is False
        assert data_source.description is None
        assert data_source.connection_config is None
        assert data_source.last_tested_at is None
        assert data_source.last_error_message is None

    def test_data_source_with_connection_config(self):
        """Test data source with connection configuration."""
        config = {
            "host": "db.example.com",
            "port": 5432,
            "database": "production",
            "username": "admin",
            "password": "secret123"
        }
        data_source = DataSource(
            user_id=1,
            name="Production DB",
            source_type=DataSourceType.POSTGRESQL,
            connection_config=config
        )
        assert data_source.connection_config == config
        assert len(data_source.connection_config) == 5
