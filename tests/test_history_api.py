"""End-to-end tests for ``GET /api/history``."""

from __future__ import annotations

from collections.abc import Generator
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.main import app


def test_empty_history_returns_200_with_empty_list(client: TestClient) -> None:
    response = client.get("/api/history")
    assert response.status_code == 200
    assert response.json() == {"success": True, "history": []}


def test_history_appears_after_successful_calculate(client: TestClient) -> None:
    calc = client.post("/api/calculate", json={"expression": "(1+2)*3"})
    assert calc.status_code == 200
    assert calc.json()["result"] == "9"

    response = client.get("/api/history")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert isinstance(body["history"], list)
    assert len(body["history"]) == 1

    item = body["history"][0]
    assert item["expression"] == "(1+2)*3"
    assert item["result"] == "9"
    assert isinstance(item["id"], int)
    assert isinstance(item["created_at"], str)


def test_history_is_returned_newest_first(client: TestClient) -> None:
    for expr in ("1+1", "2+2", "3+3"):
        client.post("/api/calculate", json={"expression": expr})

    response = client.get("/api/history")
    assert response.status_code == 200
    history = response.json()["history"]
    assert [item["expression"] for item in history] == ["3+3", "2+2", "1+1"]
    ids = [item["id"] for item in history]
    assert ids == sorted(ids, reverse=True)


def test_history_created_at_is_serializable(client: TestClient) -> None:
    client.post("/api/calculate", json={"expression": "1+2"})

    response = client.get("/api/history")
    history = response.json()["history"]
    assert len(history) == 1
    parsed = datetime.fromisoformat(history[0]["created_at"])
    assert isinstance(parsed, datetime)


def test_invalid_calculations_are_absent_from_history(client: TestClient) -> None:
    client.post("/api/calculate", json={"expression": "1+2"})
    before = client.get("/api/history").json()["history"]
    assert len(before) == 1

    invalid_resp = client.post("/api/calculate", json={"expression": "1/0"})
    assert invalid_resp.status_code == 400

    after = client.get("/api/history").json()["history"]
    assert len(after) == 1
    expressions = {item["expression"] for item in after}
    assert "1/0" not in expressions


def test_history_persists_across_fresh_db_sessions(
    client: TestClient, sqlite_session_factory
) -> None:
    """The read path must observe rows committed by a previous session.

    A row is written via one SQLAlchemy session (the request that handled
    ``POST /api/calculate``). That session is closed when the request
    ends. A second, freshly created session then issues
    ``GET /api/history`` and must see the previously committed row.
    """
    from app.models.calculation_history import CalculationHistory

    calc_response = client.post("/api/calculate", json={"expression": "(1+2)*3"})
    assert calc_response.status_code == 200

    new_session: Session = sqlite_session_factory()
    try:
        rows = new_session.query(CalculationHistory).all()
        assert len(rows) == 1
        assert rows[0].expression == "(1+2)*3"
        assert rows[0].result == "9"
        posted_id = rows[0].id
    finally:
        new_session.close()

    history_response = client.get("/api/history")
    assert history_response.status_code == 200
    body = history_response.json()
    assert body["history"]
    ids = [item["id"] for item in body["history"]]
    assert posted_id in ids


def test_history_database_failure_returns_safe_500(
    isolated_test_client: TestClient,
) -> None:
    """A read failure must yield 500 + a sanitized body."""
    db = MagicMock(spec=Session)
    db.query.side_effect = OperationalError(
        "SELECT * FROM calculation_history",
        params=None,
        orig=Exception("password=hunter2, host=10.0.0.1"),
    )

    def _override() -> MagicMock:
        return db

    app.dependency_overrides[get_db] = _override
    response = isolated_test_client.get("/api/history")

    assert response.status_code == 500
    body = response.json()
    assert body == {"success": False, "message": "Internal server error"}
    assert "password" not in str(body)
    assert "host" not in str(body)
    assert "Traceback" not in str(body)


def test_history_appears_in_openapi(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    assert "/api/history" in spec["paths"]
    assert "get" in spec["paths"]["/api/history"]
    assert "post" in spec["paths"]["/api/calculate"]
    assert "get" in spec["paths"]["/health"]


def test_history_route_uses_get_db_not_sessionlocal_directly(
    client: TestClient, monkeypatch
) -> None:
    """The history route must receive its session from ``Depends(get_db)``.

    If a future regression hardcoded ``SessionLocal`` inside the route,
    the ``get_db`` override applied by the ``client`` fixture would no
    longer take effect and this assertion would fail.
    """

    def _explode() -> None:
        raise AssertionError("get_db was bypassed")

    monkeypatch.setattr(
        "app.database.database.SessionLocal", _explode
    )

    response = client.get("/api/history")
    assert response.status_code == 200
