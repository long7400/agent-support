"""SQLAlchemy base classes for persistence models."""

from datetime import datetime, UTC

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base metadata registry for Alembic autogenerate."""


class TimestampMixin:
    """Common timestamp columns for application-owned tables."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
