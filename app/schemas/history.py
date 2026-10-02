"""Pydantic schemas for the history endpoint."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class HistoryItem(BaseModel):
    """A single persisted calculation."""

    id: int
    expression: str
    result: str
    created_at: datetime


class HistoryResponse(BaseModel):
    """Response body for ``GET /api/history``."""

    success: bool = True
    history: list[HistoryItem]


class HistoryDeleteResponse(BaseModel):
    """Response body for ``DELETE /api/history/{history_id}``."""

    success: bool = True
    message: str
