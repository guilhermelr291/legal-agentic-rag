"""Extractors domain dependencies."""

from typing import Annotated

from fastapi import Depends

from src.extractors.service import ExtractionService


def get_extraction_service() -> ExtractionService:
    """Factory dependency for ExtractionService."""
    return ExtractionService()


ExtractionDep = Annotated[ExtractionService, Depends(get_extraction_service)]
