"""
Data Source Database Model

SQLAlchemy model for managing data source connections.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, Enum
from app.core.database import Base
import enum


class DataSourceType(str, enum.Enum):
    """Data source type classification."""
    CLICKHOUSE = "clickhouse"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SNOWFLAKE = "snowflake"
    BIGQUERY = "bigquery"
    REDSHIFT = "redshift"
    MONGODB = "mongodb"
    ELASTICSEARCH = "elasticsearch"


class DataSourceStatus(str, enum.Enum):
    """Data source connection status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    CONNECTING = "connecting"


class DataSource(Base):
    """
    Data Source model for managing external data connections.

    This model stores connection details and metadata for external data sources
    that users can query against.

    Attributes:
        id: Primary key
        user_id: Foreign key to user who owns the data source
        name: Human-readable name for the data source
        description: Data source description
        source_type: Type of data source (ClickHouse, PostgreSQL, etc.)
        connection_config: Connection configuration (JSON with credentials, host, etc.)
        host: Database host (deprecated in favor of connection_config)
        port: Database port (deprecated in favor of connection_config)
        database_name: Database name (deprecated in favor of connection_config)
        status: Current connection status
        last_tested_at: Last time connection was tested
        last_error_message: Last error message if connection failed
        is_default: Whether this is the default data source for the user
        created_at: Data source creation timestamp
        updated_at: Last update timestamp
    """
    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    source_type = Column(Enum(DataSourceType), nullable=False, index=True)
    connection_config = Column(JSON, nullable=True)
    host = Column(String(255), nullable=True)
    port = Column(Integer, nullable=True)
    database_name = Column(String(255), nullable=True)
    status = Column(Enum(DataSourceStatus), default=DataSourceStatus.ACTIVE, nullable=False, index=True)
    last_tested_at = Column(DateTime, nullable=True)
    last_error_message = Column(Text, nullable=True)
    is_default = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<DataSource(id={self.id}, name={self.name}, type={self.source_type})>"

    def to_dict(self):
        """Convert data source object to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "name": self.name,
            "description": self.description,
            "source_type": self.source_type.value,
            "connection_config": self.connection_config,
            "host": self.host,
            "port": self.port,
            "database_name": self.database_name,
            "status": self.status.value,
            "last_tested_at": self.last_tested_at.isoformat() if self.last_tested_at else None,
            "last_error_message": self.last_error_message,
            "is_default": self.is_default,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

    def update_status(self, status: DataSourceStatus, error_message: str = None):
        """Update connection status."""
        self.status = status
        self.last_tested_at = datetime.utcnow()
        if error_message:
            self.last_error_message = error_message
        self.save()

    def test_connection(self):
        """Test connection to data source (placeholder - implement in service layer)."""
        # This should be implemented in the data source service
        # Returns True if connection successful, False otherwise
        pass

    def save(self):
        """Save the data source to the database."""
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            db.add(self)
            db.commit()
            db.refresh(self)
        finally:
            db.close()
