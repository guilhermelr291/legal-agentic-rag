"""Pydantic schemas for documents domain request/response models.

Defines structured data models for document upload, status tracking,
and error responses using CustomModel base with modern serialization.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from src.common.models import CustomModel

# =============================================================================
# Upload Models
# =============================================================================


class UploadResponse(CustomModel):
    """Response model for document upload endpoint.

    Returned after successful upload initiation. Document will be
    in 'processing' status until background processing completes.
    """

    document_id: str = Field(
        ...,
        description="Unique identifier for the uploaded document (UUID)",
    )
    filename: str = Field(
        ...,
        description="Original filename as provided by the user",
    )
    file_type: Literal["pdf", "docx", "xlsx"] = Field(
        ...,
        description="Detected file type from extension",
    )
    file_size: int = Field(
        ...,
        ge=0,
        description="File size in bytes",
    )
    status: Literal["processing", "ready", "failed"] = Field(
        ...,
        description="Current processing status (always 'processing' on initial upload)",
    )
    storage_path: str = Field(
        ...,
        description="Path in Supabase Storage: {user_id}/{document_id}/{filename}",
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when the document record was created",
    )


# =============================================================================
# Status Models
# =============================================================================


class DocumentStatusResponse(CustomModel):
    """Response model for document status endpoint.

    Provides current processing status with timing information
    and optional graph indexing status.
    """

    document_id: str = Field(
        ...,
        description="Unique identifier for the document",
    )
    filename: str = Field(
        ...,
        description="Original filename",
    )
    file_type: Literal["pdf", "docx", "xlsx"] = Field(
        ...,
        description="Document type",
    )
    status: Literal["processing", "ready", "failed"] = Field(
        ...,
        description="Current processing status",
    )
    error_msg: str | None = Field(
        default=None,
        description="Error message if status is 'failed'",
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when the document was uploaded",
    )
    updated_at: datetime = Field(
        ...,
        description="Timestamp of last status update",
    )
    processing_duration_seconds: float | None = Field(
        default=None,
        description="Total processing time in seconds (null if still processing)",
    )
    graph_status: Literal["processing", "ready", "failed", "timeout", "ready_empty"] | None = Field(
        default=None,
        description="Graph indexing status from documents.meta (null if not enabled)",
    )


# =============================================================================
# List Documents Models
# =============================================================================


class DocumentSummary(CustomModel):
    """Summary of a document for list views."""

    document_id: str = Field(
        ...,
        description="Unique identifier for the document",
    )
    filename: str = Field(
        ...,
        description="Original filename",
    )
    file_type: Literal["pdf", "docx", "xlsx"] = Field(
        ...,
        description="Document type",
    )
    file_size: int = Field(
        ...,
        ge=0,
        description="File size in bytes",
    )
    status: Literal["processing", "ready", "failed"] = Field(
        ...,
        description="Current processing status",
    )
    created_at: datetime = Field(
        ...,
        description="Timestamp when the document was uploaded",
    )
    updated_at: datetime = Field(
        ...,
        description="Timestamp of last status update",
    )


class DocumentListResponse(CustomModel):
    """Response model for listing user's documents."""

    documents: list[DocumentSummary] = Field(
        default_factory=list,
        description="List of document summaries",
    )
    total: int = Field(
        ...,
        ge=0,
        description="Total number of documents",
    )
    status_filter: Literal["processing", "ready", "failed"] | None = Field(
        default=None,
        description="Applied status filter (null if none)",
    )


# =============================================================================
# Error Response Models
# =============================================================================


class ErrorResponse(CustomModel):
    """Standard error response model.

    Used for all 4xx and 5xx responses to provide consistent
    error formatting across the API.
    """

    detail: str = Field(
        ...,
        description="Human-readable error description",
    )
    error_code: str | None = Field(
        default=None,
        description="Machine-readable error code for programmatic handling",
    )
    context: dict[str, Any] | None = Field(
        default=None,
        description="Additional context for debugging (only in development)",
    )


# =============================================================================
# Health Response Model
# =============================================================================


class HealthResponse(CustomModel):
    """Health check response model.

    Provides service health status and version information.
    """

    status: str = Field(
        ...,
        description="Health status: 'healthy' or 'unhealthy'",
    )
    version: str = Field(
        ...,
        description="API version string",
    )
    timestamp: datetime = Field(
        ...,
        description="Current server timestamp in UTC",
    )


__all__ = [
    "UploadResponse",
    "DocumentStatusResponse",
    "DocumentSummary",
    "DocumentListResponse",
    "ErrorResponse",
    "HealthResponse",
]
