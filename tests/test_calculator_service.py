"""Tests for the calculator service layer."""

from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    DivisionByZeroError,
    InvalidExpressionError,
    PersistenceError,
)
from app.models.calculation_history import CalculationHistory
from app.services.calculator_service import (
    CalculatorService,
    CalculationResult,
    normalize_decimal,
)


class _FailingSession:
    """A session stub whose commit raises a SQLAlchemy error."""

    def __init__(self, exc: Exception) -> None:
        self._exc = exc
        self.rollback_called = False

    def add(self, _record: CalculationHistory) -> None:
        pass

    def commit(self) -> None:
        raise self._exc

    def rollback(self) -> None:
        self.rollback_called = True

    def refresh(self, _record: CalculationHistory) -> None:
        pass


def test_successful_calculation_persists_a_history_row(db_session: Session) -> None:
    service = CalculatorService()
    before = db_session.query(CalculationHistory).count()

    result = service.calculate_and_persist(db_session, "1+2")

    assert isinstance(result, CalculationResult)
    assert result.expression == "1+2"
    assert result.result == "3"
    assert result.history_id > 0

    after = db_session.query(CalculationHistory).count()
    assert after == before + 1

    row = db_session.get(CalculationHistory, result.history_id)
    assert row is not None
    assert row.expression == "1+2"
    assert row.result == "3"


def test_decimal_arithmetic_is_persisted_exactly(db_session: Session) -> None:
    """0.1 + 0.2 must be stored as the canonical "0.3", not "0.3000000000"."""
    service = CalculatorService()
    result = service.calculate_and_persist(db_session, "0.1+0.2")
    assert result.result == "0.3"
    row = db_session.get(CalculationHistory, result.history_id)
    assert row is not None
    assert row.result == "0.3"


def test_invalid_expression_does_not_persist(db_session: Session) -> None:
    service = CalculatorService()
    before = db_session.query(CalculationHistory).count()

    with pytest.raises(InvalidExpressionError):
        service.calculate_and_persist(db_session, "1+abc")

    after = db_session.query(CalculationHistory).count()
    assert after == before


def test_invalid_expression_does_not_persist_trailing_garbage(db_session: Session) -> None:
    service = CalculatorService()
    before = db_session.query(CalculationHistory).count()

    with pytest.raises(InvalidExpressionError):
        service.calculate_and_persist(db_session, "1+2 3")

    after = db_session.query(CalculationHistory).count()
    assert after == before


def test_division_by_zero_does_not_persist(db_session: Session) -> None:
    service = CalculatorService()
    before = db_session.query(CalculationHistory).count()

    with pytest.raises(DivisionByZeroError):
        service.calculate_and_persist(db_session, "1/0")

    after = db_session.query(CalculationHistory).count()
    assert after == before


def test_division_by_zero_nested_does_not_persist(db_session: Session) -> None:
    service = CalculatorService()
    before = db_session.query(CalculationHistory).count()

    with pytest.raises(DivisionByZeroError):
        service.calculate_and_persist(db_session, "1/(2-2)")

    after = db_session.query(CalculationHistory).count()
    assert after == before


def test_commit_failure_triggers_rollback_and_raises_persistence_error() -> None:
    failing = _FailingSession(
        OperationalError("INSERT INTO ...", params=None, orig=Exception("db down"))
    )
    service = CalculatorService()

    with pytest.raises(PersistenceError):
        service.calculate_and_persist(failing, "1+2")  # type: ignore[arg-type]

    assert failing.rollback_called is True


def test_normalize_decimal_helper_is_exposed() -> None:
    """The normalization helper must be independently importable and testable."""
    assert normalize_decimal(Decimal("3.00")) == "3"
    assert normalize_decimal(Decimal("-0")) == "0"


def test_service_uses_parser_for_arithmetic(db_session: Session, monkeypatch) -> None:
    """If the parser raises, the service must propagate without persisting."""
    before = db_session.query(CalculationHistory).count()

    def _explode(_expression: str) -> Decimal:
        raise InvalidExpressionError("forced")

    monkeypatch.setattr(
        "app.services.calculator_service.parse_and_calculate", _explode
    )

    service = CalculatorService()
    with pytest.raises(InvalidExpressionError):
        service.calculate_and_persist(db_session, "1+2")

    after = db_session.query(CalculationHistory).count()
    assert after == before


def test_unexpected_db_session_error_is_not_swallowed() -> None:
    """A SQLAlchemy exception during commit must surface as PersistenceError."""
    db = MagicMock(spec=Session)
    db.commit.side_effect = OperationalError(
        "INSERT ...", params=None, orig=Exception("connection lost")
    )
    db.rollback.return_value = None

    service = CalculatorService()
    with pytest.raises(PersistenceError):
        service.calculate_and_persist(db, "1+2")  # type: ignore[arg-type]

    db.rollback.assert_called_once()


def test_successful_commit_does_not_call_refresh(db_session: Session) -> None:
    """After a successful commit the service must not perform an extra refresh."""
    refresh_calls: list[object] = []

    real_refresh = db_session.refresh

    def _tracking_refresh(instance: object, *args: object, **kwargs: object) -> None:
        refresh_calls.append(instance)
        real_refresh(instance, *args, **kwargs)  # type: ignore[arg-type]

    db_session.refresh = _tracking_refresh  # type: ignore[assignment]

    service = CalculatorService()
    result = service.calculate_and_persist(db_session, "1+2")

    assert result.history_id > 0
    assert refresh_calls == []


def test_history_id_is_available_without_refresh(db_session: Session) -> None:
    """The auto-increment id must be populated by commit alone."""
    service = CalculatorService()
    result = service.calculate_and_persist(db_session, "1+2")
    assert isinstance(result.history_id, int)
    assert result.history_id > 0
    fetched = db_session.get(CalculationHistory, result.history_id)
    assert fetched is not None


def test_commit_failure_does_not_call_refresh() -> None:
    """When commit raises, no extra refresh should be performed before raising."""

    class _TrackingSession:
        def __init__(self) -> None:
            self.refresh_calls = 0

        def add(self, _record: CalculationHistory) -> None:
            pass

        def commit(self) -> None:
            raise OperationalError(
                "INSERT ...", params=None, orig=Exception("db down")
            )

        def rollback(self) -> None:
            pass

    session = _TrackingSession()

    service = CalculatorService()
    with pytest.raises(PersistenceError):
        service.calculate_and_persist(session, "1+2")  # type: ignore[arg-type]

    assert session.refresh_calls == 0
