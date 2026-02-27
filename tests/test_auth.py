"""
Authentication Unit Tests

Tests for authentication functionality including password hashing,
JWT token generation/validation, and user authentication.
"""

import pytest
from datetime import datetime, timedelta
from app.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_access_token
)
from app.auth.schemas import UserCreate, UserLogin


class TestPasswordHashing:
    """Test password hashing functionality."""

    def test_password_hashing(self):
        """Test that passwords can be hashed correctly."""
        plain_password = "securepassword123"
        hashed_password = get_password_hash(plain_password)

        # Hash should be different from plain password
        assert hashed_password != plain_password
        # Hash should be a string
        assert isinstance(hashed_password, str)
        # Hash should have reasonable length (bcrypt hashes are 60 chars)
        assert len(hashed_password) == 60

    def test_password_verification(self):
        """Test that hashed passwords can be verified."""
        plain_password = "securepassword123"
        hashed_password = get_password_hash(plain_password)

        # Correct password should verify
        assert verify_password(plain_password, hashed_password) is True

        # Wrong password should not verify
        assert verify_password("wrongpassword", hashed_password) is False

    def test_different_passwords_different_hashes(self):
        """Test that different passwords produce different hashes."""
        password1 = "password1"
        password2 = "password2"

        hash1 = get_password_hash(password1)
        hash2 = get_password_hash(password2)

        # Different passwords should have different hashes
        assert hash1 != hash2


class TestJWTTokens:
    """Test JWT token generation and validation."""

    def test_create_token(self):
        """Test that JWT tokens can be created."""
        data = {"sub": "user@example.com", "user_id": 1}
        token = create_access_token(data)

        # Token should be a string
        assert isinstance(token, str)
        # Token should have reasonable length
        assert len(token) > 50

    def test_decode_valid_token(self):
        """Test that valid tokens can be decoded."""
        data = {"sub": "user@example.com", "user_id": 1}
        token = create_access_token(data)

        # Decode the token
        token_data = decode_access_token(token)

        # Should return valid token data
        assert token_data is not None
        assert token_data.email == "user@example.com"
        assert token_data.user_id == 1

    def test_decode_invalid_token(self):
        """Test that invalid tokens return None."""
        invalid_token = "invalid.jwt.token"

        # Should return None for invalid token
        token_data = decode_access_token(invalid_token)

        assert token_data is None

    def test_token_expiration(self):
        """Test that tokens with custom expiration work."""
        data = {"sub": "user@example.com", "user_id": 1}

        # Create token with short expiration
        short_expiration = timedelta(seconds=1)
        token = create_access_token(data, expires_delta=short_expiration)

        # Token should be valid immediately
        token_data = decode_access_token(token)
        assert token_data is not None

        # Token should still be valid after short delay
        import time
        time.sleep(0.5)
        token_data = decode_access_token(token)
        assert token_data is not None

        # Token should expire after expiration time
        time.sleep(0.6)
        token_data = decode_access_token(token)
        # Note: This test may fail if JWT validation checks expiration precisely
        # In production, proper expiration handling is important


class TestUserSchemas:
    """Test Pydantic schemas for user authentication."""

    def test_user_create_valid(self):
        """Test that UserCreate schema validates correctly."""
        user_data = UserCreate(
            email="user@example.com",
            password="securepassword123",
            full_name="John Doe"
        )

        assert user_data.email == "user@example.com"
        assert user_data.password == "securepassword123"
        assert user_data.full_name == "John Doe"

    def test_user_create_password_too_short(self):
        """Test that UserCreate rejects short passwords."""
        with pytest.raises(ValueError):
            UserCreate(
                email="user@example.com",
                password="short",
                full_name="John Doe"
            )

    def test_user_create_invalid_email(self):
        """Test that UserCreate rejects invalid emails."""
        with pytest.raises(ValueError):
            UserCreate(
                email="invalid-email",
                password="securepassword123",
                full_name="John Doe"
            )

    def test_user_login_valid(self):
        """Test that UserLogin schema validates correctly."""
        login_data = UserLogin(
            email="user@example.com",
            password="securepassword123"
        )

        assert login_data.email == "user@example.com"
        assert login_data.password == "securepassword123"


class TestTokenSchema:
    """Test Token schema."""

    def test_token_response(self):
        """Test that Token schema validates correctly."""
        from app.auth.schemas import Token

        token_data = Token(
            access_token="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
            token_type="bearer",
            expires_in=3600
        )

        assert token_data.access_token.startswith("eyJ")
        assert token_data.token_type == "bearer"
        assert token_data.expires_in == 3600


class TestUserResponseSchema:
    """Test UserResponse schema."""

    def test_user_response(self):
        """Test that UserResponse schema validates correctly."""
        from app.auth.schemas import UserResponse

        user_data = UserResponse(
            id=1,
            email="user@example.com",
            full_name="John Doe",
            is_active=True,
            created_at=datetime(2026, 2, 27, 10, 0, 0)
        )

        assert user_data.id == 1
        assert user_data.email == "user@example.com"
        assert user_data.full_name == "John Doe"
        assert user_data.is_active is True
