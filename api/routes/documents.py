"""FastAPI routes for document upload and status management.

Provides endpoints for:
- POST /documents/upload - Upload and initiate document processing
- GET /documents/{document_id}/status - Check processing status
- GET /documents - List user's documents with optional filtering
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, status

from api.models import (
    DocumentListResponse,
    DocumentStatusResponse,
    DocumentSummary,
    ErrorResponse,
    UploadResponse,
)
from my_agent.config.settings import get_settings
from services.db.repositories import DocumentCreate, DocumentRecord, DocumentRepository
from services.document_processor import DocumentProcessor
from services.embeddings.generator import EmbeddingGenerator
from services.storage.supabase_client import StorageError, SupabaseClient

logger = logging.getLogger(__name__)

# =============================================================================
# Constants
# =============================================================================

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".xlsx"}
MAX_FILE_SIZE_MB = 50
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
STORAGE_BUCKET = "documents"

# Map extensions to file types
FILE_TYPE_MAP: dict[str, Literal["pdf", "docx", "xlsx"]] = {
    ".pdf": "pdf",
    ".docx": "docx",
    ".xlsx": "xlsx",
}

# =============================================================================
# Router
# =============================================================================

router = APIRouter(prefix="/documents", tags=["documents"])


# =============================================================================
# Dependencies
# =============================================================================


async def get_supabase_client() -> SupabaseClient:
    """Dependency to get a Supabase client instance.

    Returns:
        Configured SupabaseClient using service role credentials.

    Raises:
        HTTPException: If client initialization fails.
    """
    try:
        return await SupabaseClient.from_service_role()
    except Exception as e:
        logger.exception("Failed to initialize Supabase client")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Storage service unavailable: {e}",
        ) from e


async def get_document_repo(
    client: SupabaseClient = Depends(get_supabase_client),
) -> DocumentRepository:
    """Dependency to get a DocumentRepository instance."""
    return DocumentRepository(client)


def get_current_user_id() -> str:
    """Extract user_id from request (placeholder for JWT auth).

    In production, this would validate a JWT token and extract the user_id.
    For now, returns a placeholder that should be replaced with proper auth.

    Returns:
        User ID string.

    TODO: Replace with actual JWT validation when auth is implemented.
    """
    # Placeholder - in production, extract from JWT token
    # This should be replaced with proper authentication middleware
    return "test-user-id"


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
            detail=f"File too large ({file_size / 1024 / 1024:.1f}MB). Maximum: {MAX_FILE_SIZE_MB}MB",
        )


def compute_processing_duration(doc: DocumentRecord) -> float | None:
    """Compute processing duration if document is in terminal state.

    Args:
        doc: Document record.

    Returns:
        Duration in seconds, or None if still processing.
    """
    if doc.status == "processing":
        return None
    return (doc.updated_at - doc.created_at).total_seconds()


def extract_graph_status(meta: dict) -> str | None:
    """Extract graph_status from document meta if present.

    Args:
        meta: Document metadata dict.

    Returns:
        Graph status string or None.
    """
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

        # Initialize dependencies
        client = await SupabaseClient.from_service_role()
        doc_repo = DocumentRepository(client)
        from services.db.repositories import ChunkRepository

        chunk_repo = ChunkRepository(client)
        embed_gen = EmbeddingGenerator()

        # Create and run processor
        processor = DocumentProcessor(
            storage_client=client,
            document_repo=doc_repo,
            chunk_repo=chunk_repo,
            embedding_generator=embed_gen,
        )

        await processor.process(document_id, user_id)

        logger.info("Background processing complete for document: %s", document_id)

    except Exception as e:
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
        400: {"model": ErrorResponse, "description": "Unsupported file type"},
        413: {"model": ErrorResponse, "description": "File too large"},
        500: {"model": ErrorResponse, "description": "Storage upload failed"},
    },
)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile,
    user_id: str = Depends(get_current_user_id),
    doc_repo: DocumentRepository = Depends(get_document_repo),
    client: SupabaseClient = Depends(get_supabase_client),
) -> UploadResponse:
    """Upload a document and initiate background processing.

    Validates the file type and size, creates a document record,
    uploads to Supabase Storage, and triggers background processing.

    Args:
        background_tasks: FastAPI background tasks for async processing.
        file: Uploaded file from multipart/form-data.
        user_id: Current user ID from auth dependency.
        doc_repo: Document repository for database operations.
        client: Supabase client for storage operations.

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
    doc_create = DocumentCreate(
        user_id=user_id,
        filename=file.filename,
        file_type=file_type,
        file_size=file_size,
        storage_path=storage_path,
        status="processing",
    )

    try:
        doc_record = await doc_repo.create(doc_create)
    except Exception as e:
        logger.exception("Failed to create document record")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create document record: {e}",
        ) from e

    # Upload to storage
    try:
        await client.upload_file(
            bucket_name=STORAGE_BUCKET,
            file_path=storage_path,
            file_data=file_content,
            content_type=file.content_type or "application/octet-stream",
        )
    except StorageError as e:
        # Try to update document status to failed
        try:
            await doc_repo.update_status(
                document_id=doc_record.id,
                status="failed",
                error_msg=f"Storage upload failed: {e}",
                user_id=user_id,
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
        404: {"model": ErrorResponse, "description": "Document not found"},
    },
)
async def get_document_status(
    document_id: str,
    user_id: str = Depends(get_current_user_id),
    doc_repo: DocumentRepository = Depends(get_document_repo),
) -> DocumentStatusResponse:
    """Get the current processing status of a document.

    Returns detailed status including timestamps, processing duration,
    and graph indexing status if available.

    Args:
        document_id: UUID of the document to check.
        user_id: Current user ID from auth dependency.
        doc_repo: Document repository for database operations.

    Returns:
        DocumentStatusResponse with current status and timing info.

    Raises:
        HTTPException: If document not found or access denied.
    """
    doc = await doc_repo.get_by_id(document_id, user_id)

    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {document_id}",
        )

    duration = compute_processing_duration(doc)
    graph_status = extract_graph_status(doc.meta)

    return DocumentStatusResponse(
        document_id=doc.id,
        filename=doc.filename,
        file_type=doc.file_type,
        status=doc.status,
        error_msg=doc.error_msg,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        processing_duration_seconds=duration,
        graph_status=graph_status,
    )


@router.get(
    "",
    response_model=DocumentListResponse,
)
async def list_documents(
    status_filter: Literal["processing", "ready", "failed"] | None = None,
    user_id: str = Depends(get_current_user_id),
    doc_repo: DocumentRepository = Depends(get_document_repo),
) -> DocumentListResponse:
    """List all documents for the current user.

    Optionally filter by status. Documents are returned in descending
    order by creation date (newest first).

    Args:
        status_filter: Optional status to filter by.
        user_id: Current user ID from auth dependency.
        doc_repo: Document repository for database operations.

    Returns:
        DocumentListResponse with list of document summaries.
    """
    docs = await doc_repo.list_by_user(user_id, status=status_filter)

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
