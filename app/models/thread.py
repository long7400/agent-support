"""LangGraph thread persistence model."""

from sqlalchemy import String
from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.models.base import (
    Base,
    TimestampMixin,
)


class Thread(TimestampMixin, Base):
    """Thread model for storing conversation threads.

    Attributes:
        id: The primary key
        created_at: When the thread was created
        messages: Relationship to messages in this thread
    """

    __tablename__ = "thread"

    id: Mapped[str] = mapped_column(String, primary_key=True)
