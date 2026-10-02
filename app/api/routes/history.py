"""API routes for the calculation history endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.schemas.history import HistoryItem, HistoryResponse
from app.services.history_service import HistoryService

router = APIRouter(tags=["history"])


@router.get(
    "/history",
    response_model=HistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="List persisted calculation history, newest first.",
)
def list_history(db: Session = Depends(get_db)) -> HistoryResponse:
    """Return all persisted calculations ordered by descending id."""
    service = HistoryService()
    entries = service.list_history(db)
    items = [
        HistoryItem(
            id=entry.id,
            expression=entry.expression,
            result=entry.result,
            created_at=entry.created_at,
        )
        for entry in entries
    ]
    return HistoryResponse(history=items)
