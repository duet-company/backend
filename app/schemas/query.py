"""
Query Schemas

Pydantic schemas for query management.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum


class QueryStatus(str, Enum):
    """Query execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class QueryType(str, Enum):
    """Query type classification."""
    NATURAL_LANGUAGE = "natural_language"
    SQL = "sql"
    METADATA = "metadata"
    SCHEMA_EXPLORATION = "schema_exploration"


class QueryCreate(BaseModel):
    """Schema for creating a new query."""
    natural_language: str = Field(..., min_length=1, max_length=5000)
    query_type: QueryType = QueryType.NATURAL_LANGUAGE

    @validator('natural_language')
    def validate_query(cls, v):
        """Validate natural language query."""
        if not v.strip():
            raise ValueError('Query cannot be empty or whitespace only')
        return v.strip()


class QueryResponse(BaseModel):
    """Schema for query response."""
    id: int
    user_id: int
    natural_language: str
    generated_sql: Optional[str] = None
    query_type: QueryType
    status: QueryStatus
    row_count: Optional[int] = None
    execution_time_ms: Optional[int] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class QueryResult(BaseModel):
    """Schema for query execution result."""
    query_id: int
    status: QueryStatus
    data: Optional[List[Dict[str, Any]]] = None
    row_count: Optional[int] = None
    execution_time_ms: Optional[int] = None
    error_message: Optional[str] = None
