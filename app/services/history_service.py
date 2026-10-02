"""Service layer for reading and deleting calculation history."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import (
    HistoryDeleteError,
    HistoryNotFoundError,
    HistoryReadError,
)
from app.models.calculation_history import CalculationHistory


@dataclass(frozen=True)
class HistoryEntry:
    """A single history row in a storage-agnostic shape."""

    id: int
    expression: str
    result: str
    created_at: datetime


class HistoryService:
    """Read and delete service for persisted calculation history."""

    def list_history(self, db: Session) -> list[HistoryEntry]:
        """Return all persisted history rows newest-first by primary key.

        The query reads from the database directly via the provided
        session. No in-memory caching or write operations are performed.

        Raises:
            HistoryReadError: Raised when the underlying database query
                fails. The original SQLAlchemy exception is attached via
                ``__cause__``; the HTTP layer translates this into a
                sanitized 500 response.
        """
        try:
            rows = (
                db.query(CalculationHistory)
                .order_by(CalculationHistory.id.desc())
                .all()
            )
        except SQLAlchemyError as exc:
            raise HistoryReadError("failed to read calculation history") from exc

        return [
            HistoryEntry(
                id=row.id,
                expression=row.expression,
                result=row.result,
                created_at=row.created_at,
            )
            for row in rows
        ]

    def delete_history(self, db: Session, history_id: int) -> None:
        """Delete the history row with the given primary key.

        The lookup runs before any delete. If the row is missing,
        :class:`HistoryNotFoundError` is raised without touching the
        session. If a database error occurs during lookup or delete,
        the session is rolled back and :class:`HistoryDeleteError` is
        raised.

        Raises:
            HistoryNotFoundError: When no row with ``history_id`` exists.
                The session is not modified in this case.
            HistoryDeleteError: When the database lookup or delete fails.
                The session is rolled back before this exception
                propagates.
        """
        try:
            record = db.get(CalculationHistory, history_id)
        except SQLAlchemyError as exc:
            db.rollback()
            raise HistoryDeleteError(
                "failed to locate history record"
            ) from exc

        if record is None:
            raise HistoryNotFoundError(
                f"history record {history_id} not found"
            )

        try:
            db.delete(record)
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            raise HistoryDeleteError(
                "failed to delete history record"
            ) from exc
