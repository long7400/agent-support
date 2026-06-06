"""Async SQLAlchemy database foundation for tenant-aware runtime code."""

from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager
from urllib.parse import quote_plus
from uuid import UUID

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings
from app.core.tenant_context import with_tenant_context


def build_database_url(driver: str) -> str:
    """Build a SQLAlchemy database URL from settings."""
    return (
        f"{driver}://"
        f"{quote_plus(settings.POSTGRES_USER)}:{quote_plus(settings.POSTGRES_PASSWORD)}"
        f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    )


def build_async_database_url() -> str:
    """Build the async SQLAlchemy database URL from settings."""
    return build_database_url("postgresql+asyncpg")


def build_sync_database_url() -> str:
    """Build the synchronous SQLAlchemy database URL for Alembic."""
    return build_database_url("postgresql+psycopg")


async_engine: AsyncEngine = create_async_engine(
    build_async_database_url(),
    pool_pre_ping=True,
    pool_size=settings.POSTGRES_POOL_SIZE,
    max_overflow=settings.POSTGRES_MAX_OVERFLOW,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncIterator[AsyncSession]:
    """Yield an async database session for FastAPI dependencies."""
    async with AsyncSessionLocal() as session:
        yield session


def tenant_transaction(session: AsyncSession, tenant_id: UUID) -> AbstractAsyncContextManager[AsyncSession]:
    """Backward-compatible alias for tenant-scoped transactions."""
    return with_tenant_context(session, tenant_id)
