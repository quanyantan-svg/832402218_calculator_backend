"""Pydantic request and response schemas for the calculator API."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.services.expression_parser import MAX_EXPRESSION_LENGTH


class CalculationRequest(BaseModel):
    """Request body for ``POST /api/calculate``."""

    expression: str = Field(
        min_length=1,
        max_length=MAX_EXPRESSION_LENGTH,
        description="Mathematical expression to evaluate.",
    )


class CalculationResponse(BaseModel):
    """Successful response from ``POST /api/calculate``."""

    success: bool = True
    expression: str
    result: str


class ErrorResponse(BaseModel):
    """Generic error response shape used by all calculator endpoints."""

    success: bool = False
    message: str
