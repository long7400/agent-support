from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from core.config import get_settings


def create_session_factory(database_url: str | None = None) -> sessionmaker[Session]:
    url = database_url or get_settings().database_url
    engine = create_engine(url, pool_pre_ping=True)
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def create_admin_session_factory() -> sessionmaker[Session]:
    return create_session_factory(get_settings().database_admin_url)


@contextmanager
def session_scope(factory: sessionmaker[Session] | None = None) -> Iterator[Session]:
    session_factory = factory or create_session_factory()
    with session_factory() as session, session.begin():
        yield session


@contextmanager
def admin_session_scope(factory: sessionmaker[Session] | None = None) -> Iterator[Session]:
    session_factory = factory or create_admin_session_factory()
    with session_factory() as session, session.begin():
        yield session
