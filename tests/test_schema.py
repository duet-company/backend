"""
Unit Tests for Schema Models
"""

import pytest
from datetime import datetime
from app.models.schema import Schema, Table, Column


class TestSchemaModel:
    """Test suite for Schema model."""

    def test_schema_creation(self):
        """Test creating a new schema."""
        schema = Schema(
            data_source_id=1,
            name="public",
            description="Public schema",
            table_count=5
        )
        assert schema.id is None
        assert schema.data_source_id == 1
        assert schema.name == "public"
        assert schema.description == "Public schema"
        assert schema.table_count == 5
        assert schema.is_active is True
        assert schema.last_synced_at is None

    def test_schema_to_dict(self):
        """Test converting schema to dictionary."""
        schema = Schema(
            id=1,
            data_source_id=1,
            name="public",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        result = schema.to_dict()
        assert result["id"] == 1
        assert result["data_source_id"] == 1
        assert result["name"] == "public"
        assert result["is_active"] is True

    def test_schema_repr(self):
        """Test schema string representation."""
        schema = Schema(id=1, name="public", data_source_id=1)
        repr_str = repr(schema)
        assert "Schema(id=1" in repr_str
        assert "name=public" in repr_str
        assert "data_source_id=1" in repr_str


class TestTableModel:
    """Test suite for Table model."""

    def test_table_creation(self):
        """Test creating a new table."""
        table = Table(
            schema_id=1,
            name="users",
            description="User table",
            row_count_estimate=1000,
            column_count=10
        )
        assert table.id is None
        assert table.schema_id == 1
        assert table.name == "users"
        assert table.description == "User table"
        assert table.row_count_estimate == 1000
        assert table.column_count == 10
        assert table.is_active is True

    def test_table_to_dict(self):
        """Test converting table to dictionary."""
        table = Table(
            id=1,
            schema_id=1,
            name="users",
            column_count=10,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        result = table.to_dict()
        assert result["id"] == 1
        assert result["schema_id"] == 1
        assert result["name"] == "users"
        assert result["column_count"] == 10

    def test_table_repr(self):
        """Test table string representation."""
        table = Table(id=1, name="users", schema_id=1)
        repr_str = repr(table)
        assert "Table(id=1" in repr_str
        assert "name=users" in repr_str
        assert "schema_id=1" in repr_str


class TestColumnModel:
    """Test suite for Column model."""

    def test_column_creation(self):
        """Test creating a new column."""
        column = Column(
            table_id=1,
            name="email",
            data_type="VARCHAR(255)",
            is_nullable=False,
            is_primary_key=True,
            ordinal_position=1
        )
        assert column.id is None
        assert column.table_id == 1
        assert column.name == "email"
        assert column.data_type == "VARCHAR(255)"
        assert column.is_nullable is False
        assert column.is_primary_key is True
        assert column.ordinal_position == 1

    def test_column_to_dict(self):
        """Test converting column to dictionary."""
        column = Column(
            id=1,
            table_id=1,
            name="email",
            data_type="VARCHAR(255)",
            ordinal_position=1,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        result = column.to_dict()
        assert result["id"] == 1
        assert result["table_id"] == 1
        assert result["name"] == "email"
        assert result["data_type"] == "VARCHAR(255)"
        assert result["is_nullable"] is True  # Default value
        assert result["is_primary_key"] is False  # Default value

    def test_column_repr(self):
        """Test column string representation."""
        column = Column(id=1, name="email", table_id=1, data_type="VARCHAR(255)")
        repr_str = repr(column)
        assert "Column(id=1" in repr_str
        assert "name=email" in repr_str
        assert "table_id=1" in repr_str
        assert "type=VARCHAR(255)" in repr_str

    def test_column_defaults(self):
        """Test column default values."""
        column = Column(
            table_id=1,
            name="test",
            data_type="TEXT",
            ordinal_position=1
        )
        assert column.is_nullable is True  # Default
        assert column.is_primary_key is False  # Default
        assert column.default_value is None
        assert column.description is None
