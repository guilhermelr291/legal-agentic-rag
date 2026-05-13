# Document Processor Design

**Spec**: `.specs/features/document-processor/spec.md`  
**Status**: Draft

---

## Architecture Overview

The Document Processor is an orchestrator that coordinates the complete document processing pipeline. It operates as a background task (FastAPI BackgroundTasks) to process uploaded documents asynchronously without blocking the HTTP response.

```mermaid
flowchart TD
    subgraph "Document Upload Flow"
        A[Client Uploads File] --> B[POST /documents/upload]
        B --> C[Create Document Record<br/>status='processing']
        C --> D[Upload to Storage]
        D --> E[Add Background Task]
        E --> F[Return 201 Created]
    end

    subgraph "Background Processing"
        F --> G[trigger_document_processing]
        G --> H[DocumentProcessor.process]

        H --> I{File Type?}
        I -->|PDF/DOCX| J[Vector Pipeline]
        I -->|XLSX| K[Metadata Pipeline]

        subgraph "Vector Pipeline"
            J --> J1[Download from Storage]
            J1 --> J2[Extract Text]
            J2 --> J3[Chunk Document]
            J3 --> J4[Generate Embeddings]
            J4 --> J5[Upsert Chunks]
            J5 --> J6[status='ready']
        end

        subgraph "Metadata Pipeline"
            K --> K1[Download from Storage]
            K1 --> K2[Extract XLSX Metadata]
            K2 --> K3[Save to meta['xlsx_structure']]
            K3 --> K4[status='ready']
        end

        J6 --> L[Cleanup Temp Files]
        K4 --> L
    end

    subgraph "Error Handling"
        J2 -->|Extraction Failed| M[status='failed']
        J3 -->|No Text Content| M
        J4 -->|Embedding Failed| M
        J5 -->|Database Error| M
        K2 -->|XLSX Error| M
        M --> L
    end
```



---

## Code Reuse Analysis

### Existing Components to Leverage


| Component           | Location                    | How to Use                                              |
| ------------------- | --------------------------- | ------------------------------------------------------- |
| `StorageService`    | `src/storage/service.py`    | Download files from Supabase Storage to temp location   |
| `ExtractionService` | `src/extractors/service.py` | Extract text (PDF/DOCX) or metadata (XLSX)              |
| `ChunkingService`   | `src/chunking/service.py`   | Split documents into `LegalChunk` objects with metadata |
| `EmbeddingsService` | `src/embeddings/service.py` | Generate OpenAI embeddings in batches with retry        |
| `DocumentService`   | `src/documents/service.py`  | Update document status, meta, error messages            |
| `ProcessingError`   | `src/common/exceptions.py`  | Base exception class to extend                          |
| `SessionFactory`    | `src/common/database.py`    | Create isolated DB sessions in background tasks         |
| `Document`, `Chunk` | `src/documents/models.py`   | SQLAlchemy ORM models with proper relationships         |


### Integration Points


| System               | Integration Method                                          |
| -------------------- | ----------------------------------------------------------- |
| **Supabase Storage** | `StorageService.download_file()` → temp file                |
| **Extractors**       | `ExtractionService.extract_text()` / `extract_metadata()`   |
| **Chunking**         | `ChunkingService.chunk()` with pages from extraction result |
| **Embeddings**       | `EmbeddingsService.generate_embeddings()` with batching     |
| **Database**         | SQLAlchemy async session with `SessionFactory`              |


### Files to Create/Modify


| File                            | Action     | Purpose                                                                        |
| ------------------------------- | ---------- | ------------------------------------------------------------------------------ |
| `src/documents/processor.py`    | **Create** | Main `DocumentProcessor` orchestrator class                                    |
| `src/documents/exceptions.py`   | **Create** | Exception hierarchy (`DocumentProcessingError`, `ExtractionFailedError`, etc.) |
| `src/documents/router.py`       | **Update** | Replace TODO at lines 149-151 with actual processor call                       |
| `src/documents/service.py`      | **Update** | Add `upsert_chunks()` method for idempotent chunk persistence                  |
| `src/documents/dependencies.py` | **Update** | Add `ProcessorDep` if dependency injection pattern desired                     |


---

## Components

### DocumentProcessor

- **Purpose**: Orchestrates the complete document processing pipeline from download to completion
- **Location**: `src/documents/processor.py`
- **Interfaces**:
  - `__init__(storage, extraction, chunking, embeddings, db)` - Initialize with all service dependencies
  - `async process(document_id: str, user_id: str) -> None` - Main entry point, processes document end-to-end
  - `async _process_pdf_docx(ctx: ProcessingContext) -> None` - Vector pipeline for text documents
  - `async _process_xlsx(ctx: ProcessingContext) -> None` - Metadata pipeline for spreadsheets
  - `async _cleanup_temp_file(path: Path) -> None` - Cleanup helper
- **Dependencies**: All service classes passed via constructor injection
- **Reuses**: FastAPI background task pattern, SQLAlchemy async patterns from codebase

### ProcessingContext (Internal Dataclass)

- **Purpose**: Tracks processing state across pipeline stages
- **Location**: `src/documents/processor.py` (internal class)
- **Fields**:
  - `document_id: str` - UUID of document being processed
  - `user_id: str` - User ID for RLS
  - `file_path: Path` - Local temp file path
  - `document: Document | None` - Loaded document record
  - `extracted_text: str` - Raw extracted text
  - `chunks: list[LegalChunk]` - Generated chunks
  - `stage_timings: dict[str, float]` - Performance tracking

### Exception Hierarchy

- **Purpose**: Specific exception types for each pipeline stage with error codes
- **Location**: `src/documents/exceptions.py`
- **Interfaces**:
  - `DocumentProcessingError(message, stage, code)` - Base for all processing errors
  - `ExtractionFailedError(message, file_type)` - Text extraction failures
  - `NoTextContentError()` - Empty document content
  - `ChunkingFailedError(message)` - Chunking failures
  - `EmbeddingGenerationError(message, batch_number)` - Embedding API failures
  - `DatabaseError(message)` - Database persistence failures
- **Dependencies**: Extends `ProcessingError` from `src/common/exceptions.py`

---

## Data Models

### Existing Model Usage

**Chunk** model already has unique constraint on `(document_id, chunk_index)` for upsert operations:

```python
__table_args__ = (
    UniqueConstraint(
        "document_id", "chunk_index",
        name="chunk_document_id_chunk_index_key"
    ),
)
```

---

## Error Handling Strategy


| Error Scenario                        | Exception Type             | Handling                     | Document State                                                           |
| ------------------------------------- | -------------------------- | ---------------------------- | ------------------------------------------------------------------------ |
| File not found in storage             | `StorageError`             | Log error, set failed status | `status='failed'`, `error_msg='Storage download failed: file not found'` |
| PDF/DOCX corrupted                    | `ExtractionFailedError`    | Log with traceback           | `status='failed'`, `code='EXTRACTION_FAILED'`                            |
| Document has no text                  | `NoTextContentError`       | Log warning                  | `status='failed'`, `code='NO_TEXT_CONTENT'`                              |
| Chunking fails                        | `ChunkingFailedError`      | Log exception                | `status='failed'`, `code='CHUNKING_FAILED'`                              |
| Embedding API fails (retry exhausted) | `EmbeddingGenerationError` | Log with batch number        | `status='failed'`, `code='EMBEDDING_FAILED'`                             |
| Database upsert fails                 | `DatabaseError`            | Log with SQL details         | `status='failed'`, `code='DATABASE_ERROR'`                               |
| XLSX password protected               | `ExtractionFailedError`    | Log specific message         | `status='failed'`, `code='EXTRACTION_FAILED'`                            |


**Cleanup Guarantee**: Temp files are always cleaned up via `try/finally` or `contextlib` pattern, regardless of success or failure.

---

## Tech Decisions


| Decision                  | Choice                                            | Rationale                                                             |
| ------------------------- | ------------------------------------------------- | --------------------------------------------------------------------- |
| **Orchestrator Pattern**  | `DocumentProcessor` class with injected services  | Testable, separates concerns, allows easy mocking                     |
| **Constructor Injection** | All services passed to `__init__`                 | Follows existing codebase patterns (services receive dependencies)    |
| **Temp File Pattern**     | `tempfile.NamedTemporaryFile` with manual cleanup | Cross-platform, handles permissions, explicit cleanup in `finally`    |
| **Batch Size**            | 100 chunks per embedding batch                    | Balance between API efficiency and memory usage (configurable)        |
| **Retry Strategy**        | Single retry with 2s delay for embeddings         | Spec requirement; keeps simple without exponential backoff complexity |
| **Upsert Pattern**        | `ON CONFLICT DO UPDATE` with unique constraint    | Idempotent re-processing, prevents duplicate chunks                   |
| **Background Tasks**      | FastAPI `BackgroundTasks`                         | Spec requirement; simpler than Celery for MVP scope                   |
| **Separate DB Session**   | `SessionFactory()` in background task             | Isolated transaction, prevents blocking main request                  |
| **Exception Hierarchy**   | Stage-specific exceptions with codes              | Enables programmatic error handling and monitoring                    |


---

## Implementation Notes

### Pipeline Flow Details

```
process(document_id, user_id)
  ├── Load document record
  ├── Verify status='processing'
  ├── Download to temp file
  ├── Route by file_type:
  │   ├── 'pdf'/'docx': _process_pdf_docx()
  │   │   ├── Extract text (pages with char positions)
  │   │   ├── Validate: has content?
  │   │   ├── Chunk with page info
  │   │   ├── Validate: has chunks?
  │   │   ├── Generate embeddings (batched)
  │   │   ├── Upsert chunks to DB
  │   │   └── Update status='ready'
  │   └── 'xlsx': _process_xlsx()
  │       ├── Extract sheet/column metadata
  │       ├── Validate: has sheets?
  │       ├── Save to meta['xlsx_structure']
  │       └── Update status='ready' (no chunks/embeddings)
  ├── Cleanup temp file
  └── Log total duration
```

### Chunk Upsert SQL Pattern

```python
from sqlalchemy.dialects.postgresql import insert

stmt = insert(Chunk).values(chunk_data)
stmt = stmt.on_conflict_do_update(
    index_elements=['document_id', 'chunk_index'],
    set_=dict(
        content=stmt.excluded.content,
        embedding=stmt.excluded.embedding,
        section_hint=stmt.excluded.section_hint,
        section_path=stmt.excluded.section_path,
        page_start=stmt.excluded.page_start,
        page_end=stmt.excluded.page_end,
        anchors=stmt.excluded.anchors,
        char_start=stmt.excluded.char_start,
        char_end=stmt.excluded.char_end,
    )
)
await db.execute(stmt)
```

---

## Concerns from CONCERNS.md


| Concern                           | Mitigation in Design                                                                          |
| --------------------------------- | --------------------------------------------------------------------------------------------- |
| **Registry globals**              | DocumentProcessor receives all dependencies via constructor, no global registry needed        |
| **Supabase client compatibility** | StorageService already handles this; processor just uses the service                          |
| **Test coverage gaps**            | Design includes clear interfaces that can be mocked; background task is isolated and testable |
| **Performance - no p95 metrics**  | Processor logs stage timings to enable future metric collection                               |
| **Broad exception in lifespan**   | Processor catches specific exceptions per stage with detailed logging                         |


---

## Open Questions

None. All requirements derived from spec and existing service implementations.