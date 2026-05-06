"""PDF text extractor using PyPDFLoader."""

from langchain_community.document_loaders import PyPDFLoader

from src.extractors.base import ExtractionResult, TextExtractor


class PDFExtractor(TextExtractor):
    """Extract text and metadata from PDF files."""

    def extract(self, file_path: str) -> ExtractionResult:
        """Extract text and metadata from a PDF file.

        Args:
            file_path: Path to the PDF file

        Returns:
            ExtractionResult with text, pages list, and metadata
        """
        try:
            loader = PyPDFLoader(file_path)
            pages = loader.load()

            if not pages:
                return self._create_error_result("PDF contains no pages")

            # Build text with page boundaries
            full_text_parts: list[str] = []
            page_boundaries: list[dict] = []
            current_char = 0

            for page in pages:
                page_text = page.page_content
                page_label = page.metadata.get("page_label")
                if page_label is not None:
                    try:
                        page_number = int(page_label)
                    except ValueError:
                        page_number = page_label  # Keep as string for roman numerals, etc.
                else:
                    page_number = page.metadata.get("page", 0) + 1

                page_boundaries.append(
                    {
                        "number": page_number,
                        "start_char": current_char,
                        "end_char": current_char + len(page_text),
                    }
                )

                full_text_parts.append(page_text)
                current_char += len(page_text)

            full_text = "\n\n".join(full_text_parts)

            # Extract basic metadata
            metadata: dict = {
                "total_pages": len(pages),
                "source": file_path,
            }

            # Add any available PDF metadata from first page
            if pages and pages[0].metadata:
                pdf_meta = pages[0].metadata
                for key in ["title", "author", "subject", "creator", "producer"]:
                    if key in pdf_meta:
                        metadata[key] = pdf_meta[key]

            return ExtractionResult(
                text=full_text,
                pages=page_boundaries,
                metadata=metadata,
                success=True,
            )

        except FileNotFoundError:
            return self._create_error_result(f"File not found: {file_path}")
        except PermissionError:
            return self._create_error_result(f"Permission denied: {file_path}")
        except Exception as e:
            return self._create_error_result(f"PDF extraction failed: {e!s}")
