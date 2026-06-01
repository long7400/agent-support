"""User persistence model."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

import bcrypt
from sqlalchemy import String
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)

from app.models.base import (
    Base,
    TimestampMixin,
)

if TYPE_CHECKING:
    from app.models.session import Session


class User(TimestampMixin, Base):
    """User model for storing user accounts.

    Attributes:
        id: The primary key
        email: User's email (unique)
        hashed_password: Bcrypt hashed password
        username: Optional display name for the user
        created_at: When the user was created
        sessions: Relationship to user's chat sessions
    """

    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    sessions: Mapped[list[Session]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def verify_password(self, password: str) -> bool:
        """Verify if the provided password matches the hash."""
        return bcrypt.checkpw(password.encode("utf-8"), self.hashed_password.encode("utf-8"))

    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt."""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")
