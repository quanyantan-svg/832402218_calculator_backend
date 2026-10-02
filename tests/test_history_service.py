"""Tests for the history query and deletion service layer."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    HistoryDeleteError,
    HistoryNotFoundError,
    HistoryReadError,
)
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


# ---------------------------------------------------------------------------
# delete_history tests
# ---------------------------------------------------------------------------


def test_existing_record_can_be_deleted(db_session: Session) -> None:
    result = CalculatorService().calculate_and_persist(db_session, "1+2")
    target_id = result.history_id

    service = HistoryService()
    service.delete_history(db_session, target_id)

    assert db_session.get(CalculationHistory, target_id) is None


def test_row_count_decreases_by_exactly_one(db_session: Session) -> None:
    CalculatorService().calculate_and_persist(db_session, "1+1")
    result = CalculatorService().calculate_and_persist(db_session, "2+2")

    before = db_session.query(CalculationHistory).count()
    assert before == 2

    HistoryService().delete_history(db_session, result.history_id)

    after = db_session.query(CalculationHistory).count()
    assert after == 1


def test_correct_id_deleted_other_rows_remain(db_session: Session) -> None:
    keep1 = CalculatorService().calculate_and_persist(db_session, "1+1")
    target = CalculatorService().calculate_and_persist(db_session, "2+2")
    keep2 = CalculatorService().calculate_and_persist(db_session, "3+3")

    HistoryService().delete_history(db_session, target.history_id)

    remaining_ids = {row.id for row in db_session.query(CalculationHistory).all()}
    assert remaining_ids == {keep1.history_id, keep2.history_id}
    assert target.history_id not in remaining_ids


def test_missing_id_raises_history_not_found(db_session: Session) -> None:
    with pytest.raises(HistoryNotFoundError):
        HistoryService().delete_history(db_session, 999999)


def test_missing_id_does_not_commit(db_session: Session) -> None:
    CalculatorService().calculate_and_persist(db_session, "1+2")

    class _CountingCommitSession(Session):
        commit_calls = 0

        def commit(self) -> None:  # type: ignore[override]
            type(self).commit_calls += 1
            super().commit()

    # Use the existing session to test that an absent id does not trigger
    # any commit side-effects (commit count stays zero on this session).
    session = db_session
    type(session).commit_calls = 0  # type: ignore[attr-defined]

    def _tracking_commit() -> None:
        type(session).commit_calls += 1  # type: ignore[attr-defined]

    real_commit = session.commit
    session.commit = _tracking_commit  # type: ignore[assignment]

    try:
        with pytest.raises(HistoryNotFoundError):
            HistoryService().delete_history(session, 999999)
        assert type(session).commit_calls == 0  # type: ignore[attr-defined]
    finally:
        session.commit = real_commit  # type: ignore[assignment]

    # existing row still present
    assert db_session.query(CalculationHistory).count() == 1


def test_successful_delete_commits_exactly_once(db_session: Session) -> None:
    result = CalculatorService().calculate_and_persist(db_session, "1+2")

    session = db_session
    type(session).commit_calls = 0  # type: ignore[attr-defined]

    def _tracking_commit() -> None:
        type(session).commit_calls += 1  # type: ignore[attr-defined]

    real_commit = session.commit
    session.commit = _tracking_commit  # type: ignore[assignment]

    try:
        HistoryService().delete_history(session, result.history_id)
        assert type(session).commit_calls == 1  # type: ignore[attr-defined]
    finally:
        session.commit = real_commit  # type: ignore[assignment]


def test_commit_failure_triggers_rollback() -> None:
    """A SQLAlchemy exception during delete() or commit() rolls back."""

    class _FailingDeleteSession:
        def __init__(self) -> None:
            self.rollback_called = False
            self.record = CalculationHistory(id=1, expression="1+1", result="2")

        def get(self, _model: type, _pk: int) -> CalculationHistory:
            return self.record

        def delete(self, _record: CalculationHistory) -> None:
            raise OperationalError(
                "DELETE ...", params=None, orig=Exception("db down")
            )

        def commit(self) -> None:
            pass

        def rollback(self) -> None:
            self.rollback_called = True

    session = _FailingDeleteSession()
    service = HistoryService()

    with pytest.raises(HistoryDeleteError):
        service.delete_history(session, 1)  # type: ignore[arg-type]

    assert session.rollback_called is True


def test_commit_failure_after_delete_triggers_rollback() -> None:
    """If delete() succeeds but commit() fails, the session is rolled back."""

    class _FailingCommitSession:
        def __init__(self) -> None:
            self.rollback_called = False
            self.deleted: list[CalculationHistory] = []
            self.record = CalculationHistory(id=1, expression="1+1", result="2")

        def get(self, _model: type, _pk: int) -> CalculationHistory:
            return self.record

        def delete(self, record: CalculationHistory) -> None:
            self.deleted.append(record)

        def commit(self) -> None:
            raise OperationalError(
                "COMMIT ...", params=None, orig=Exception("db down")
            )

        def rollback(self) -> None:
            self.rollback_called = True

    session = _FailingCommitSession()
    service = HistoryService()

    with pytest.raises(HistoryDeleteError):
        service.delete_history(session, 1)  # type: ignore[arg-type]

    assert session.rollback_called is True
    assert session.deleted == [session.record]


def test_lookup_failure_becomes_history_delete_error() -> None:
    """A SQLAlchemy exception during the initial lookup raises HistoryDeleteError."""

    class _FailingLookupSession:
        def get(self, _model: type, _pk: int) -> None:
            raise OperationalError(
                "SELECT ...", params=None, orig=Exception("db down")
            )

        def rollback(self) -> None:
            pass

    session = _FailingLookupSession()
    service = HistoryService()

    with pytest.raises(HistoryDeleteError):
        service.delete_history(session, 1)  # type: ignore[arg-type]


def test_failed_delete_does_not_falsely_report_success(db_session: Session) -> None:
    """After a failed delete, the row must still exist."""
    result = CalculatorService().calculate_and_persist(db_session, "1+2")
    target_id = result.history_id

    session = db_session
    real_delete = session.delete

    def _failing_delete(_record: CalculationHistory) -> None:
        raise OperationalError(
            "DELETE ...", params=None, orig=Exception("db down")
        )

    session.delete = _failing_delete  # type: ignore[assignment]

    try:
        with pytest.raises(HistoryDeleteError):
            HistoryService().delete_history(session, target_id)
    finally:
        session.delete = real_delete  # type: ignore[assignment]

    # row must still exist because the transaction rolled back
    row = db_session.get(CalculationHistory, target_id)
    assert row is not None
    assert row.expression == "1+2"
    assert row.result == "3"
