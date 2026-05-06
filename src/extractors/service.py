"""Unified extraction service for all document types."""

from pathlib import Path
from typing import Any

from src.extractors.base import ExtractionResult
from src.extractors.docx import DOCXExtractor
from src.extractors.pdf import PDFExtractor
from src.extractors.xlsx import XLSXMetadata, XLSXMetadataExtractor


class ExtractionService:
    """Unified service for extracting content from various document types."""

    def __init__(self) -> None:
        self._pdf_extractor = PDFExtractor()
        self._docx_extractor = DOCXExtractor()
        self._xlsx_extractor = XLSXMetadataExtractor()

    async def extract_text(self, file_path: str | Path) -> ExtractionResult:
        """Extract text from PDF or DOCX files.

        Args:
            file_path: Path to the document

        Returns:
            ExtractionResult with text, pages, and metadata
        """
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix == ".pdf":
            return self._pdf_extractor.extract(str(path))
        elif suffix in (".docx", ".doc"):
            return self._docx_extractor.extract(str(path))
        else:
            return ExtractionResult(success=False, error=f"Unsupported file type: {suffix}")

    async def extract_metadata(self, file_path: str | Path) -> XLSXMetadata | dict[str, Any]:
        """Extract metadata from XLSX files.

        Args:
            file_path: Path to the XLSX file

        Returns:
            XLSXMetadata for XLSX files, empty dict for others
        """
        path = Path(file_path)
        if path.suffix.lower() == ".xlsx":
            return self._xlsx_extractor.extract(str(path))
        return {}


# Synchronous version for simple use cases
def extract_text_sync(file_path: str | Path) -> ExtractionResult:
    """Synchronous text extraction based on file type."""
    service = ExtractionService()
    import asyncio

    return asyncio.run(service.extract_text(file_path))
