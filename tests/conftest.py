"""Shared pytest fixtures for the calculator backend test suite."""

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

    Uses ``StaticPool`` so every connection shares the same in-memory
    database across sessions created from this engine.
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
def db_session(sqlite_session_factory) -> Generator[Session, None, None]:
    """A single SQLAlchemy session bound to the in-memory SQLite database."""
    session = sqlite_session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(sqlite_session_factory) -> Generator[TestClient, None, None]:
    """A FastAPI test client with ``get_db`` overridden to use SQLite."""

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
