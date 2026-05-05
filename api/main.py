"""FastAPI application main entry point.

Provides the core FastAPI application with:
- CORS middleware for Streamlit frontend
- Document routes at /api/v1 prefix
- Health check endpoint
- Startup/shutdown lifecycle management
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.models import ErrorResponse, HealthResponse
from api.routes.documents import router as documents_router
from my_agent.config.settings import get_settings

logger = logging.getLogger(__name__)

# =============================================================================
# Application Configuration
# =============================================================================

API_VERSION = "0.1.0"
API_PREFIX = "/api/"

# CORS origins - configured for Streamlit default port
DEFAULT_CORS_ORIGINS = [
    "http://localhost:8501",  # Streamlit default
    "http://127.0.0.1:8501",
    "http://localhost:3000",  # Common dev port
    "http://127.0.0.1:3000",
]

# =============================================================================
# Lifespan Management
# =============================================================================


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan manager for startup and shutdown events.

    Handles:
    - Startup: Initialize connections, validate configuration
    - Shutdown: Cleanup resources

    Args:
        app: The FastAPI application instance.

    Yields:
        None during application runtime.
    """
    # Startup
    logger.info("Starting up FastAPI application...")

    try:
        # Validate settings are loadable
        settings = get_settings()
        logger.info(
            "Configuration loaded: embedding_model=%s, graph_rag=%s",
            settings.openai_embedding_model,
            settings.graph_rag_enabled,
        )
    except Exception as e:
        logger.error("Failed to load configuration: %s", e)
        raise

    logger.info(
        "FastAPI application ready: version=%s, prefix=%s",
        API_VERSION,
        API_PREFIX,
    )

    yield

    # Shutdown
    logger.info("Shutting down FastAPI application...")
    # Cleanup resources if needed
    logger.info("Shutdown complete")


# =============================================================================
# Application Factory
# =============================================================================


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance.
    """
    app = FastAPI(
        title="Agentic RAG Document Ingestion API",
        description="""
        API for document upload, processing, and status tracking.

        ## Features

        - **Document Upload**: Upload PDF, DOCX, and XLSX files (max 50MB)
        - **Background Processing**: Async extraction, chunking, and embedding
        - **Status Tracking**: Real-time status polling for processing state
        - **Graph RAG Ready**: Optional entity/relation extraction (feature-flagged)

        ## File Types

        - **PDF**: Text extraction, legal-aware chunking, embeddings
        - **DOCX**: Text extraction, legal-aware chunking, embeddings
        - **XLSX**: Metadata extraction only (for XLSX tool routing)

        ## Authentication

        Currently uses placeholder auth. Production should implement JWT validation.
        """,
        version=API_VERSION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=DEFAULT_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(
        documents_router,
        prefix=API_PREFIX,
    )

    return app


# =============================================================================
# Global App Instance
# =============================================================================

app = create_app()


# =============================================================================
# Health Check Endpoint
# =============================================================================


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["health"],
    summary="Health check endpoint",
    description="Returns service health status and version information.",
)
async def health_check() -> HealthResponse:
    """Check API health status.

    Returns:
        HealthResponse with status, version, and current timestamp.
    """
    return HealthResponse(
        status="healthy",
        version=API_VERSION,
        timestamp=datetime.now(timezone.utc),
    )


# =============================================================================
# Global Exception Handlers
# =============================================================================


@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception) -> JSONResponse:
    """Handle unhandled exceptions globally.

    Args:
        request: The incoming request.
        exc: The unhandled exception.

    Returns:
        JSONResponse with error details.
    """
    logger.exception("Unhandled exception: %s", exc)

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            detail="An unexpected error occurred",
            error_code="INTERNAL_ERROR",
        ).model_dump(),
    )


# =============================================================================
# Root Endpoint (Redirect to docs)
# =============================================================================


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    """Root endpoint - redirects to documentation.

    Returns:
        Simple message with documentation link.
    """
    return {
        "message": "Agentic RAG Document Ingestion API",
        "docs": "/docs",
        "health": "/health",
    }


# =============================================================================
# Module Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    # Run with: python -m api.main or uvicorn api.main:app --reload
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
