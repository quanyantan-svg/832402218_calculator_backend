"""End-to-end tests for ``POST /api/calculate``."""

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.main import app
from app.models.calculation_history import CalculationHistory


@pytest.mark.parametrize(
    ("expression", "expected_result"),
    [
        ("1+2", "3"),
        ("1+2*3", "7"),
        ("(1+2)*3", "9"),
        ("0.1+0.2", "0.3"),
        ("3*-2", "-6"),
        ("5-8", "-3"),
        ("8/2", "4"),
        ("-(1+2)", "-3"),
        ("0.5*4", "2"),
    ],
)
def test_calculate_success(
    client: TestClient,
    expression: str,
    expected_result: str,
) -> None:
    response = client.post("/api/calculate", json={"expression": expression})
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["expression"] == expression
    assert body["result"] == expected_result


def test_calculate_persists_history_row(
    client: TestClient, db_session: Session
) -> None:
    before = db_session.query(CalculationHistory).count()
    response = client.post("/api/calculate", json={"expression": "(1+2)*3"})
    assert response.status_code == 200
    after = db_session.query(CalculationHistory).count()
    assert after == before + 1
    row = (
        db_session.query(CalculationHistory)
        .filter(CalculationHistory.expression == "(1+2)*3")
        .one()
    )
    assert row.result == "9"


@pytest.mark.parametrize(
    "expression",
    [
        "1+",
        "abc",
        "1**2",
        "1 2",
        "(1+2",
        "( )",
    ],
)
def test_calculate_invalid_expression_returns_client_error(
    client: TestClient, expression: str
) -> None:
    response = client.post("/api/calculate", json={"expression": expression})
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert isinstance(body["message"], str)
    assert body["message"]


def test_calculate_division_by_zero_returns_client_error(client: TestClient) -> None:
    response = client.post("/api/calculate", json={"expression": "1/0"})
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert "division" in body["message"].lower()


def test_calculate_division_by_zero_via_subexpression(client: TestClient) -> None:
    response = client.post("/api/calculate", json={"expression": "1/(2-2)"})
    assert response.status_code == 400
    assert response.json()["success"] is False


def test_calculate_missing_expression_field(client: TestClient) -> None:
    response = client.post("/api/calculate", json={})
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["message"] == "Invalid request"


def test_calculate_wrong_type_for_expression(client: TestClient) -> None:
    response = client.post("/api/calculate", json={"expression": 42})
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["message"] == "Invalid request"


def test_calculate_empty_string_rejected(client: TestClient) -> None:
    response = client.post("/api/calculate", json={"expression": ""})
    assert response.status_code == 400
    assert response.json()["success"] is False


def test_calculate_expression_too_long(client: TestClient) -> None:
    long_expression = "1+" * 512 + "1"
    assert len(long_expression) > 1024
    response = client.post("/api/calculate", json={"expression": long_expression})
    assert response.status_code == 400
    body = response.json()
    assert body["success"] is False
    assert body["message"] == "Invalid request"


def test_calculate_invalid_does_not_persist_history(
    client: TestClient, db_session: Session
) -> None:
    before = db_session.query(CalculationHistory).count()
    client.post("/api/calculate", json={"expression": "1+"})
    client.post("/api/calculate", json={"expression": "1/0"})
    client.post("/api/calculate", json={"expression": "abc"})
    after = db_session.query(CalculationHistory).count()
    assert after == before


def test_calculate_persistence_failure_returns_server_error(
    sqlite_session_factory,
) -> None:
    """A DB commit failure must not surface as a successful calculation."""

    class _FailingSession:
        def __init__(self) -> None:
            self.rollback_called = False

        def add(self, _record: object) -> None:
            pass

        def commit(self) -> None:
            raise OperationalError(
                "INSERT ...", params=None, orig=Exception("db down")
            )

        def rollback(self) -> None:
            self.rollback_called = True

        def refresh(self, _record: object) -> None:
            pass

        def close(self) -> None:
            pass

    failing = _FailingSession()

    def _override() -> _FailingSession:
        return failing

    app.dependency_overrides[get_db] = _override
    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                "/api/calculate", json={"expression": "1+2"}
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    body = response.json()
    assert body["success"] is False
    assert body["message"] == "Internal server error"
    assert failing.rollback_called is True


def test_calculate_response_does_not_leak_internal_details(client: TestClient) -> None:
    """Error responses must not include stack traces or DB connection info."""
    response = client.post("/api/calculate", json={"expression": "1+"})
    assert response.status_code == 400
    body = response.json()
    serialized = str(body)
    for forbidden in ("Traceback", "SQLAlchemy", "sqlite", "mysql", "pymysql"):
        assert forbidden not in serialized


def test_calculate_with_internal_db_error_does_not_leak_internal_details(
    sqlite_session_factory,
) -> None:
    db = MagicMock(spec=Session)
    db.commit.side_effect = OperationalError(
        "INSERT INTO calculation_history ...",
        params=None,
        orig=Exception("password=hunter2, host=10.0.0.1"),
    )

    def _override() -> MagicMock:
        return db

    app.dependency_overrides[get_db] = _override
    try:
        with TestClient(app) as test_client:
            response = test_client.post(
                "/api/calculate", json={"expression": "1+2"}
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    body = response.json()
    assert body == {"success": False, "message": "Internal server error"}
    assert "password" not in str(body)
    assert "host" not in str(body)


def test_calculate_appears_in_docs(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    assert "/api/calculate" in spec["paths"]
    assert "post" in spec["paths"]["/api/calculate"]
