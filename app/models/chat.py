"""
Chat Database Model

SQLAlchemy model for storing conversations between users and AI agents.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, JSON, DateTime, Text
from sqlalchemy.orm import relationship
from app.core.database import Base


class Chat(Base):
    """
    Chat model for storing conversation history and context.

    Attributes:
        id: Primary key
        user_id: Foreign key to User
        title: Optional title for the conversation
        messages: JSON array of message objects
        context: JSON object storing conversation context (previous queries, state)
        status: Chat status (active, archived, deleted)
        created_at: Creation timestamp
        updated_at: Last update timestamp
    """
    __tablename__ = "chats"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    title = Column(String(255), nullable=True)
    messages = Column(JSON, nullable=False, default=list)
    context = Column(JSON, nullable=False, default=dict)
    status = Column(String(50), default="active", nullable=False)  # active, archived, deleted
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f"<Chat(id={self.id}, user_id={self.user_id}, title={self.title}, status={self.status})>"

    def to_dict(self):
        """Convert chat object to dictionary."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "messages": self.messages,
            "context": self.context,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

    def add_message(self, role: str, content: str, metadata: dict = None):
        """
        Add a message to the chat.

        Args:
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional metadata (timestamps, tokens, etc.)
        """
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": metadata or {}
        }
        self.messages.append(message)
        self.updated_at = datetime.utcnow()

    def update_context(self, key: str, value: any):
        """
        Update a key in the conversation context.

        Args:
            key: Context key
            value: Context value
        """
        if self.context is None:
            self.context = {}
        self.context[key] = value
        self.updated_at = datetime.utcnow()

    def get_last_n_messages(self, n: int):
        """
        Get the last N messages from the chat.

        Args:
            n: Number of messages to retrieve

        Returns:
            List of the last N messages
        """
        return self.messages[-n:] if self.messages else []

    def save(self):
        """
        Save the chat to the database.

        Note: This is a convenience method that should be used within a session.
        """
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            db.add(self)
            db.commit()
            db.refresh(self)
        finally:
            db.close()

    def delete(self):
        """
        Delete the chat from the database.

        Note: This is a convenience method that should be used within a session.
        """
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            db.delete(self)
            db.commit()
        finally:
            db.close()
