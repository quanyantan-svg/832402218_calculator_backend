import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
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
        version="0.1.0",
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

    return app


app = create_app()
