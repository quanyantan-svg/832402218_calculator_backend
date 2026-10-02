"""End-to-end tests for ``DELETE /api/history/{history_id}``."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.main import app
from app.models.calculation_history import CalculationHistory


def _post_calculation(client: TestClient, expression: str) -> dict[str, object]:
    response = client.post("/api/calculate", json={"expression": expression})
    assert response.status_code == 200
    return response.json()


def test_delete_history_removes_record_round_trip(client: TestClient) -> None:
    posted = _post_calculation(client, "(1+2)*3")

    listed = client.get("/api/history").json()["history"]
    target_id = next(
        item["id"] for item in listed if item["expression"] == "(1+2)*3"
    )

    delete_response = client.delete(f"/api/history/{target_id}")
    assert delete_response.status_code == 200
    body = delete_response.json()
    assert body == {"success": True, "message": "History record deleted"}

    listed_after = client.get("/api/history").json()["history"]
    ids = [item["id"] for item in listed_after]
    assert target_id not in ids


def test_delete_history_keeps_other_rows(client: TestClient) -> None:
    keep1 = _post_calculation(client, "1+1")
    target = _post_calculation(client, "2+2")
    keep2 = _post_calculation(client, "3+3")

    listed = {item["expression"]: item["id"] for item in client.get("/api/history").json()["history"]}
    target_id = listed["2+2"]

    response = client.delete(f"/api/history/{target_id}")
    assert response.status_code == 200

    remaining = client.get("/api/history").json()["history"]
    remaining_expressions = {item["expression"] for item in remaining}
    assert remaining_expressions == {"1+1", "3+3"}

    # Also confirm the kept rows' ids match what POST returned via the
    # database view (i.e. they are the same persistent rows).
    remaining_ids = {item["id"] for item in remaining}
    assert listed["1+1"] in remaining_ids
    assert listed["3+3"] in remaining_ids


def test_delete_nonexistent_id_returns_404(client: TestClient) -> None:
    response = client.delete("/api/history/999999")
    assert response.status_code == 404
    body = response.json()
    assert body == {"success": False, "message": "History record not found"}


def test_delete_invalid_path_id_returns_client_error(client: TestClient) -> None:
    """Non-integer path parameter must produce a 4xx, never a 5xx."""
    response = client.delete("/api/history/abc")
    assert 400 <= response.status_code < 500
    body = response.json()
    assert body["success"] is False
    assert isinstance(body["message"], str)
    for forbidden in ("Traceback", "SQLAlchemy", "sqlite", "mysql", "pymysql"):
        assert forbidden not in str(body)


def test_delete_then_get_returns_empty_history_for_single_record(
    client: TestClient,
) -> None:
    posted = _post_calculation(client, "1+2")

    listed = client.get("/api/history").json()["history"]
    target_id = listed[0]["id"]

    response = client.delete(f"/api/history/{target_id}")
    assert response.status_code == 200

    after = client.get("/api/history").json()
    assert after == {"success": True, "history": []}


def test_delete_failure_returns_safe_500(
    isolated_test_client: TestClient,
) -> None:
    """A database failure during delete must yield 500 + a sanitized body."""

    class _FailingDeleteSession:
        def __init__(self) -> None:
            self.rollback_called = False

        def get(self, _model: type, _pk: int) -> CalculationHistory:
            return CalculationHistory(id=1, expression="1+1", result="2")

        def delete(self, _record: CalculationHistory) -> None:
            raise OperationalError(
                "DELETE ...", params=None, orig=Exception("password=hunter2, host=10.0.0.1")
            )

        def commit(self) -> None:
            pass

        def rollback(self) -> None:
            self.rollback_called = True

    session = _FailingDeleteSession()

    def _override() -> _FailingDeleteSession:
        return session

    app.dependency_overrides[get_db] = _override
    response = isolated_test_client.delete("/api/history/1")

    assert response.status_code == 500
    body = response.json()
    assert body == {"success": False, "message": "Internal server error"}
    assert "password" not in str(body)
    assert "host" not in str(body)
    assert "Traceback" not in str(body)
    assert session.rollback_called is True


def test_delete_appears_in_openapi(client: TestClient) -> None:
    spec = client.get("/openapi.json").json()
    paths = spec["paths"]
    assert "/health" in paths and "get" in paths["/health"]
    assert "/api/calculate" in paths and "post" in paths["/api/calculate"]
    assert "/api/history" in paths and "get" in paths["/api/history"]

    delete_paths = [p for p in paths if paths[p].get("delete")]
    assert any(p.startswith("/api/history/") for p in delete_paths), (
        f"no DELETE path for /api/history/{{id}}; paths={list(paths)}"
    )


def test_delete_is_real_database_state_not_filtering(
    client: TestClient, sqlite_session_factory
) -> None:
    """Prove the row is genuinely gone from the database after DELETE."""
    _post_calculation(client, "1+1")
    target = _post_calculation(client, "2+2")
    _post_calculation(client, "3+3")

    listed = client.get("/api/history").json()["history"]
    target_id = next(item["id"] for item in listed if item["expression"] == "2+2")
    keep1_id = next(item["id"] for item in listed if item["expression"] == "1+1")
    keep2_id = next(item["id"] for item in listed if item["expression"] == "3+3")

    delete_response = client.delete(f"/api/history/{target_id}")
    assert delete_response.status_code == 200

    # Open a fresh SQLAlchemy session to confirm the row is truly gone
    # from the underlying storage, not merely absent from a response.
    fresh_session: Session = sqlite_session_factory()
    try:
        rows = fresh_session.query(CalculationHistory).all()
        ids = {row.id for row in rows}
        assert target_id not in ids
        assert {keep1_id, keep2_id} == ids
    finally:
        fresh_session.close()

    # A fresh HTTP request must also still see the row as gone.
    after = client.get("/api/history").json()["history"]
    after_ids = [item["id"] for item in after]
    assert target_id not in after_ids


def test_delete_history_route_uses_get_db(client: TestClient, monkeypatch) -> None:
    """The DELETE route must receive its session from ``Depends(get_db)``.

    Hardcoding ``SessionLocal`` inside the route would bypass the
    dependency override that the test fixtures install.
    """
    _post_calculation(client, "1+1")
    listed = client.get("/api/history").json()["history"]
    target_id = listed[0]["id"]

    def _explode() -> None:
        raise AssertionError("get_db was bypassed")

    monkeypatch.setattr("app.database.database.SessionLocal", _explode)
    response = client.delete(f"/api/history/{target_id}")
    assert response.status_code == 200
