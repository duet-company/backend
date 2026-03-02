"""
Query Database Model

SQLAlchemy model for storing user queries and their execution results.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.orm import relationship
from app.core.database import Base
import enum


class QueryStatus(str, enum.Enum):
    """Query execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class QueryType(str, enum.Enum):
    """Query type classification."""
    NATURAL_LANGUAGE = "natural_language"
    SQL = "sql"
    METADATA = "metadata"
    SCHEMA_EXPLORATION = "schema_exploration"


class Query(Base):
    """
    Query model for storing user queries.

    Attributes:
        id: Primary key
        user_id: Foreign key to user who created the query
        natural_language: Original natural language query text
        generated_sql: Generated SQL query (if applicable)
        query_type: Type of query (NL, SQL, etc.)
        status: Current execution status
        result_data: Query result data (JSON)
        row_count: Number of rows returned
        execution_time_ms: Query execution time in milliseconds
        error_message: Error message if query failed
        created_at: Query creation timestamp
        updated_at: Last update timestamp
        completed_at: Query completion timestamp
    """
    __tablename__ = "queries"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    natural_language = Column(Text, nullable=False)
    generated_sql = Column(Text, nullable=True)
    query_type = Column(Enum(QueryType), default=QueryType.NATURAL_LANGUAGE, nullable=False)
    status = Column(Enum(QueryStatus), default=QueryStatus.PENDING, nullable=False, index=True)
    result_data = Column(JSON, nullable=True)
    row_count = Column(Integer, nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", backref="queries")

    def __repr__(self):
        return f"<Query(id={self.id}, user_id={self.user_id}, status={self.status})>"

    def to_dict(self):
        """Convert query object to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "natural_language": self.natural_language,
            "generated_sql": self.generated_sql,
            "query_type": self.query_type.value,
            "status": self.status.value,
            "row_count": self.row_count,
            "execution_time_ms": self.execution_time_ms,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }

    def mark_completed(self, result_data=None, row_count=None, execution_time_ms=None):
        """Mark query as completed with results."""
        self.status = QueryStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        self.result_data = result_data
        self.row_count = row_count
        self.execution_time_ms = execution_time_ms
        self.save()

    def mark_failed(self, error_message):
        """Mark query as failed with error message."""
        self.status = QueryStatus.FAILED
        self.completed_at = datetime.utcnow()
        self.error_message = error_message
        self.save()

    def save(self):
        """Save the query to the database."""
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            db.add(self)
            db.commit()
            db.refresh(self)
        finally:
            db.close()
