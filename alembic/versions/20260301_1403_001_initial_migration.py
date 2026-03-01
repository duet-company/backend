"""Initial migration - Create all tables

Revision ID: 001
Revises:
Create Date: 2026-03-01 14:03:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create all database tables."""
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('full_name', sa.String(length=255), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)

    # Create data_sources table
    op.create_table(
        'data_sources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('source_type', sa.Enum('clickhouse', 'postgresql', 'mysql', 'snowflake', 'bigquery', 'redshift', 'mongodb', 'elasticsearch', name='datasourcetype'), nullable=False),
        sa.Column('connection_config', sa.JSON(), nullable=True),
        sa.Column('host', sa.String(length=255), nullable=True),
        sa.Column('port', sa.Integer(), nullable=True),
        sa.Column('database_name', sa.String(length=255), nullable=True),
        sa.Column('status', sa.Enum('active', 'inactive', 'error', 'connecting', name='datasourcestatus'), nullable=False),
        sa.Column('last_tested_at', sa.DateTime(), nullable=True),
        sa.Column('last_error_message', sa.Text(), nullable=True),
        sa.Column('is_default', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_data_sources_id'), 'data_sources', ['id'], unique=False)
    op.create_index(op.f('ix_data_sources_source_type'), 'data_sources', ['source_type'], unique=False)
    op.create_index(op.f('ix_data_sources_status'), 'data_sources', ['status'], unique=False)
    op.create_index(op.f('ix_data_sources_user_id'), 'data_sources', ['user_id'], unique=False)

    # Create schemas table
    op.create_table(
        'schemas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('data_source_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('table_count', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['data_source_id'], ['data_sources.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_schemas_data_source_id'), 'schemas', ['data_source_id'], unique=False)
    op.create_index(op.f('ix_schemas_id'), 'schemas', ['id'], unique=False)
    op.create_index(op.f('ix_schemas_name'), 'schemas', ['name'], unique=False)

    # Create tables table
    op.create_table(
        'tables',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('schema_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('row_count_estimate', sa.Integer(), nullable=True),
        sa.Column('column_count', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['schema_id'], ['schemas.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_tables_id'), 'tables', ['id'], unique=False)
    op.create_index(op.f('ix_tables_name'), 'tables', ['name'], unique=False)
    op.create_index(op.f('ix_tables_schema_id'), 'tables', ['schema_id'], unique=False)

    # Create columns table
    op.create_table(
        'columns',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('table_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('data_type', sa.String(length=100), nullable=False),
        sa.Column('is_nullable', sa.Boolean(), nullable=False),
        sa.Column('is_primary_key', sa.Boolean(), nullable=False),
        sa.Column('default_value', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('ordinal_position', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['table_id'], ['tables.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_columns_id'), 'columns', ['id'], unique=False)
    op.create_index(op.f('ix_columns_table_id'), 'columns', ['table_id'], unique=False)

    # Create queries table
    op.create_table(
        'queries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('natural_language', sa.Text(), nullable=False),
        sa.Column('generated_sql', sa.Text(), nullable=True),
        sa.Column('query_type', sa.Enum('natural_language', 'sql', 'metadata', 'schema_exploration', name='querytype'), nullable=False),
        sa.Column('status', sa.Enum('pending', 'running', 'completed', 'failed', 'cancelled', name='querystatus'), nullable=False),
        sa.Column('result_data', sa.JSON(), nullable=True),
        sa.Column('row_count', sa.Integer(), nullable=True),
        sa.Column('execution_time_ms', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_queries_id'), 'queries', ['id'], unique=False)
    op.create_index(op.f('ix_queries_status'), 'queries', ['status'], unique=False)
    op.create_index(op.f('ix_queries_user_id'), 'queries', ['user_id'], unique=False)


def downgrade() -> None:
    """Drop all database tables."""
    op.drop_index(op.f('ix_queries_user_id'), table_name='queries')
    op.drop_index(op.f('ix_queries_status'), table_name='queries')
    op.drop_index(op.f('ix_queries_id'), table_name='queries')
    op.drop_table('queries')

    op.drop_index(op.f('ix_columns_table_id'), table_name='columns')
    op.drop_index(op.f('ix_columns_id'), table_name='columns')
    op.drop_table('columns')

    op.drop_index(op.f('ix_tables_schema_id'), table_name='tables')
    op.drop_index(op.f('ix_tables_name'), table_name='tables')
    op.drop_index(op.f('ix_tables_id'), table_name='tables')
    op.drop_table('tables')

    op.drop_index(op.f('ix_schemas_name'), table_name='schemas')
    op.drop_index(op.f('ix_schemas_id'), table_name='schemas')
    op.drop_index(op.f('ix_schemas_data_source_id'), table_name='schemas')
    op.drop_table('schemas')

    op.drop_index(op.f('ix_data_sources_user_id'), table_name='data_sources')
    op.drop_index(op.f('ix_data_sources_status'), table_name='data_sources')
    op.drop_index(op.f('ix_data_sources_source_type'), table_name='data_sources')
    op.drop_index(op.f('ix_data_sources_id'), table_name='data_sources')
    op.drop_table('data_sources')

    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
