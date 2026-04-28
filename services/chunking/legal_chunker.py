"""Legal document chunking with structure preservation using LangChain."""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import tiktoken
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


@dataclass
class LegalChunk:
    """A chunk of legal document with metadata for Graph RAG.

    Attributes:
        content: The chunk text content
        chunk_index: Sequential index within document
        section_hint: Detected heading (e.g., 'Clause 12', 'Art. 5')
        section_path: Hierarchy breadcrumbs
        page_start: Starting page number
        page_end: Ending page number
        anchors: Detected references in text (for Graph RAG edges)
        char_start: Start character offset
        char_end: End character offset
        token_count: Number of tokens in the chunk
    """

    content: str = ""
    chunk_index: int = 0
    section_hint: Optional[str] = None
    section_path: List[str] = field(default_factory=list)
    page_start: Optional[int] = None
    page_end: Optional[int] = None
    anchors: List[str] = field(default_factory=list)
    char_start: int = 0
    char_end: int = 0
    token_count: int = 0


class LegalChunker:
    """Hybrid chunker: LangChain for robust splitting + custom metadata enrichment.

    Uses RecursiveCharacterTextSplitter with tiktoken for accurate token counting,
    then enriches chunks with legal-specific metadata (section hints, anchors, etc.)
    for Graph RAG support.

    Config:
        chunk_size: Maximum tokens per chunk (default: 1000)
        chunk_overlap: Tokens to overlap between chunks (default: 10% of chunk_size)
    """

    
    HEADING_PATTERNS = [
        (r"^\d+\.\s*", "numbered_section"),
        (r"^Article\s+\d+|^Art\.\s*\d+", "article"),
        (r"^CLAUSE\s+\d+", "clause"),
        (r"^SECTION\s+|^CHAPTER\s+|^TITLE\s+", "section"),
    ]

    
    ANCHOR_PATTERNS = [
        (r"Clause\s+(\d+)", "Clause"),
        (r"Article\s+(\d+)|Art\.?\s*(\d+)", "Article"),
        (r"Annex\s+(\w+)", "Annex"),
        (r"Section\s+(\d+)", "Section"),
    ]

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: Optional[int] = None,
    ):
        """Initialize the chunker with configuration.

        Args:
            chunk_size: Maximum tokens per chunk (default: 1000)
            chunk_overlap: Tokens to overlap between chunks.
                          If None, defaults to 10% of chunk_size.
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap if chunk_overlap is not None else chunk_size // 10
        self.encoding = tiktoken.get_encoding("cl100k_base")

        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=self._count_tokens,
            separators=["\n\n", "\n", ". ", " ", ""],
            add_start_index=True,
        )

    def _count_tokens(self, text: str) -> int:
        """Count tokens using tiktoken (OpenAI cl100k_base encoding).

        Args:
            text: Text to count tokens for

        Returns:
            Number of tokens
        """
        return len(self.encoding.encode(text))

    def _detect_heading(self, text: str) -> Optional[str]:
        """Detect heading in the first line of text.

        Args:
            text: Text to analyze

        Returns:
            Detected heading text or None
        """
        first_line = text.split("\n")[0].strip()
        for pattern, _ in self.HEADING_PATTERNS:
            if re.match(pattern, first_line, re.IGNORECASE):
                return first_line
        return None

    def _extract_anchors(self, text: str) -> List[str]:
        """Extract anchor references from text for Graph RAG edges.

        Detects references like "Clause X", "Article Y", "Annex Z", "Section N".

        Args:
            text: Text to analyze for anchors

        Returns:
            List of detected anchor strings
        """
        anchors = []
        for pattern, prefix in self.ANCHOR_PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                groups = match.groups()
                value = next((g for g in groups if g is not None), "")
                if value:
                    anchors.append(f"{prefix} {value}")
        return list(set(anchors))  # Remove duplicates

    def chunk(
        self, text: str, pages: List[Dict[str, Any]]
    ) -> List[LegalChunk]:
        """Chunk text into LegalChunk objects with metadata for Graph RAG.

        Uses LangChain's RecursiveCharacterTextSplitter for robust token-based
        splitting, then enriches with legal-specific metadata.

        Processes each page separately to preserve accurate page numbers
        from the source document (e.g., page_label from PDF).

        Args:
            text: Document text to chunk
            pages: List of page info with number, start_char, end_char.
                   Each chunk will have page_start/page_end set to the actual
                   page number from the source (e.g., page_label).

        Returns:
            List of LegalChunk objects with all metadata fields
        """
        if not text.strip():
            return []

        chunks: List[LegalChunk] = []

        # Process page by page to preserve accurate page numbers
        for page in pages:
            page_text = text[page["start_char"] : page["end_char"]]
            page_number = page["number"]

            documents: List[Document] = self.splitter.create_documents([page_text])

            for doc in documents:
                content = doc.page_content

                # Position within the full document
                char_start = page["start_char"] + doc.metadata.get("start_index", 0)
                char_end = char_start + len(content)

                # Extract legal metadata
                section_hint = self._detect_heading(content)
                anchors = self._extract_anchors(content)
                token_count = self._count_tokens(content)

                chunks.append(
                    LegalChunk(
                        content=content,
                        chunk_index=len(chunks),
                        section_hint=section_hint,
                        section_path=[section_hint] if section_hint else [],
                        page_start=page_number,
                        page_end=page_number,
                        anchors=anchors,
                        char_start=char_start,
                        char_end=char_end,
                        token_count=token_count,
                    )
                )

        return chunks
