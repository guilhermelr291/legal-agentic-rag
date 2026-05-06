"""Documents domain dependencies.

Provides FastAPI dependencies for document routes using modern
Annotated[...] pattern and dependency chaining.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, status
from sqlalchemy import select

from src.common.database import DbDep
from src.documents.models import Document


async def get_current_user_id() -> str:
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


async def valid_document_id(
    document_id: str,
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: DbDep,
) -> Document:
    """Validate document exists and belongs to user.

    Args:
        document_id: UUID of the document to validate.
        user_id: Current user ID from auth dependency.
        db: Database session.

    Returns:
        Document ORM model instance.

    Raises:
        HTTPException: 404 if document not found, 403 if access denied.
    """
    result = await db.execute(select(Document).where(Document.id == document_id))
    document = result.scalar_one_or_none()

    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document not found: {document_id}",
        )

    if document.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this document",
        )

    return document


# Type aliases for Annotated dependency injection (modern FastAPI pattern)
UserIdDep = Annotated[str, Depends(get_current_user_id)]
DocumentDep = Annotated[Document, Depends(valid_document_id)]


__all__ = [
    "get_current_user_id",
    "valid_document_id",
    "UserIdDep",
    "DocumentDep",
]
