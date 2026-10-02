import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes.calculator import router as calculator_router
from app.api.routes.history import router as history_router
from app.core.config import get_settings
from app.core.exceptions import (
    DivisionByZeroError,
    HistoryDeleteError,
    HistoryNotFoundError,
    HistoryReadError,
    InvalidExpressionError,
    PersistenceError,
)
from app.database.database import Base, SessionLocal, engine
from app import models  # noqa: F401  ensure models are registered with Base.metadata

logger = logging.getLogger("calculator_backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ensured.")
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.4.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["health"])
    def health() -> dict:
        try:
            with SessionLocal() as session:
                session.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            logger.error("Database health check failed: %s", exc.__class__.__name__)
            return {
                "status": "unhealthy",
                "app": {"name": settings.app_name, "env": settings.app_env},
                "database": {"connected": False},
            }

        return {
            "status": "healthy",
            "app": {"name": settings.app_name, "env": settings.app_env},
            "database": {"connected": True},
        }

    @app.exception_handler(InvalidExpressionError)
    async def _invalid_expression_handler(
        request: Request, exc: InvalidExpressionError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": str(exc)},
        )

    @app.exception_handler(DivisionByZeroError)
    async def _division_by_zero_handler(
        request: Request, exc: DivisionByZeroError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": str(exc)},
        )

    @app.exception_handler(PersistenceError)
    async def _persistence_error_handler(
        request: Request, exc: PersistenceError
    ) -> JSONResponse:
        logger.error(
            "Persistence failure on %s %s: %s",
            request.method,
            request.url.path,
            exc.__class__.__name__,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "message": "Internal server error"},
        )

    @app.exception_handler(HistoryReadError)
    async def _history_read_error_handler(
        request: Request, exc: HistoryReadError
    ) -> JSONResponse:
        logger.error(
            "History read failure on %s %s: %s",
            request.method,
            request.url.path,
            exc.__class__.__name__,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "message": "Internal server error"},
        )

    @app.exception_handler(HistoryDeleteError)
    async def _history_delete_error_handler(
        request: Request, exc: HistoryDeleteError
    ) -> JSONResponse:
        logger.error(
            "History delete failure on %s %s: %s",
            request.method,
            request.url.path,
            exc.__class__.__name__,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"success": False, "message": "Internal server error"},
        )

    @app.exception_handler(HistoryNotFoundError)
    async def _history_not_found_handler(
        request: Request, exc: HistoryNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"success": False, "message": "History record not found"},
        )

    @app.exception_handler(RequestValidationError)
    async def _request_validation_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"success": False, "message": "Invalid request"},
        )

    app.include_router(calculator_router, prefix="/api")
    app.include_router(history_router, prefix="/api")

    return app


app = create_app()
