"""
Schema Database Model

SQLAlchemy model for managing database schemas and table structures.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base


class Schema(Base):
    """
    Schema model for storing database schema metadata.

    This model represents a database schema (namespace) that contains tables.

    Attributes:
        id: Primary key
        data_source_id: Foreign key to the data source
        name: Schema name (e.g., "public", "analytics")
        description: Schema description
        table_count: Number of tables in the schema
        is_active: Whether the schema is active
        last_synced_at: Last time schema was synchronized
        created_at: Schema creation timestamp
        updated_at: Last update timestamp
    """
    __tablename__ = "schemas"

    id = Column(Integer, primary_key=True, index=True)
    data_source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    table_count = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    data_source = relationship("DataSource", backref="schemas")
    tables = relationship("Table", back_populates="schema", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Schema(id={self.id}, name={self.name}, data_source_id={self.data_source_id})>"

    def to_dict(self):
        """Convert schema object to dictionary."""
        return {
            "id": self.id,
            "data_source_id": self.data_source_id,
            "name": self.name,
            "description": self.description,
            "table_count": self.table_count,
            "is_active": self.is_active,
            "last_synced_at": self.last_synced_at.isoformat() if self.last_synced_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class Table(Base):
    """
    Table model for storing table metadata within schemas.

    Attributes:
        id: Primary key
        schema_id: Foreign key to the schema
        name: Table name
        description: Table description
        row_count_estimate: Estimated row count
        column_count: Number of columns in the table
        is_active: Whether the table is active
        last_synced_at: Last time table was synchronized
        created_at: Table creation timestamp
        updated_at: Last update timestamp
    """
    __tablename__ = "tables"

    id = Column(Integer, primary_key=True, index=True)
    schema_id = Column(Integer, ForeignKey("schemas.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    row_count_estimate = Column(Integer, nullable=True)
    column_count = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    schema = relationship("Schema", back_populates="tables")
    columns = relationship("Column", back_populates="table", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Table(id={self.id}, name={self.name}, schema_id={self.schema_id})>"

    def to_dict(self):
        """Convert table object to dictionary."""
        return {
            "id": self.id,
            "schema_id": self.schema_id,
            "name": self.name,
            "description": self.description,
            "row_count_estimate": self.row_count_estimate,
            "column_count": self.column_count,
            "is_active": self.is_active,
            "last_synced_at": self.last_synced_at.isoformat() if self.last_synced_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class Column(Base):
    """
    Column model for storing column metadata within tables.

    Attributes:
        id: Primary key
        table_id: Foreign key to the table
        name: Column name
        data_type: Column data type (e.g., "VARCHAR", "INTEGER", "TIMESTAMP")
        is_nullable: Whether column can contain NULL values
        is_primary_key: Whether column is part of primary key
        default_value: Default value for column
        description: Column description
        ordinal_position: Column position in the table (1-indexed)
        created_at: Column creation timestamp
        updated_at: Last update timestamp
    """
    __tablename__ = "columns"

    id = Column(Integer, primary_key=True, index=True)
    table_id = Column(Integer, ForeignKey("tables.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    data_type = Column(String(100), nullable=False)
    is_nullable = Column(Boolean, default=True, nullable=False)
    is_primary_key = Column(Boolean, default=False, nullable=False)
    default_value = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    ordinal_position = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    table = relationship("Table", back_populates="columns")

    def __repr__(self):
        return f"<Column(id={self.id}, name={self.name}, table_id={self.table_id}, type={self.data_type})>"

    def to_dict(self):
        """Convert column object to dictionary."""
        return {
            "id": self.id,
            "table_id": self.table_id,
            "name": self.name,
            "data_type": self.data_type,
            "is_nullable": self.is_nullable,
            "is_primary_key": self.is_primary_key,
            "default_value": self.default_value,
            "description": self.description,
            "ordinal_position": self.ordinal_position,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
