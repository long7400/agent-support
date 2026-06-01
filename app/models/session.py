"""Chat session persistence model."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
)

from sqlalchemy import (
    ForeignKey,
    String,
)
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
    from app.models.user import User


class Session(TimestampMixin, Base):
    """Session model for storing chat sessions.

    Attributes:
        id: The primary key
        user_id: Foreign key to the user
        name: Name of the session (defaults to empty string)
        username: Display name copied from the user at session creation
        created_at: When the session was created
        messages: Relationship to session messages
        user: Relationship to the session owner
    """

    __tablename__ = "session"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String, default="", server_default="", nullable=False)
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    user: Mapped[User] = relationship(back_populates="sessions")
