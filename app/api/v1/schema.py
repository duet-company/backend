"""
Schema Management API - Database schema operations endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
import logging

from app.core.security import get_current_active_user

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# Pydantic Models
# ============================================================================

class SchemaField(BaseModel):
    """Schema field definition"""
    name: str = Field(..., description="Field name")
    type: str = Field(..., description="Field type (string, integer, float, boolean, datetime)")
    nullable: bool = Field(default=True, description="Whether field can be null")
    primary_key: bool = Field(default=False, description="Whether field is a primary key")
    description: Optional[str] = Field(None, description="Field description")

    @validator('type')
    def validate_type(cls, v):
        valid_types = {'string', 'integer', 'float', 'boolean', 'datetime', 'date', 'json'}
        if v not in valid_types:
            raise ValueError(f'Invalid type. Must be one of: {valid_types}')
        return v


class SchemaIndex(BaseModel):
    """Schema index definition"""
    name: str = Field(..., description="Index name")
    fields: List[str] = Field(..., description="List of field names")
    unique: bool = Field(default=False, description="Whether index is unique")


class SchemaCreateRequest(BaseModel):
    """Schema creation request"""
    name: str = Field(..., description="Schema name", min_length=1, max_length=255)
    description: str = Field(default="", description="Schema description")
    platform_id: str = Field(..., description="Platform ID")
    fields: List[SchemaField] = Field(..., description="List of schema fields")
    indexes: List[SchemaIndex] = Field(default_factory=list, description="List of schema indexes")

    @validator('fields')
    def validate_fields(cls, v):
        if not v:
            raise ValueError('At least one field is required')
        return v


class SchemaUpdateRequest(BaseModel):
    """Schema update request"""
    description: Optional[str] = Field(None, description="Schema description")
    fields: Optional[List[SchemaField]] = Field(None, description="List of schema fields")
    indexes: Optional[List[SchemaIndex]] = Field(None, description="List of schema indexes")


class SchemaResponse(BaseModel):
    """Schema response"""
    id: str
    name: str
    description: str
    platform_id: str
    fields: List[SchemaField]
    indexes: List[SchemaIndex]
    status: str
    created_at: str
    updated_at: str


class SchemaListResponse(BaseModel):
    """Schema list response"""
    schemas: List[SchemaResponse]
    total: int
    page: int
    per_page: int


# ============================================================================
# In-Memory Storage (Replace with Database)
# ============================================================================

schemas_db: Dict[str, SchemaResponse] = {}


def _generate_schema_id() -> str:
    """Generate unique schema ID"""
    return f"schema_{len(schemas_db) + 1}"


def _get_timestamp() -> str:
    """Get current ISO timestamp"""
    from datetime import datetime
    return datetime.utcnow().isoformat() + "Z"


# ============================================================================
# API Endpoints
# ============================================================================

@router.post("/", response_model=SchemaResponse, status_code=201)
async def create_schema(request: SchemaCreateRequest, current_user: dict = Depends(get_current_active_user)):
    """
    Create a new database schema

    - Validates schema fields and types
    - Ensures at least one primary key exists
    - Creates schema in platform database
    - Returns schema details

    **Authentication required**
    """
    try:
        logger.info(f"Creating schema: {request.name} for platform {request.platform_id}")

        # Validate at least one primary key exists
        has_primary_key = any(field.primary_key for field in request.fields)
        if not has_primary_key:
            raise HTTPException(
                status_code=400,
                detail="Schema must have at least one primary key field"
            )

        # Validate field names are unique
        field_names = [field.name for field in request.fields]
        if len(field_names) != len(set(field_names)):
            raise HTTPException(
                status_code=400,
                detail="Field names must be unique"
            )

        # Create schema
        schema_id = _generate_schema_id()
        now = _get_timestamp()

        schema = SchemaResponse(
            id=schema_id,
            name=request.name,
            description=request.description,
            platform_id=request.platform_id,
            fields=request.fields,
            indexes=request.indexes,
            status="active",
            created_at=now,
            updated_at=now
        )

        schemas_db[schema_id] = schema
        logger.info(f"Schema created: {schema_id}")
        return schema

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating schema: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=SchemaListResponse)
async def list_schemas(
    platform_id: Optional[str] = Query(None, description="Filter by platform ID"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(get_current_active_user)
):
    """
    List all schemas

    - Supports pagination
    - Filter by platform ID
    - Returns paginated list of schemas

    **Authentication required**
    """
    try:
        # Filter schemas
        filtered_schemas = [
            schema for schema in schemas_db.values()
            if platform_id is None or schema.platform_id == platform_id
        ]

        # Paginate
        start = (page - 1) * per_page
        end = start + per_page
        paginated_schemas = filtered_schemas[start:end]

        return SchemaListResponse(
            schemas=paginated_schemas,
            total=len(filtered_schemas),
            page=page,
            per_page=per_page
        )

    except Exception as e:
        logger.error(f"Error listing schemas: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{schema_id}", response_model=SchemaResponse)
async def get_schema(schema_id: str, current_user: dict = Depends(get_current_active_user)):
    """
    Get schema details by ID

    - Returns full schema definition
    - Includes fields and indexes
    - 404 if schema not found

    **Authentication required**
    """
    if schema_id not in schemas_db:
        raise HTTPException(status_code=404, detail="Schema not found")
    return schemas_db[schema_id]


@router.put("/{schema_id}", response_model=SchemaResponse)
async def update_schema(schema_id: str, request: SchemaUpdateRequest, current_user: dict = Depends(get_current_active_user)):
    """
    Update an existing schema

    - Can update description, fields, or indexes
    - Validates field and index changes
    - 404 if schema not found

    **Authentication required**
    """
    if schema_id not in schemas_db:
        raise HTTPException(status_code=404, detail="Schema not found")

    try:
        logger.info(f"Updating schema: {schema_id}")

        schema = schemas_db[schema_id]

        # Update fields if provided
        if request.fields is not None:
            # Validate at least one primary key exists
            has_primary_key = any(field.primary_key for field in request.fields)
            if not has_primary_key:
                raise HTTPException(
                    status_code=400,
                    detail="Schema must have at least one primary key field"
                )

            # Validate field names are unique
            field_names = [field.name for field in request.fields]
            if len(field_names) != len(set(field_names)):
                raise HTTPException(
                    status_code=400,
                    detail="Field names must be unique"
                )

            schema.fields = request.fields

        # Update description if provided
        if request.description is not None:
            schema.description = request.description

        # Update indexes if provided
        if request.indexes is not None:
            schema.indexes = request.indexes

        # Update timestamp
        schema.updated_at = _get_timestamp()

        logger.info(f"Schema updated: {schema_id}")
        return schema

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating schema: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{schema_id}")
async def delete_schema(schema_id: str, current_user: dict = Depends(get_current_active_user)):
    """
    Delete a schema

    - Removes schema from database
    - 404 if schema not found
    - Returns success message

    **Authentication required**
    """
    if schema_id not in schemas_db:
        raise HTTPException(status_code=404, detail="Schema not found")

    try:
        del schemas_db[schema_id]
        logger.info(f"Schema deleted: {schema_id}")
        return {"message": "Schema deleted successfully"}

    except Exception as e:
        logger.error(f"Error deleting schema: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{schema_id}/validate")
async def validate_schema(schema_id: str, current_user: dict = Depends(get_current_active_user)):
    """
    Validate a schema

    - Checks field definitions
    - Validates index configurations
    - Ensures schema consistency
    - Returns validation results

    **Authentication required**
    """
    if schema_id not in schemas_db:
        raise HTTPException(status_code=404, detail="Schema not found")

    try:
        schema = schemas_db[schema_id]
        errors = []
        warnings = []

        # Validate fields
        if not schema.fields:
            errors.append("Schema must have at least one field")

        # Validate primary key
        primary_keys = [f for f in schema.fields if f.primary_key]
        if len(primary_keys) == 0:
            errors.append("Schema must have at least one primary key")
        elif len(primary_keys) > 1:
            warnings.append("Multiple primary keys detected")

        # Validate field names are unique
        field_names = [f.name for f in schema.fields]
        if len(field_names) != len(set(field_names)):
            errors.append("Field names must be unique")

        # Validate indexes
        for index in schema.indexes:
            if not index.fields:
                errors.append(f"Index '{index.name}' must have at least one field")

            # Check if indexed fields exist
            for field_name in index.fields:
                if field_name not in field_names:
                    errors.append(
                        f"Index '{index.name}' references non-existent field '{field_name}'"
                    )

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "schema_id": schema_id
        }

    except Exception as e:
        logger.error(f"Error validating schema: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{schema_id}/sql")
async def generate_sql(schema_id: str, current_user: dict = Depends(get_current_active_user)):
    """
    Generate SQL CREATE TABLE statement for schema

    - Generates ClickHouse-compatible SQL
    - Includes field definitions and indexes
    - Returns SQL statement

    **Authentication required**
    """
    if schema_id not in schemas_db:
        raise HTTPException(status_code=404, detail="Schema not found")

    try:
        schema = schemas_db[schema_id]

        # Generate field definitions
        field_defs = []
        for field in schema.fields:
            type_mapping = {
                'string': 'String',
                'integer': 'Int64',
                'float': 'Float64',
                'boolean': 'UInt8',
                'datetime': 'DateTime',
                'date': 'Date',
                'json': 'String'
            }

            nullable_suffix = '' if field.primary_key else ' Nullable'

            field_def = f"    {field.name} {type_mapping.get(field.type, 'String')}{nullable_suffix}"
            field_defs.append(field_def)

        # Generate CREATE TABLE statement
        sql = f"""-- Schema: {schema.name}
-- Platform: {schema.platform_id}
-- Created: {schema.created_at}

CREATE TABLE IF NOT EXISTS {schema.name} (
{',\\n'.join(field_defs)}
) ENGINE = MergeTree()
ORDER BY ({', '.join([f.name for f in schema.fields if f.primary_key])});
"""

        return {
            "sql": sql,
            "schema_id": schema_id,
            "schema_name": schema.name
        }

    except Exception as e:
        logger.error(f"Error generating SQL: {e}")
        raise HTTPException(status_code=500, detail=str(e))
