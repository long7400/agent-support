"""Async SQLAlchemy database service for user and session operations."""

from typing import (
    List,
    Optional,
)

from fastapi import HTTPException
from sqlalchemy import (
    select,
    text,
)

from app.infra.config import settings
from app.infra.database import (
    AsyncSessionLocal,
    async_engine,
)
from app.infra.logging import logger
from app.models.session import Session as ChatSession
from app.models.user import User


class DatabaseService:
    """Service class for database operations.

    This class handles all database operations for Users, Sessions, and Messages.
    It uses SQLAlchemy 2.0 async sessions and maintains a connection pool.
    """

    def __init__(self):
        """Initialize database service with connection pool."""
        self.engine = async_engine
        self.sessionmaker = AsyncSessionLocal
        logger.info(
            "database_initialized",
            environment=settings.ENVIRONMENT.value,
            pool_size=settings.POSTGRES_POOL_SIZE,
            max_overflow=settings.POSTGRES_MAX_OVERFLOW,
        )

    async def create_user(self, email: str, password: str, username: str | None = None) -> User:
        """Create a new user.

        Args:
            email: User's email address
            password: Hashed password
            username: Optional display name

        Returns:
            User: The created user
        """
        async with self.sessionmaker() as session:
            user = User(email=email, hashed_password=password, username=username)
            session.add(user)
            await session.commit()
            await session.refresh(user)
            logger.info("user_created", email=email)
            return user

    async def get_user(self, user_id: int) -> Optional[User]:
        """Get a user by ID.

        Args:
            user_id: The ID of the user to retrieve

        Returns:
            Optional[User]: The user if found, None otherwise
        """
        async with self.sessionmaker() as session:
            user = await session.get(User, user_id)
            return user

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get a user by email.

        Args:
            email: The email of the user to retrieve

        Returns:
            Optional[User]: The user if found, None otherwise
        """
        async with self.sessionmaker() as session:
            statement = select(User).where(User.email == email)
            result = await session.execute(statement)
            return result.scalar_one_or_none()

    async def delete_user_by_email(self, email: str) -> bool:
        """Delete a user by email.

        Args:
            email: The email of the user to delete

        Returns:
            bool: True if deletion was successful, False if user not found
        """
        async with self.sessionmaker() as session:
            result = await session.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()
            if not user:
                return False

            await session.delete(user)
            await session.commit()
            logger.info("user_deleted", email=email)
            return True

    async def create_session(
        self, session_id: str, user_id: int, name: str = "", username: str | None = None
    ) -> ChatSession:
        """Create a new chat session.

        Args:
            session_id: The ID for the new session
            user_id: The ID of the user who owns the session
            name: Optional name for the session (defaults to empty string)
            username: Display name copied from the user for LLM personalization

        Returns:
            ChatSession: The created session
        """
        async with self.sessionmaker() as session:
            chat_session = ChatSession(id=session_id, user_id=user_id, name=name, username=username)
            session.add(chat_session)
            await session.commit()
            await session.refresh(chat_session)
            logger.info("session_created", session_id=session_id, user_id=user_id, name=name)
            return chat_session

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session by ID.

        Args:
            session_id: The ID of the session to delete

        Returns:
            bool: True if deletion was successful, False if session not found
        """
        async with self.sessionmaker() as session:
            chat_session = await session.get(ChatSession, session_id)
            if not chat_session:
                return False

            await session.delete(chat_session)
            await session.commit()
            logger.info("session_deleted", session_id=session_id)
            return True

    async def get_session(self, session_id: str) -> Optional[ChatSession]:
        """Get a session by ID.

        Args:
            session_id: The ID of the session to retrieve

        Returns:
            Optional[ChatSession]: The session if found, None otherwise
        """
        async with self.sessionmaker() as session:
            chat_session = await session.get(ChatSession, session_id)
            return chat_session

    async def get_user_sessions(self, user_id: int) -> List[ChatSession]:
        """Get all sessions for a user.

        Args:
            user_id: The ID of the user

        Returns:
            List[ChatSession]: List of user's sessions
        """
        async with self.sessionmaker() as session:
            statement = select(ChatSession).where(ChatSession.user_id == user_id).order_by(ChatSession.created_at)
            result = await session.execute(statement)
            return list(result.scalars().all())

    async def update_session_name(self, session_id: str, name: str) -> ChatSession:
        """Update a session's name.

        Args:
            session_id: The ID of the session to update
            name: The new name for the session

        Returns:
            ChatSession: The updated session

        Raises:
            HTTPException: If session is not found
        """
        async with self.sessionmaker() as session:
            chat_session = await session.get(ChatSession, session_id)
            if not chat_session:
                raise HTTPException(status_code=404, detail="Session not found")

            chat_session.name = name
            session.add(chat_session)
            await session.commit()
            await session.refresh(chat_session)
            logger.info("session_name_updated", session_id=session_id, name=name)
            return chat_session

    def get_session_maker(self):
        """Get a session maker for creating database sessions.

        Returns:
            async_sessionmaker: A SQLAlchemy async session maker.
        """
        return self.sessionmaker

    async def health_check(self) -> bool:
        """Check database connection health.

        Returns:
            bool: True if database is healthy, False otherwise
        """
        try:
            async with self.sessionmaker() as session:
                await session.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.exception("database_health_check_failed", error=str(e))
            return False


# Create a singleton instance
database_service = DatabaseService()
