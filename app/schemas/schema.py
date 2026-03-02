"""
Schema Schemas

Pydantic schemas for database schema management.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ColumnResponse(BaseModel):
    """Schema for column response."""
    id: int
    table_id: int
    name: str
    data_type: str
    is_nullable: bool
    is_primary_key: bool
    default_value: Optional[str] = None
    description: Optional[str] = None
    ordinal_position: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class TableResponse(BaseModel):
    """Schema for table response."""
    id: int
    schema_id: int
    name: str
    description: Optional[str] = None
    row_count_estimate: Optional[int] = None
    column_count: int
    is_active: bool
    last_synced_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    columns: List[ColumnResponse] = []

    class Config:
        orm_mode = True


class SchemaResponse(BaseModel):
    """Schema for schema response."""
    id: int
    data_source_id: int
    name: str
    description: Optional[str] = None
    table_count: int
    is_active: bool
    last_synced_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    tables: List[TableResponse] = []

    class Config:
        orm_mode = True


class SchemaSyncRequest(BaseModel):
    """Schema for requesting schema synchronization."""
    data_source_id: int
    schema_names: Optional[List[str]] = None
    force_sync: bool = False
