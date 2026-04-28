"""Base text extractor interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ExtractionResult:
    """Result from text extraction.

    Attributes:
        text: Extracted text content
        pages: List of page information (number, start/end char positions)
        metadata: Additional file-specific metadata
        success: Whether extraction succeeded
        error: Error message if extraction failed
    """

    text: str = ""
    pages: List[Dict[str, Any]] = None
    metadata: Dict[str, Any] = None
    success: bool = True
    error: Optional[str] = None

    def __post_init__(self):
        if self.pages is None:
            self.pages = []
        if self.metadata is None:
            self.metadata = {}


class TextExtractor(ABC):
    """Abstract base class for text extractors."""

    @abstractmethod
    def extract(self, file_path: str) -> ExtractionResult:
        """Extract text and metadata from a file.

        Args:
            file_path: Path to the file to extract

        Returns:
            ExtractionResult with text, pages, and metadata
        """
        pass

    def _create_error_result(self, error_msg: str) -> ExtractionResult:
        """Create a failed extraction result.

        Args:
            error_msg: Error message describing what went wrong

        Returns:
            ExtractionResult with success=False and error message
        """
        return ExtractionResult(
            text="",
            pages=[],
            metadata={},
            success=False,
            error=error_msg,
        )
