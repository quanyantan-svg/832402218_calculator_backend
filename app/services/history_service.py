"""Service layer for reading calculation history from storage."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import HistoryReadError
from app.models.calculation_history import CalculationHistory


@dataclass(frozen=True)
class HistoryEntry:
    """A single history row in a storage-agnostic shape."""

    id: int
    expression: str
    result: str
    created_at: datetime


class HistoryService:
    """Read-only query service for persisted calculation history."""

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
