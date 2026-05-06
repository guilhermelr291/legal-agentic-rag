"""Extractors domain for document text and metadata extraction."""

from src.extractors.base import ExtractionResult, TextExtractor
from src.extractors.config import ExtractorsConfig, extractors_settings
from src.extractors.dependencies import ExtractionDep, get_extraction_service
from src.extractors.docx import DOCXExtractor
from src.extractors.pdf import PDFExtractor
from src.extractors.service import ExtractionService, extract_text_sync
from src.extractors.xlsx import XLSXMetadata, XLSXMetadataExtractor

__all__ = [
    "ExtractorsConfig",
    "extractors_settings",
    "TextExtractor",
    "ExtractionResult",
    "PDFExtractor",
    "DOCXExtractor",
    "XLSXMetadataExtractor",
    "XLSXMetadata",
    "ExtractionService",
    "extract_text_sync",
    "ExtractionDep",
    "get_extraction_service",
]
