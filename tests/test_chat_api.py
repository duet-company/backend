"""
Tests for Chat API endpoints
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.main import app
from app.core.database import Base, get_db
from app.models.chat import Chat
from app.models.user import User
import json

# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db_session():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def test_user(db_session: Session):
    """Create a test user."""
    user = User(
        email="test@example.com",
        hashed_password="hashed_password_here",
        full_name="Test User",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def test_chat(db_session: Session, test_user: User):
    """Create a test chat."""
    chat = Chat(
        user_id=test_user.id,
        title="Test Chat",
        messages=[
            {
                "role": "user",
                "content": "Hello",
                "timestamp": "2026-03-02T14:00:00",
                "metadata": {}
            },
            {
                "role": "assistant",
                "content": "Hi there!",
                "timestamp": "2026-03-02T14:00:01",
                "metadata": {}
            }
        ],
        context={"test": "data"},
        status="active"
    )
    db_session.add(chat)
    db_session.commit()
    db_session.refresh(chat)
    return chat


@pytest.fixture
def client(db_session: Session):
    """Create a test client with database dependency override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.mark.integration
class TestChatModel:
    """Tests for Chat model."""

    def test_create_chat(self, db_session: Session, test_user: User):
        """Test creating a chat."""
        chat = Chat(
            user_id=test_user.id,
            title="New Chat",
            messages=[],
            context={},
            status="active"
        )
        db_session.add(chat)
        db_session.commit()

        assert chat.id is not None
        assert chat.title == "New Chat"
        assert chat.user_id == test_user.id

    def test_add_message(self, db_session: Session, test_user: User):
        """Test adding a message to chat."""
        chat = Chat(
            user_id=test_user.id,
            title="Chat",
            messages=[],
            context={},
            status="active"
        )
        db_session.add(chat)
        db_session.commit()

        chat.add_message("user", "Test message", {"key": "value"})
        db_session.commit()

        assert len(chat.messages) == 1
        assert chat.messages[0]["role"] == "user"
        assert chat.messages[0]["content"] == "Test message"
        assert chat.messages[0]["metadata"]["key"] == "value"

    def test_update_context(self, db_session: Session, test_user: User):
        """Test updating chat context."""
        chat = Chat(
            user_id=test_user.id,
            title="Chat",
            messages=[],
            context={},
            status="active"
        )
        db_session.add(chat)
        db_session.commit()

        chat.update_context("query", "SELECT * FROM table")
        db_session.commit()

        assert chat.context["query"] == "SELECT * FROM table"

    def test_get_last_n_messages(self, db_session: Session, test_user: User):
        """Test getting last N messages."""
        chat = Chat(
            user_id=test_user.id,
            title="Chat",
            messages=[],
            context={},
            status="active"
        )
        db_session.add(chat)
        db_session.commit()

        # Add 5 messages
        for i in range(5):
            chat.add_message("user", f"Message {i+1}")

        db_session.commit()

        # Get last 3 messages
        last_3 = chat.get_last_n_messages(3)
        assert len(last_3) == 3
        assert last_3[0]["content"] == "Message 3"
        assert last_3[2]["content"] == "Message 5"


@pytest.mark.integration
class TestChatAPI:
    """Tests for Chat API endpoints."""

    def test_get_suggestions(self, client: TestClient):
        """Test getting message suggestions."""
        response = client.get("/api/v1/chat/suggestions")
        assert response.status_code == 200

        data = response.json()
        assert "suggestions" in data
        assert len(data["suggestions"]) > 0

    def test_get_chat_history_unauthorized(self, client: TestClient):
        """Test getting chat history without authentication."""
        response = client.get("/api/v1/chat/history")
        assert response.status_code == 401

    def test_send_message_unauthorized(self, client: TestClient):
        """Test sending a message without authentication."""
        response = client.post(
            "/api/v1/chat/send",
            json={"message": "Test message"}
        )
        assert response.status_code == 401

    def test_delete_chat_unauthorized(self, client: TestClient):
        """Test deleting a chat without authentication."""
        response = client.delete("/api/v1/chat/1")
        assert response.status_code == 401

    def test_get_chat_unauthorized(self, client: TestClient):
        """Test getting a chat without authentication."""
        response = client.get("/api/v1/chat/1")
        assert response.status_code == 401


@pytest.mark.integration
class TestChatMessageHandling:
    """Tests for chat message handling."""

    def test_message_json_serialization(self, test_chat: Chat):
        """Test that messages can be serialized to JSON."""
        chat_dict = test_chat.to_dict()
        assert "messages" in chat_dict
        assert len(chat_dict["messages"]) == 2
        assert chat_dict["messages"][0]["role"] == "user"

    def test_context_json_serialization(self, test_chat: Chat):
        """Test that context can be serialized to JSON."""
        chat_dict = test_chat.to_dict()
        assert "context" in chat_dict
        assert chat_dict["context"]["test"] == "data"

    def test_chat_to_dict(self, test_chat: Chat):
        """Test chat to_dict method."""
        chat_dict = test_chat.to_dict()

        assert chat_dict["id"] == test_chat.id
        assert chat_dict["title"] == test_chat.title
        assert chat_dict["status"] == test_chat.status
        assert "created_at" in chat_dict
        assert "updated_at" in chat_dict
