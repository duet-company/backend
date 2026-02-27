"""
Authentication Service

Business logic for user authentication and management.
"""

from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.user import User
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    decode_access_token
)
from app.auth.schemas import UserCreate, UserLogin, Token


class AuthService:
    """Service for handling authentication operations."""

    @staticmethod
    def create_user(db: Session, user_data: UserCreate) -> User:
        """
        Create a new user in the database.

        Args:
            db: Database session
            user_data: User creation data

        Returns:
            User: The created user

        Raises:
            ValueError: If user with email already exists
        """
        # Check if user already exists
        existing_user = db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise ValueError(f"User with email {user_data.email} already exists")

        # Create new user
        hashed_password = get_password_hash(user_data.password)
        new_user = User(
            email=user_data.email,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            is_active=True
        )

        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        return new_user

    @staticmethod
    def authenticate_user(db: Session, credentials: UserLogin) -> Optional[User]:
        """
        Authenticate a user with email and password.

        Args:
            db: Database session
            credentials: User login credentials

        Returns:
            User: The authenticated user if credentials are valid, None otherwise
        """
        user = db.query(User).filter(User.email == credentials.email).first()

        if not user:
            return None

        if not verify_password(credentials.password, user.hashed_password):
            return None

        return user

    @staticmethod
    def create_token_for_user(user: User) -> Token:
        """
        Create a JWT access token for a user.

        Args:
            user: The user to create a token for

        Returns:
            Token: The JWT token response
        """
        access_token = create_access_token(
            data={"sub": user.email, "user_id": user.id}
        )

        return Token(
            access_token=access_token,
            token_type="bearer",
            expires_in=3600  # 1 hour default
        )

    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Optional[User]:
        """
        Get a user by email address.

        Args:
            db: Database session
            email: User's email address

        Returns:
            User: The user if found, None otherwise
        """
        return db.query(User).filter(User.email == email).first()

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
        """
        Get a user by ID.

        Args:
            db: Database session
            user_id: User's ID

        Returns:
            User: The user if found, None otherwise
        """
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def update_user_password(db: Session, user: User, new_password: str) -> User:
        """
        Update a user's password.

        Args:
            db: Database session
            user: The user to update
            new_password: The new plain text password

        Returns:
            User: The updated user
        """
        user.hashed_password = get_password_hash(new_password)
        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)

        return user

    @staticmethod
    def deactivate_user(db: Session, user_id: int) -> Optional[User]:
        """
        Deactivate a user account.

        Args:
            db: Database session
            user_id: The ID of the user to deactivate

        Returns:
            User: The deactivated user if found, None otherwise
        """
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None

        user.is_active = False
        user.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(user)

        return user
