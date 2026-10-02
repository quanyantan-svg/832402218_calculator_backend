"""Service layer that coordinates parsing, normalization, and persistence."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import PersistenceError
from app.models.calculation_history import CalculationHistory
from app.services.expression_parser import parse_and_calculate


@dataclass(frozen=True)
class CalculationResult:
    """Outcome of a single successful calculation."""

    expression: str
    result: str
    history_id: int


def normalize_decimal(value: Decimal) -> str:
    """Convert a :class:`Decimal` to a clean plain decimal string.

    Trailing zeros are stripped and scientific notation is avoided for
    normal calculator magnitudes. A value of zero is always rendered as
    ``"0"`` regardless of its original sign.
    """
    if value == 0:
        return "0"
    return format(value.normalize(), "f")


class CalculatorService:
    """Coordinates parse, normalize, persist for a single calculation."""

    def calculate_and_persist(
        self, db: Session, expression: str
    ) -> CalculationResult:
        """Parse, evaluate, and persist ``expression``.

        The auto-increment primary key of the inserted row is populated by
        ``commit()`` and remains accessible without an extra refresh
        because the configured session uses ``expire_on_commit=False``.

        Raises:
            InvalidExpressionError: Propagated from the parser when the
                input is not a valid expression. Nothing is persisted in
                this case.
            DivisionByZeroError: Propagated from the parser when the
                evaluation requires division by zero. Nothing is
                persisted in this case.
            PersistenceError: Raised when the database commit fails.
                The session is rolled back before the exception propagates.
        """
        result = parse_and_calculate(expression)
        normalized = normalize_decimal(result)

        record = CalculationHistory(expression=expression, result=normalized)
        db.add(record)
        try:
            db.commit()
        except SQLAlchemyError as exc:
            db.rollback()
            raise PersistenceError("failed to persist calculation") from exc

        return CalculationResult(
            expression=expression,
            result=normalized,
            history_id=record.id,
        )
