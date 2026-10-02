"""Shared pytest fixtures for the calculator backend test suite.

The fixtures in this module ensure the normal automated suite never
contacts MySQL. ``isolated_app`` patches ``app.main.engine`` and
``app.main.SessionLocal`` to the in-memory SQLite engine so that both
the application lifespan (which calls ``Base.metadata.create_all``)
and the ``/health`` endpoint operate against SQLite.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database.database import Base, get_db
from app.main import app


@pytest.fixture
def sqlite_engine():
    """An in-memory SQLite engine with the application schema created.

    ``StaticPool`` keeps a single shared connection so every session
    created from this engine sees the same in-memory database.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def sqlite_session_factory(sqlite_engine):
    """A ``sessionmaker`` bound to the in-memory SQLite engine."""
    return sessionmaker(
        bind=sqlite_engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
        class_=Session,
    )


@pytest.fixture
def isolated_app(monkeypatch, sqlite_engine, sqlite_session_factory):
    """Patch ``app.main.engine`` and ``app.main.SessionLocal`` to SQLite.

    With this fixture active, the application lifespan and the
    ``/health`` endpoint operate against the in-memory SQLite engine,
    so the normal automated suite never contacts MySQL.
    """
    monkeypatch.setattr("app.main.engine", sqlite_engine)
    monkeypatch.setattr("app.main.SessionLocal", sqlite_session_factory)
    yield app


@pytest.fixture
def db_session(sqlite_session_factory) -> Generator[Session, None, None]:
    """A single SQLAlchemy session bound to the in-memory SQLite database."""
    session = sqlite_session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(isolated_app, sqlite_session_factory) -> Generator[TestClient, None, None]:
    """A FastAPI test client fully isolated from MySQL.

    ``isolated_app`` ensures the application lifespan and ``/health``
    use SQLite. This fixture additionally overrides ``get_db`` so that
    request handlers also receive SQLite sessions.
    """

    def _override_get_db() -> Generator[Session, None, None]:
        session = sqlite_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def isolated_test_client(isolated_app):
    """A bare ``TestClient`` whose MySQL-backed modules are patched to SQLite.

    Tests that need to install their own ``get_db`` override (for example
    to inject a failing session) should use this fixture and apply their
    own override inside the test body.
    """
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
