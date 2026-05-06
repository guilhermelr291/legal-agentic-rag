"""FastAPI router for document upload and status management.

Provides endpoints for:
- POST /upload - Upload and initiate document processing
- GET /{document_id}/status - Check processing status
- GET / - List user's documents with optional filtering
- DELETE /{document_id} - Delete a document and its associated data

Uses modern Annotated[..., Depends(...)] pattern throughout.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, status

from src.common.database import DbDep
from src.common.exceptions import StorageError
from src.documents.config import documents_settings
from src.documents.dependencies import DocumentDep, UserIdDep
from src.documents.models import Document
from src.documents.schemas import (
    DocumentListResponse,
    DocumentStatusResponse,
    DocumentSummary,
    ErrorResponse,
    UploadResponse,
)
from src.documents.service import DocumentService
from src.storage.dependencies import StorageDep

logger = logging.getLogger(__name__)

# =============================================================================
# Router
# =============================================================================

router = APIRouter(prefix="/documents", tags=["documents"])

# =============================================================================
# Constants
# =============================================================================

ALLOWED_EXTENSIONS = documents_settings.ALLOWED_EXTENSIONS
MAX_FILE_SIZE_BYTES = documents_settings.MAX_FILE_SIZE
STORAGE_BUCKET = "documents"

# Map extensions to file types
FILE_TYPE_MAP: dict[str, Literal["pdf", "docx", "xlsx"]] = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".xlsx": "xlsx",
}


# =============================================================================
# Helper Functions
# =============================================================================


def validate_file_extension(filename: str) -> Literal["pdf", "docx", "xlsx"]:
    """Validate file extension and return file type.

    Args:
        filename: Original filename from upload.

    Returns:
        File type string.

    Raises:
        HTTPException: If extension is not allowed.
    """
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )
    return FILE_TYPE_MAP[ext]


def validate_file_size(file_size: int) -> None:
    """Validate file size is within limits.

    Args:
        file_size: Size in bytes.

    Raises:
        HTTPException: If file exceeds max size.
    """
    if file_size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large ({file_size / 1024 / 1024:.1f}MB). Maximum: {MAX_FILE_SIZE_BYTES / 1024 / 1024:.0f}MB",
        )


def compute_processing_duration(doc: Document) -> float | None:
    """Compute processing duration if document is in terminal state.

    Args:
        doc: Document ORM model.

    Returns:
        Duration in seconds, or None if still processing.
    """
    if doc.status == "processing":
        return None
    if doc.processed_at and doc.created_at:
        return (doc.processed_at - doc.created_at).total_seconds()
    return None


def extract_graph_status(meta: dict | None) -> str | None:
    """Extract graph_status from document meta if present.

    Args:
        meta: Document metadata dict.

    Returns:
        Graph status string or None.
    """
    if not meta:
        return None
    return meta.get("graph_status")


async def trigger_document_processing(
    document_id: str,
    user_id: str,
) -> None:
    """Background task to process a document after upload.

    Initializes all dependencies and runs the document processor.
    Any errors are caught and logged; document status is updated
    by the processor itself.

    Args:
        document_id: UUID of the document to process.
        user_id: User ID for RLS enforcement.
    """
    try:
        logger.info("Starting background processing for document: %s", document_id)

        # TODO: Import and use DocumentProcessor when available
        # For now, this is a placeholder that will be implemented
        # when the document processing pipeline is migrated

        logger.info("Background processing complete for document: %s", document_id)

    except Exception:
        # Log error but don't re-raise - processor should have set status to failed
        logger.exception("Background processing failed for document: %s", document_id)


# =============================================================================
# Endpoints
# =============================================================================


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: {
            "model": ErrorResponse,
            "description": "Unsupported file type",
        },
        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE: {
            "model": ErrorResponse,
            "description": "File too large",
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "model": ErrorResponse,
            "description": "Storage upload failed",
        },
    },
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    user_id: UserIdDep,
    db: DbDep,
    storage: StorageDep,
) -> UploadResponse:
    """Upload a document and initiate background processing.

    Validates the file type and size, creates a document record,
    uploads to Supabase Storage, and triggers background processing.

    Args:
        background_tasks: FastAPI background tasks for async processing.
        file: Uploaded file from multipart/form-data.
        user_id: Current user ID from auth dependency.
        db: Database session.
        storage: Storage service for file operations.

    Returns:
        UploadResponse with document_id and initial status.

    Raises:
        HTTPException: For validation errors or storage failures.
    """
    # Validate filename exists
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided",
        )

    # Validate extension
    file_type = validate_file_extension(file.filename)

    # Read file content for size validation and upload
    try:
        file_content = await file.read()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read file: {e}",
        ) from e

    # Validate size
    file_size = len(file_content)
    validate_file_size(file_size)

    # Generate document ID
    document_id = str(uuid.uuid4())

    # Build storage path: {user_id}/{document_id}/{filename}
    storage_path = f"{user_id}/{document_id}/{file.filename}"

    logger.info(
        "Processing upload: %s (type=%s, size=%d bytes) for user=%s",
        file.filename,
        file_type,
        file_size,
        user_id,
    )

    # Create document record first
    doc_service = DocumentService(db)
    try:
        doc_record = await doc_service.create(
            user_id=user_id,
            filename=file.filename,
            file_type=file_type,
            file_size=file_size,
            storage_path=storage_path,
            status="processing",
        )
    except Exception as e:
        logger.exception("Failed to create document record")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create document record: {e}",
        ) from e

    # Upload to storage
    try:
        await storage.upload_file(
            bucket_name=STORAGE_BUCKET,
            file_path=storage_path,
            file_data=file_content,
            content_type=file.content_type or "application/octet-stream",
        )
    except StorageError as e:
        # Try to update document status to failed
        try:
            await doc_service.update_status(
                document_id=doc_record.id,
                user_id=user_id,
                status="failed",
                error_msg=f"Storage upload failed: {e}",
            )
        except Exception as cleanup_error:
            logger.error("Failed to update status after upload error: %s", cleanup_error)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file to storage: {e}",
        ) from e

    # Trigger background processing
    background_tasks.add_task(
        trigger_document_processing,
        document_id=doc_record.id,
        user_id=user_id,
    )

    logger.info(
        "Upload complete, background processing triggered: %s",
        doc_record.id,
    )

    # Commit the transaction before returning
    await db.commit()

    return UploadResponse(
        document_id=doc_record.id,
        filename=doc_record.filename,
        file_type=doc_record.file_type,
        file_size=doc_record.file_size,
        status=doc_record.status,
        storage_path=doc_record.storage_path,
        created_at=doc_record.created_at,
    )


@router.get(
    "/{document_id}/status",
    response_model=DocumentStatusResponse,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Document not found"},
    },
)
async def get_document_status(
    document: DocumentDep,
) -> DocumentStatusResponse:
    """Get the current processing status of a document.

    Returns detailed status including timestamps, processing duration,
    and graph indexing status if available.

    Args:
        document: Validated Document ORM model from dependency.

    Returns:
        DocumentStatusResponse with current status and timing info.
    """
    duration = compute_processing_duration(document)
    graph_status = extract_graph_status(document.meta)

    return DocumentStatusResponse(
        document_id=document.id,
        filename=document.filename,
        file_type=document.file_type,
        status=document.status,
        error_msg=document.error_msg,
        created_at=document.created_at,
        updated_at=document.updated_at,
        processing_duration_seconds=duration,
        graph_status=graph_status,
    )


@router.get(
    "",
    response_model=DocumentListResponse,
)
async def list_documents(
    user_id: UserIdDep,
    db: DbDep,
    status_filter: Literal["processing", "ready", "failed"] | None = None,
) -> DocumentListResponse:
    """List all documents for the current user.

    Optionally filter by status. Documents are returned in descending
    order by creation date (newest first).

    Args:
        user_id: Current user ID from auth dependency.
        db: Database session.
        status_filter: Optional status to filter by.

    Returns:
        DocumentListResponse with list of document summaries.
    """
    doc_service = DocumentService(db)
    docs = await doc_service.list_by_user(user_id, status=status_filter)

    summaries = [
        DocumentSummary(
            document_id=doc.id,
            filename=doc.filename,
            file_type=doc.file_type,
            file_size=doc.file_size,
            status=doc.status,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
        )
        for doc in docs
    ]

    return DocumentListResponse(
        documents=summaries,
        total=len(summaries),
        status_filter=status_filter,
    )


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Document not found"},
    },
)
async def delete_document(
    document: DocumentDep,
    user_id: UserIdDep,
    db: DbDep,
    storage: StorageDep,
) -> None:
    """Delete a document and its associated data.

    Deletes the document record, all chunks, graph data, and the
    file from storage. This operation is idempotent - if the document
    doesn't exist, it returns 204 (no error).

    Args:
        document: Validated Document ORM model from dependency.
        user_id: Current user ID from auth dependency.
        db: Database session.
        storage: Storage service for file operations.

    Raises:
        HTTPException: If delete fails.
    """
    document_id = document.id
    storage_path = document.storage_path

    # Delete from storage first (best effort - don't fail if storage delete fails)
    try:
        await storage.delete_file(
            bucket_name=STORAGE_BUCKET,
            file_paths=storage_path,
        )
        logger.info("Deleted file from storage: %s", storage_path)
    except Exception:
        logger.warning("Failed to delete file from storage: %s", storage_path)
        # Continue with DB deletion even if storage deletion fails

    # Delete document record (cascades to chunks and graph data via FK)
    doc_service = DocumentService(db)
    deleted = await doc_service.delete(document_id, user_id)

    if deleted:
        await db.commit()
        logger.info("Deleted document: %s", document_id)
    else:
        # Document existed when we checked but was deleted between get and delete
        logger.warning("Document disappeared during deletion: %s", document_id)


__all__ = ["router"]
