"""API routes for the calculator."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.schemas.calculator import (
    CalculationRequest,
    CalculationResponse,
)
from app.services.calculator_service import CalculatorService

router = APIRouter(tags=["calculator"])


@router.post(
    "/calculate",
    response_model=CalculationResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate a mathematical expression and persist the result.",
)
def calculate(
    payload: CalculationRequest,
    db: Session = Depends(get_db),
) -> CalculationResponse:
    """Parse ``payload.expression``, compute the result, and persist it."""
    service = CalculatorService()
    result = service.calculate_and_persist(db, payload.expression)
    return CalculationResponse(expression=result.expression, result=result.result)
