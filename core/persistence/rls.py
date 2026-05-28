from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from core.persistence.db import create_session_factory


def set_tenant_context(session: Session, tenant_id: UUID) -> None:
    session.execute(
        text("SELECT set_config('app.current_tenant', :tenant_id, true)"),
        {"tenant_id": str(tenant_id)},
    )


@contextmanager
def tenant_session(
    tenant_id: UUID,
    factory: sessionmaker[Session] | None = None,
) -> Iterator[Session]:
    session_factory = factory or create_session_factory()
    with session_factory() as session, session.begin():
        set_tenant_context(session, tenant_id)
        yield session
