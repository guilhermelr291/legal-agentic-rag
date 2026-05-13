# Document Processor Specification

## Problem Statement

The document upload flow in `src/documents/router.py` has a TODO placeholder for `DocumentProcessor` (line 149-151). While all individual services exist (extractors, chunking, embeddings, storage), there is no orchestrator that coordinates the complete document processing pipeline. Without this component, uploaded documents remain in `processing` status indefinitely and never become queryable by the RAG agent.

**Why now:** The document-ingestion spec (Phase 2) defines the pipeline, but the `DocumentProcessor` component that executes this pipeline was not explicitly created. The router needs this processor to handle background document processing.

---

## Goals

### Core (MVP — required)

- Implement `DocumentProcessor` class that orchestrates the complete document processing pipeline
- Integrate with existing services: Storage, Extractors, Chunking, Embeddings
- Support PDF/DOCX processing: extract → chunk → embed → persist
- Support XLSX processing: extract metadata → persist (no chunks)
- Update document status throughout processing with proper error handling
- Zero duplicate chunks per document via idempotent upsert

---

## Out of Scope (this feature)

| Feature | Reason |
|---------|--------|
| OCR for scanned PDFs | MVP targets digital PDFs only |
| Parallel processing within a single document | BackgroundTasks processes one at a time; complexity not justified |
| Real-time progress notifications | Streamlit polling is sufficient |
| Automatic retry mechanism | User must re-upload failed documents |
| Table extraction from PDF/DOCX | XLSX is handled separately; PDF tables extracted as text |
| Graph RAG / entity extraction | Separate feature to be implemented later |

---

## Definitions

### DocumentProcessor

The orchestrator class that coordinates the document processing pipeline. It:
1. Downloads the file from storage
2. Routes to appropriate extractor based on file type
3. For PDF/DOCX: chunks text, generates embeddings, persists chunks
4. For XLSX: extracts metadata, saves to document.meta
5. Updates document status at each stage
6. Handles errors gracefully with status updates

### ProcessingContext

Internal dataclass that tracks processing state:
- document_id, user_id
- file_path (temporary local path)
- extracted content/metadata
- chunks (for PDF/DOCX)
- processing stages and timings

---

## User Stories

### P1: PDF/DOCX Processing ⭐ MVP

**User Story:** As a legal user, when I upload a PDF or DOCX, I want it chunked and embedded so the RAG agent can retrieve relevant passages.

**Acceptance Criteria**

1. WHEN a PDF/DOCX is uploaded THEN processor SHALL download it from storage to a temporary location
2. WHEN file is downloaded THEN processor SHALL extract text using the appropriate extractor
3. WHEN text is extracted THEN processor SHALL apply legal-first chunking
4. WHEN chunks are created THEN processor SHALL generate embeddings in batches of 100
5. WHEN embeddings are ready THEN processor SHALL upsert chunks to database with idempotency
6. WHEN all chunks are persisted THEN processor SHALL update document `status='ready'` and set `processed_at`
7. WHEN any stage fails THEN processor SHALL set `status='failed'`, save `error_msg`, and clean up temporary files

**Independent Test**

- Upload a 5-page PDF via API → verify status transitions `processing → ready` → verify `chunks` table has records with embeddings for that document

---

### P2: XLSX Processing ⭐ MVP

**User Story:** As a user, when I upload an XLSX, I want its structure extracted so the agent can use the XLSX tool for precise queries.

**Acceptance Criteria**

1. WHEN an XLSX is uploaded THEN processor SHALL download it from storage
2. WHEN file is downloaded THEN processor SHALL extract sheet names and column names for each sheet
3. WHEN metadata is extracted THEN processor SHALL save it to `documents.meta['xlsx_structure']`
4. WHEN metadata is saved THEN processor SHALL set `status='ready'` (skip chunking/embeddings)
5. WHEN XLSX is processed THEN processor SHALL verify no `chunks` exist for that document

**Independent Test**

- Upload an XLSX with 3 sheets → verify `documents.meta['xlsx_structure']` contains correct sheets/columns → verify `chunks` table is empty for that document

---

### P3: Error Handling and Observability ⭐ MVP

**User Story:** As a developer, I want clear logs and error states when processing fails, so I can diagnose issues.

**Acceptance Criteria**

1. WHEN processing starts THEN processor SHALL log each stage with duration
2. WHEN extraction fails THEN processor SHALL set `status='failed'` with error message "Text extraction failed: {details}"
3. WHEN chunking yields 0 chunks THEN processor SHALL set `status='failed'` with error "Document contains no extractable text"
4. WHEN embeddings API fails THEN processor SHALL retry once with 2s backoff; if still fails → `status='failed'`
5. WHEN any error occurs THEN processor SHALL clean up temporary files and log the full error with traceback

**Independent Test**

- Upload a corrupted PDF → verify `status='failed'` with appropriate error message → verify temp files are cleaned up

---

## Functional Requirements

### DocumentProcessor Interface

```python
class DocumentProcessor:
    """Orchestrates document processing pipeline."""

    def __init__(
        self,
        storage: StorageService,
        extraction: ExtractionService,
        chunking: ChunkingService,
        embeddings: EmbeddingsService,
        db: AsyncSession,
    ) -> None:
        ...

    async def process(self, document_id: str, user_id: str) -> None:
        """Process a document through the complete pipeline.

        Args:
            document_id: UUID of the document to process
            user_id: User ID for RLS and isolation

        Updates document status and creates chunks in database.
        All errors are caught, logged, and status is updated to 'failed'.
        """
        ...
```

### Processing Pipeline

1. **Initialize**
   - Log start
   - Get document record from DB
   - Verify status is `processing`

2. **Download**
   - Download from storage to temp file
   - Log duration

3. **Route by Type**

   **PDF/DOCX branch:**
   - Extract text using `ExtractionService`
   - Apply legal-first chunking using `ChunkingService`
   - Generate embeddings in batches using `EmbeddingsService`
   - Upsert chunks to database with `ON CONFLICT DO UPDATE`
   - Update document `status='ready'`

   **XLSX branch:**
   - Extract sheet/column metadata using `XLSXMetadataExtractor`
   - Save to `documents.meta['xlsx_structure']`
   - Update document `status='ready'`

4. **Cleanup**
   - Delete temp file (always, even on error)
   - Log completion/failure with total duration

### Error Handling with Specific Exceptions

The processor uses a hierarchy of specific exceptions that inherit from `ProcessingError`. Each exception includes:
- **Descriptive message**: Human-readable error description
- **Error code**: Machine-readable code for programmatic handling (e.g., `EXTRACTION_FAILED`)
- **Stage**: Which pipeline stage failed (`extraction`, `chunking`, `embedding`, `persistence`)

| Stage | Exception | Error Code | Behavior |
|-------|-----------|------------|----------|
| Download | `StorageError` | `STORAGE_ERROR` | status='failed', error_msg=exc.message |
| Extract | `ExtractionFailedError` | `EXTRACTION_FAILED` | status='failed', error_msg=exc.message |
| Extract | `NoTextContentError` | `NO_TEXT_CONTENT` | status='failed', error_msg=exc.message |
| Chunk | `ChunkingFailedError` | `CHUNKING_FAILED` | status='failed', error_msg=exc.message |
| Embed | `EmbeddingGenerationError` | `EMBEDDING_FAILED` | status='failed', error_msg=exc.message |
| Persist | `DatabaseError` | `DATABASE_ERROR` | status='failed', error_msg=exc.message |

### Exception Hierarchy

```python
# src/documents/exceptions.py
from src.common.exceptions import ProcessingError

class DocumentProcessingError(ProcessingError):
    """Base for document processing pipeline errors."""
    
    def __init__(self, message: str, stage: str, code: str):
        super().__init__(message, code)
        self.stage = stage  # 'extraction', 'chunking', 'embedding', 'persistence'

class ExtractionFailedError(DocumentProcessingError):
    """Text extraction failed (PDF/DOCX)."""
    
    def __init__(self, message: str, file_type: str):
        super().__init__(
            message=f"Failed to extract text from {file_type}: {message}",
            stage="extraction",
            code="EXTRACTION_FAILED"
        )
        self.file_type = file_type

class NoTextContentError(DocumentProcessingError):
    """Document has no extractable text."""
    
    def __init__(self):
        super().__init__(
            message="Document contains no extractable text",
            stage="extraction",
            code="NO_TEXT_CONTENT"
        )

class ChunkingFailedError(DocumentProcessingError):
    """Legal chunking failed."""
    
    def __init__(self, message: str):
        super().__init__(
            message=f"Failed to chunk document: {message}",
            stage="chunking",
            code="CHUNKING_FAILED"
        )

class EmbeddingGenerationError(DocumentProcessingError):
    """Embedding API failed after retries."""
    
    def __init__(self, message: str, batch_number: int | None = None):
        super().__init__(
            message=f"Failed to generate embeddings: {message}",
            stage="embedding",
            code="EMBEDDING_FAILED"
        )
        self.batch_number = batch_number

class DatabaseError(DocumentProcessingError):
    """Database persistence failed."""
    
    def __init__(self, message: str):
        super().__init__(
            message=f"Database error: {message}",
            stage="persistence",
            code="DATABASE_ERROR"
        )
```

### Observability

- Log at INFO level for each stage start/complete
- Log stage duration
- Log at ERROR level for failures with full traceback
- Context: document_id, user_id, file_type

---

## Edge Cases

### Validation & Extraction

- WHEN PDF has no extractable text THEN raise `NoTextContentError` → status='failed', error_msg='Document contains no extractable text', code='NO_TEXT_CONTENT'
- WHEN file is deleted from storage during processing THEN raise `StorageError` → status='failed', error_msg='Storage download failed: file not found', code='STORAGE_ERROR'
- WHEN temp directory has no space THEN raise `StorageError` → status='failed', error_msg='Storage download failed: insufficient space', code='STORAGE_ERROR'
- WHEN PDF is corrupted THEN raise `ExtractionFailedError` → status='failed', error_msg='Failed to extract text from pdf: PDF extraction failed: file corrupted', code='EXTRACTION_FAILED'

### Chunking

- WHEN chunk > 1000 tokens THEN split by paragraph
- WHEN chunk < 100 tokens THEN merge with next chunk
- WHEN document has only headers THEN merge adjacent headers
- WHEN chunking fails unexpectedly THEN raise `ChunkingFailedError` → status='failed', code='CHUNKING_FAILED'

### Embeddings

- WHEN batch fails (API error) THEN retry once with 2s sleep
- WHEN retry also fails THEN raise `EmbeddingGenerationError` → status='failed', code='EMBEDDING_FAILED'
- WHEN batch size < 100 (last batch) THEN process normally

### XLSX

- WHEN XLSX has password protection THEN raise `ExtractionFailedError` → status='failed', error_msg='Failed to extract text from xlsx: Encrypted XLSX not supported', code='EXTRACTION_FAILED'
- WHEN XLSX has 0 sheets THEN raise `ExtractionFailedError` → status='failed', error_msg='Failed to extract text from xlsx: Empty XLSX file', code='EXTRACTION_FAILED'

### Cleanup

- WHEN temp file doesn't exist (already cleaned) THEN log warning, don't raise
- WHEN cleanup fails (permission error) THEN log error but don't affect status

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
|----------------|-------|-------|--------|
| PROC-01 | P1 PDF/DOCX | Design | **In Design** |
| PROC-02 | P1 PDF/DOCX | Design | **In Design** |
| PROC-03 | P1 PDF/DOCX | Design | **In Design** |
| PROC-04 | P1 PDF/DOCX | Design | **In Design** |
| PROC-05 | P1 PDF/DOCX | Design | **In Design** |
| PROC-06 | P1 PDF/DOCX | Design | **In Design** |
| PROC-07 | P1 PDF/DOCX | Design | **In Design** |
| PROC-08 | P2 XLSX | Design | **In Design** |
| PROC-09 | P2 XLSX | Design | **In Design** |
| PROC-10 | P2 XLSX | Design | **In Design** |
| PROC-11 | P2 XLSX | Design | **In Design** |
| PROC-12 | P2 XLSX | Design | **In Design** |
| PROC-13 | P3 Error Handling | Design | **In Design** |
| PROC-14 | P3 Error Handling | Design | **In Design** |
| PROC-15 | P3 Error Handling | Design | **In Design** |
| PROC-16 | P3 Error Handling | Design | **In Design** |
| PROC-17 | P3 Error Handling | Design | **In Design** |

**ID format:** `PROC-[NUMBER]`

**Status values:** Pending → In Design → In Tasks → Implementing → Verified

---

## Success Criteria

### MVP (All Features)

- [ ] User uploads PDF → status `ready` in < 30 seconds (10-page document)
- [ ] User uploads XLSX → `documents.meta['xlsx_structure']` contains correct metadata
- [ ] Corrupted PDF fails gracefully with clear error message in `error_msg`
- [ ] Zero duplicate chunks per document (`UNIQUE(document_id, chunk_index)` enforced)
- [ ] Temp files are always cleaned up (verify after 100 uploads)

---

## Technical Notes

### Dependencies

All dependencies already exist from Phase 2 refactor:

```python
# Existing services to integrate
from src.storage.service import StorageService
from src.extractors.service import ExtractionService
from src.chunking.service import ChunkingService
from src.embeddings.service import EmbeddingsService
from src.documents.service import DocumentService

# Database
from src.common.database import AsyncSession
```

### File Locations

- **New file:** `src/documents/processor.py` — DocumentProcessor implementation
- **New file:** `src/documents/exceptions.py` — Document processing exception hierarchy (DocumentProcessingError, ExtractionFailedError, etc.)
- **Update:** `src/documents/router.py` — Replace TODO with actual processor call
- **Update:** `src/documents/service.py` — May need chunk upsert method
- **Update:** `src/documents/dependencies.py` — Add `ProcessorDep` if needed

### Temp File Handling

```python
import tempfile
from pathlib import Path

# Use tempfile for automatic cleanup
with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
    tmp_path = Path(tmp.name)
    try:
        # Download and process
        await storage.download_to_path(bucket, path, tmp_path)
        # ... process ...
    finally:
        # Always cleanup
        if tmp_path.exists():
            tmp_path.unlink()
```

### Chunk Upsert Pattern

```python
# SQLAlchemy 2.0 upsert for chunks
from sqlalchemy.dialects.postgresql import insert

stmt = insert(Chunk).values(chunk_data)
stmt = stmt.on_conflict_do_update(
    index_elements=['document_id', 'chunk_index'],
    set_=dict(
        content=stmt.excluded.content,
        embedding=stmt.excluded.embedding,
        # ... other fields
    )
)
await db.execute(stmt)
```

### Dependencies Integration

The processor will be instantiated in the background task with all required services:

```python
async def trigger_document_processing(
    document_id: str,
    user_id: str,
) -> None:
    """Background task to process a document."""
    # Initialize services
    storage = await StorageService.from_service_role()
    extraction = ExtractionService()
    chunking = ChunkingService()
    embeddings = EmbeddingsService()
    
    async with SessionFactory() as db:
        processor = DocumentProcessor(
            storage=storage,
            extraction=extraction,
            chunking=chunking,
            embeddings=embeddings,
            db=db,
        )
        await processor.process(document_id, user_id)
```

---

## References

- Document Ingestion Spec: `.specs/features/document-ingestion/spec.md`
- FastAPI Standards: `.cursor/rules/agentic-rag-standards.mdc`
- Router TODO: `src/documents/router.py:149-151`
- Phase 2 Tasks: `.specs/features/refactor-to-standards/tasks.md`

---

## Open Questions

None. This spec derives directly from the document-ingestion spec and existing service implementations.
