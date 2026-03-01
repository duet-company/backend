"""
Data Source Schemas

Pydantic schemas for data source management.
"""

from pydantic import BaseModel, Field, validator, HttpUrl
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class DataSourceType(str, Enum):
    """Data source type classification."""
    CLICKHOUSE = "clickhouse"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"
    SNOWFLAKE = "snowflake"
    BIGQUERY = "bigquery"
    REDSHIFT = "redshift"
    MONGODB = "mongodb"
    ELASTICSEARCH = "elasticsearch"


class DataSourceStatus(str, Enum):
    """Data source connection status."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    CONNECTING = "connecting"


class DataSourceCreate(BaseModel):
    """Schema for creating a new data source."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    source_type: DataSourceType
    connection_config: Dict[str, Any] = Field(..., description="Connection details")
    is_default: bool = False

    @validator('connection_config')
    def validate_connection_config(cls, v, values):
        """Validate connection config based on source type."""
        source_type = values.get('source_type', DataSourceType.POSTGRESQL)

        # Required fields for each type
        required_fields = {
            DataSourceType.POSTGRESQL: ['host', 'port', 'database', 'username', 'password'],
            DataSourceType.CLICKHOUSE: ['host', 'port', 'database', 'username', 'password'],
            DataSourceType.MYSQL: ['host', 'port', 'database', 'username', 'password'],
            # Add more as needed
        }

        if source_type in required_fields:
            missing_fields = [f for f in required_fields[source_type] if f not in v]
            if missing_fields:
                raise ValueError(f'Missing required connection fields: {", ".join(missing_fields)}')

        return v


class DataSourceUpdate(BaseModel):
    """Schema for updating a data source."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    connection_config: Optional[Dict[str, Any]] = None
    is_default: Optional[bool] = None


class DataSourceResponse(BaseModel):
    """Schema for data source response."""
    id: int
    user_id: int
    name: str
    description: Optional[str] = None
    source_type: DataSourceType
    connection_config: Optional[Dict[str, Any]] = None
    status: DataSourceStatus
    last_tested_at: Optional[datetime] = None
    last_error_message: Optional[str] = None
    is_default: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class DataSourceTestResponse(BaseModel):
    """Schema for data source connection test response."""
    data_source_id: int
    success: bool
    status: DataSourceStatus
    error_message: Optional[str] = None
    tested_at: datetime
