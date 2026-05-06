"""FastAPI application factory with lifespan management.

Provides the main application entry point with:
- Lifespan context manager for startup/shutdown
- CORS middleware for Streamlit frontend
- Router inclusion with versioning
- Health check endpoint
- Global exception handlers
- Documentation controls per environment
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.common.config import common_settings
from src.common.exceptions import (
    BaseAppException,
    NotFoundError,
    ProcessingError,
    StorageError,
    UnauthorizedError,
    ValidationError,
)

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


# Configure logging
logging.basicConfig(
    level=getattr(logging, common_settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Environments where docs should be shown
SHOW_DOCS_IN = {"development", "staging", "local"}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context manager.

    Handles startup and shutdown events.

    Args:
        app: FastAPI application instance.

    Yields:
        None during application lifetime.
    """
    # Startup
    logger.info(
        "Starting up application - environment: %s",
        common_settings.ENVIRONMENT,
    )

    # Import and initialize agents registry if needed
    try:
        from src.agents.registry import init_default_llm

        init_default_llm()
        logger.info("Agents LLM initialized")
    except Exception as e:
        logger.warning("Could not initialize agents LLM: %s", e)

    yield

    # Shutdown
    logger.info("Shutting down application")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    # Determine if docs should be shown
    show_docs = common_settings.ENVIRONMENT in SHOW_DOCS_IN

    app_kwargs = {
        "title": "Agentic RAG API",
        "description": "API for document management and RAG-based querying",
        "version": "1.0.0",
        "lifespan": lifespan,
    }

    if not show_docs:
        app_kwargs["openapi_url"] = None  # Disables /docs and /redoc
        app_kwargs["docs_url"] = None
        app_kwargs["redoc_url"] = None

    app = FastAPI(**app_kwargs)

    # Configure CORS for Streamlit frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:8501",  # Streamlit default
            "http://127.0.0.1:8501",
            "http://localhost:3000",  # Common dev port
            "http://127.0.0.1:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers with API versioning
    from src.agents.router import router as agents_router
    from src.documents.router import router as documents_router

    app.include_router(
        documents_router,
        prefix="/api/v1",
    )
    app.include_router(
        agents_router,
        prefix="/api/v1",
    )

    # Health check endpoint
    @app.get(
        "/health",
        status_code=status.HTTP_200_OK,
        tags=["health"],
        summary="Health check",
        description="Check if the API is running and healthy.",
    )
    async def health_check() -> dict[str, str]:
        """Return health status."""
        return {
            "status": "healthy",
            "environment": common_settings.ENVIRONMENT,
            "version": "1.0.0",
        }

    # Global exception handlers
    @app.exception_handler(BaseAppException)
    async def base_app_exception_handler(
        request,  # noqa: ARG001
        exc: BaseAppException,
    ) -> JSONResponse:
        """Handle all application-specific exceptions."""
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

        if isinstance(exc, NotFoundError):
            status_code = status.HTTP_404_NOT_FOUND
        elif isinstance(exc, ValidationError):
            status_code = status.HTTP_400_BAD_REQUEST
        elif isinstance(exc, UnauthorizedError):
            status_code = status.HTTP_401_UNAUTHORIZED
        elif isinstance(exc, StorageError):
            status_code = status.HTTP_502_BAD_GATEWAY
        elif isinstance(exc, ProcessingError):
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

        return JSONResponse(
            status_code=status_code,
            content={
                "error": exc.message,
                "code": exc.code,
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request,  # noqa: ARG001
        exc: Exception,
    ) -> JSONResponse:
        """Handle unhandled exceptions."""
        logger.exception("Unhandled exception")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "Internal server error",
                "code": "INTERNAL_ERROR",
            },
        )

    return app


# Create default app instance for uvicorn
app = create_app()
