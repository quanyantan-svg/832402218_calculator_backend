"""Tests for the history query service layer."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.exceptions import HistoryReadError
from app.models.calculation_history import CalculationHistory
from app.services.calculator_service import CalculatorService
from app.services.history_service import HistoryEntry, HistoryService


def test_empty_database_returns_empty_list(db_session: Session) -> None:
    service = HistoryService()
    assert service.list_history(db_session) == []


def test_one_row_is_returned_with_all_fields(db_session: Session) -> None:
    CalculatorService().calculate_and_persist(db_session, "1+2")

    service = HistoryService()
    entries = service.list_history(db_session)

    assert len(entries) == 1
    entry = entries[0]
    assert isinstance(entry, HistoryEntry)
    assert isinstance(entry.id, int) and entry.id > 0
    assert entry.expression == "1+2"
    assert entry.result == "3"
    assert isinstance(entry.created_at, datetime)


def test_multiple_rows_returned_newest_first_by_id(db_session: Session) -> None:
    CalculatorService().calculate_and_persist(db_session, "1+1")
    CalculatorService().calculate_and_persist(db_session, "2+2")
    CalculatorService().calculate_and_persist(db_session, "3+3")

    service = HistoryService()
    entries = service.list_history(db_session)

    assert [e.expression for e in entries] == ["3+3", "2+2", "1+1"]
    assert entries[0].id > entries[1].id > entries[2].id


def test_history_query_does_not_create_update_or_delete_rows(db_session: Session) -> None:
    CalculatorService().calculate_and_persist(db_session, "1+1")
    CalculatorService().calculate_and_persist(db_session, "2+2")

    before = db_session.query(CalculationHistory).count()
    service = HistoryService()

    service.list_history(db_session)
    service.list_history(db_session)

    after = db_session.query(CalculationHistory).count()
    assert after == before


def test_history_query_does_not_commit_a_transaction(db_session: Session) -> None:
    """``GET /api/history`` is a read; it must not flush or commit."""
    CalculatorService().calculate_and_persist(db_session, "1+1")

    service = HistoryService()

    before_id = db_session.query(CalculationHistory).order_by(
        CalculationHistory.id.desc()
    ).first().id

    service.list_history(db_session)

    assert db_session.query(CalculationHistory).count() == 1
    assert (
        db_session.query(CalculationHistory).order_by(
            CalculationHistory.id.desc()
        ).first().id
        == before_id
    )


def test_database_failure_becomes_history_read_error() -> None:
    db = MagicMock(spec=Session)
    db.query.side_effect = OperationalError(
        "SELECT ...", params=None, orig=Exception("db down")
    )

    service = HistoryService()
    with pytest.raises(HistoryReadError):
        service.list_history(db)
