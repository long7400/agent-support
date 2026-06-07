"""Helpers for transaction-scoped tenant context."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.logging import bind_context


async def set_local_tenant_context(session: AsyncSession, tenant_id: UUID) -> None:
    """Set PostgreSQL RLS tenant context for the current transaction."""
    # Equivalent to SET LOCAL app.current_tenant, but bind-safe with asyncpg.
    await session.execute(
        text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )
    bind_context(tenant_id=str(tenant_id))


@asynccontextmanager
async def with_tenant_context(session: AsyncSession, tenant_id: UUID) -> AsyncIterator[AsyncSession]:
    """Open a transaction and set PostgreSQL RLS tenant context with SET LOCAL."""
    async with session.begin():
        await set_local_tenant_context(session, tenant_id)
        yield session
