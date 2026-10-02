"""API routes for the calculation history endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Path, status
from sqlalchemy.orm import Session

from app.database.database import get_db
from app.schemas.history import (
    HistoryDeleteResponse,
    HistoryItem,
    HistoryResponse,
)
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


@router.delete(
    "/history/{history_id}",
    response_model=HistoryDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete a single history record by id.",
    responses={status.HTTP_404_NOT_FOUND: {"description": "History record not found."}},
)
def delete_history(
    history_id: int = Path(..., ge=1, description="Primary key of the history row."),
    db: Session = Depends(get_db),
) -> HistoryDeleteResponse:
    """Delete the persisted history row identified by ``history_id``."""
    service = HistoryService()
    service.delete_history(db, history_id)
    return HistoryDeleteResponse(message="History record deleted")
