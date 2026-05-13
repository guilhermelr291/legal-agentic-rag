# Document Processor Tasks

**Spec**: `.specs/features/document-processor/spec.md`  
**Design**: `.specs/features/document-processor/design.md`  
**Status**: In Tasks

---

## Task Summary

| Task | Description | Priority | Status | Requirement IDs |
|------|-------------|----------|--------|-----------------|
| T1 | Create document processing exception hierarchy | P1 | **completed** | PROC-13, PROC-14, PROC-15, PROC-16, PROC-17 |
| T2 | Create DocumentProcessor class with constructor injection | P1 | pending | PROC-01, PROC-13 |
| T3 | Implement download stage with temp file handling | P1 | pending | PROC-01, PROC-13, PROC-17 |
| T4 | Implement PDF/DOCX processing pipeline | P1 | pending | PROC-02, PROC-03, PROC-04, PROC-05, PROC-06 |
| T5 | Implement XLSX metadata extraction pipeline | P1 | pending | PROC-08, PROC-09, PROC-10, PROC-11, PROC-12 |
| T6 | Add chunk upsert method to DocumentService | P1 | pending | PROC-05 |
| T7 | Integrate processor into router background task | P1 | pending | PROC-01, PROC-07 |
| T8 | Write unit tests for DocumentProcessor | P1 | pending | All PROC requirements |

---

## Task Details

### T1: Create document processing exception hierarchy

**What**: Create `src/documents/exceptions.py` with the complete exception hierarchy as defined in the spec.

**Where**:
- Create: `src/documents/exceptions.py`

**Depends on**: None

**Reuses**:
- `ProcessingError` from `src/common/exceptions.py` as base class

**Done when**:
- [x] `DocumentProcessingError` base class exists with `message`, `stage`, `code` attributes
- [x] `ExtractionFailedError` class exists with `file_type` attribute
- [x] `NoTextContentError` class exists
- [x] `ChunkingFailedError` class exists
- [x] `EmbeddingGenerationError` class exists with `batch_number` attribute
- [x] `DatabaseError` class exists
- [x] All exception classes properly extend `DocumentProcessingError`
- [x] All exception classes are importable from the module

**Tests**:
- Unit test: Instantiate each exception type and verify attributes
- Unit test: Verify exception hierarchy (all are `DocumentProcessingError` subclasses)
- Unit test: Verify error codes match spec requirements

**Gate**:
```bash
python -c "from src.documents.exceptions import DocumentProcessingError, ExtractionFailedError, NoTextContentError, ChunkingFailedError, EmbeddingGenerationError, DatabaseError; print('All exceptions importable')"
pytest tests/unit/documents/test_exceptions.py -v
```

**Requirement Traceability**:
- Implements: PROC-13 (specific exceptions for each stage)
- Implements: PROC-14 (error codes for programmatic handling)
- Implements: PROC-15, PROC-16, PROC-17 (error handling patterns)

---

### T2: Create DocumentProcessor class with constructor injection

**What**: Create `src/documents/processor.py` with the main `DocumentProcessor` class using constructor injection for all dependencies.

**Where**:
- Create: `src/documents/processor.py`

**Depends on**: T1 (exceptions must exist)

**Reuses**:
- `StorageService` from `src/storage/service.py`
- `ExtractionService` from `src/extractors/service.py`
- `ChunkingService` from `src/chunking/service.py`
- `EmbeddingsService` from `src/embeddings/service.py`
- `ProcessingContext` dataclass (to be defined internally)

**Done when**:
- [ ] `DocumentProcessor` class exists with `__init__` accepting all required services
- [ ] `ProcessingContext` dataclass defined with all required fields
- [ ] `process()` method stub exists with proper signature
- [ ] Internal methods `_process_pdf_docx()` and `_process_xlsx()` stubs exist
- [ ] `_cleanup_temp_file()` helper method exists
- [ ] All imports are valid and module is importable

**Tests**:
- Unit test: Instantiate DocumentProcessor with mock services
- Unit test: Verify ProcessingContext can be instantiated with test data
- Unit test: Verify all required methods exist

**Gate**:
```bash
python -c "from src.documents.processor import DocumentProcessor, ProcessingContext; print('DocumentProcessor importable')"
pytest tests/unit/documents/test_processor_init.py -v
```

**Requirement Traceability**:
- Implements: PROC-01 (orchestrator class with injected services)
- Implements: PROC-13 (error handling structure in place)

---

### T3: Implement download stage with temp file handling

**What**: Implement the file download stage in DocumentProcessor with proper temp file handling and cleanup.

**Where**:
- Update: `src/documents/processor.py` (add to `process()` method)

**Depends on**: T2 (DocumentProcessor class exists)

**Reuses**:
- `StorageService.download_to_path()` method
- `tempfile.NamedTemporaryFile` for temp file creation
- SQLAlchemy async patterns for document lookup

**Done when**:
- [ ] `process()` method loads document record and verifies `status='processing'`
- [ ] File is downloaded from storage to temp location using `tempfile.NamedTemporaryFile`
- [ ] Download stage is logged with duration
- [ ] `ProcessingContext` is populated with file_path
- [ ] `_cleanup_temp_file()` properly deletes temp file in `finally` block
- [ ] Cleanup logs warning if file doesn't exist (already cleaned)
- [ ] Cleanup logs error on permission failure but doesn't affect status

**Tests**:
- Unit test: Verify temp file is created and cleaned up on success
- Unit test: Verify temp file is cleaned up on failure
- Unit test: Verify document status verification before processing
- Unit test: Verify StorageService.download_to_path is called with correct args

**Gate**:
```bash
pytest tests/unit/documents/test_processor_download.py -v
```

**Requirement Traceability**:
- Implements: PROC-01 (download file from storage to temp)
- Implements: PROC-13 (log stage with duration)
- Implements: PROC-17 (temp file cleanup guarantee)

---

### T4: Implement PDF/DOCX processing pipeline

**What**: Implement the complete vector processing pipeline for PDF and DOCX files including extraction, chunking, embeddings, and persistence.

**Where**:
- Update: `src/documents/processor.py` (implement `_process_pdf_docx()` method)

**Depends on**: T3 (download stage implemented)

**Reuses**:
- `ExtractionService.extract_text()` for text extraction
- `ChunkingService.chunk()` for legal-first chunking
- `EmbeddingsService.generate_embeddings()` for embedding generation
- PostgreSQL upsert pattern with `on_conflict_do_update`

**Done when**:
- [ ] `_process_pdf_docx()` extracts text using `ExtractionService`
- [ ] Raises `NoTextContentError` when extracted text is empty
- [ ] Chunks text using `ChunkingService` with page information
- [ ] Raises `ChunkingFailedError` when chunking fails
- [ ] Generates embeddings in batches of 100 using `EmbeddingsService`
- [ ] Retries failed batch once with 2s delay
- [ ] Raises `EmbeddingGenerationError` when retry fails
- [ ] Upserts chunks to database with `ON CONFLICT DO UPDATE`
- [ ] Updates document `status='ready'` and `processed_at` on success
- [ ] Updates document `error_msg` and `status='failed'` on any error
- [ ] Each stage logs start/complete with duration

**Tests**:
- Integration test: Full PDF pipeline with mocked services
- Unit test: Empty PDF raises `NoTextContentError`
- Unit test: Chunking failure raises `ChunkingFailedError`
- Unit test: Embedding API failure with retry logic
- Unit test: Database upsert uses correct conflict resolution

**Gate**:
```bash
pytest tests/unit/documents/test_processor_pdf_pipeline.py -v
pytest tests/integration/test_document_processor_pdf.py -v
```

**Requirement Traceability**:
- Implements: PROC-02 (extract text)
- Implements: PROC-03 (apply legal-first chunking)
- Implements: PROC-04 (generate embeddings in batches of 100)
- Implements: PROC-05 (upsert chunks with idempotency)
- Implements: PROC-06 (update status to 'ready')
- Implements: PROC-14, PROC-15, PROC-16 (error handling per stage)

---

### T5: Implement XLSX metadata extraction pipeline

**What**: Implement the metadata-only processing pipeline for XLSX files that extracts sheet/column structure without creating chunks.

**Where**:
- Update: `src/documents/processor.py` (implement `_process_xlsx()` method)

**Depends on**: T3 (download stage implemented)

**Reuses**:
- `ExtractionService.extract_metadata()` for XLSX metadata extraction
- Document model's `meta` JSONB field for storing structure

**Done when**:
- [ ] `_process_xlsx()` extracts sheet names and column names using `ExtractionService`
- [ ] Validates that XLSX has at least one sheet
- [ ] Raises `ExtractionFailedError` for password-protected XLSX
- [ ] Raises `ExtractionFailedError` for empty XLSX (0 sheets)
- [ ] Saves metadata structure to `document.meta['xlsx_structure']`
- [ ] Updates document `status='ready'` without creating chunks
- [ ] Verifies no chunks exist for XLSX documents after processing
- [ ] Stage is logged with duration

**Tests**:
- Integration test: Full XLSX pipeline with mocked services
- Unit test: Password-protected XLSX raises `ExtractionFailedError`
- Unit test: Empty XLSX raises `ExtractionFailedError`
- Unit test: Verify chunks table is empty after XLSX processing

**Gate**:
```bash
pytest tests/unit/documents/test_processor_xlsx_pipeline.py -v
pytest tests/integration/test_document_processor_xlsx.py -v
```

**Requirement Traceability**:
- Implements: PROC-08 (download XLSX from storage)
- Implements: PROC-09 (extract sheet/column metadata)
- Implements: PROC-10 (save to meta['xlsx_structure'])
- Implements: PROC-11 (set status='ready')
- Implements: PROC-12 (verify no chunks created)

---

### T6: Add chunk upsert method to DocumentService

**What**: Add an `upsert_chunks()` method to `DocumentService` for idempotent chunk persistence using PostgreSQL upsert.

**Where**:
- Update: `src/documents/service.py`

**Depends on**: None (can be done in parallel with T2-T5)

**Reuses**:
- SQLAlchemy 2.0 async patterns
- PostgreSQL `insert().on_conflict_do_update()` syntax
- Existing `Chunk` model with unique constraint

**Done when**:
- [ ] `upsert_chunks()` method exists in `DocumentService`
- [ ] Method accepts list of chunk dictionaries
- [ ] Uses `insert(Chunk).on_conflict_do_update()` pattern
- [ ] Updates all chunk fields on conflict: content, embedding, section_hint, section_path, page_start, page_end, anchors, char_start, char_end
- [ ] Uses `index_elements=['document_id', 'chunk_index']` for conflict detection
- [ ] Method is async and uses provided database session
- [ ] Returns number of chunks upserted

**Tests**:
- Unit test: Insert new chunks
- Unit test: Update existing chunks (same document_id + chunk_index)
- Unit test: Mixed insert and update in single call
- Unit test: Verify all fields are updated on conflict

**Gate**:
```bash
pytest tests/unit/documents/test_service_upsert_chunks.py -v
```

**Requirement Traceability**:
- Implements: PROC-05 (idempotent chunk persistence)
- Implements: PROC-05 requirement for zero duplicate chunks

---

### T7: Integrate processor into router background task

**What**: Replace the TODO placeholder in the router with the actual processor call and background task integration.

**Where**:
- Update: `src/documents/router.py` (lines 149-151)
- May update: `src/documents/dependencies.py` (add ProcessorDep if needed)

**Depends on**: T2-T6 (processor and service methods ready)

**Reuses**:
- FastAPI `BackgroundTasks` for async processing
- `SessionFactory` for isolated database sessions
- All existing service initialization patterns

**Done when**:
- [ ] TODO at `src/documents/router.py:149-151` is removed
- [ ] `trigger_document_processing()` background task function exists
- [ ] Function initializes all required services (Storage, Extraction, Chunking, Embeddings)
- [ ] Function creates isolated DB session using `SessionFactory()`
- [ ] Function instantiates `DocumentProcessor` with all dependencies
- [ ] Function calls `processor.process(document_id, user_id)`
- [ ] Background task is added via `background_tasks.add_task()` in upload endpoint
- [ ] Upload endpoint returns 201 immediately (doesn't wait for processing)

**Tests**:
- Integration test: Upload endpoint returns 201 and triggers background task
- Unit test: Verify all services are initialized in background task
- Unit test: Verify processor is called with correct arguments

**Gate**:
```bash
pytest tests/unit/documents/test_router_background_task.py -v
pytest tests/integration/test_document_upload_flow.py -v
```

**Requirement Traceability**:
- Implements: PROC-01 (processor integrated)
- Implements: PROC-07 (cleanup and status update)

---

### T8: Write unit tests for DocumentProcessor

**What**: Create comprehensive unit tests for the DocumentProcessor covering all success and error paths.

**Where**:
- Create: `tests/unit/documents/test_processor.py`
- Create: `tests/unit/documents/test_exceptions.py`
- Create: `tests/unit/documents/test_service_upsert_chunks.py`
- Create: `tests/integration/test_document_processor.py`

**Depends on**: T1-T7 (implementation complete)

**Reuses**:
- Pytest async test patterns from existing codebase
- Mock factories for services
- Test fixtures from conftest.py

**Done when**:
- [ ] `test_exceptions.py` covers all exception classes
- [ ] `test_processor.py` covers:
  - [ ] Constructor injection
  - [ ] Document loading and status verification
  - [ ] Temp file download and cleanup
  - [ ] PDF/DOCX happy path
  - [ ] XLSX happy path
  - [ ] Empty document error (NoTextContentError)
  - [ ] Chunking failure error (ChunkingFailedError)
  - [ ] Embedding retry logic
  - [ ] Embedding failure after retry (EmbeddingGenerationError)
  - [ ] Database error handling (DatabaseError)
  - [ ] Storage error handling
  - [ ] Corrupted PDF error (ExtractionFailedError)
- [ ] `test_service_upsert_chunks.py` covers upsert logic
- [ ] `test_document_processor.py` (integration) covers end-to-end flow
- [ ] All tests pass with `pytest`
- [ ] Code coverage >80% for processor module

**Tests**:
- Run full test suite for document module

**Gate**:
```bash
pytest tests/unit/documents/ -v --cov=src.documents --cov-report=term-missing
pytest tests/integration/test_document_processor.py -v
```

**Requirement Traceability**:
- Verifies: All PROC requirements through testing

---

## Dependency Graph

```
T1 (Exceptions)
    ↓
T2 (Processor Class)
    ↓
    ├── T3 (Download) ──→ T4 (PDF/DOCX Pipeline)
    │                        ↓
    └── T3 (Download) ──→ T5 (XLSX Pipeline)

T6 (Upsert Method) ───────→ T4 (uses upsert)
     (parallel work)

T7 (Router Integration) ←─── T2, T3, T4, T5, T6

T8 (Tests) ←────────────── T1, T2, T3, T4, T5, T6, T7
```

---

## Parallel Execution Plan

**Phase 1 (Parallel)**:
- [P] T1: Create exception hierarchy
- [P] T6: Add chunk upsert method to DocumentService

**Phase 2 (Sequential from T1)**:
- T2: Create DocumentProcessor class
- T3: Implement download stage

**Phase 3 (Parallel from T3)**:
- [P] T4: Implement PDF/DOCX pipeline
- [P] T5: Implement XLSX pipeline

**Phase 4 (After T4, T5)**:
- T7: Integrate processor into router

**Phase 5 (Final)**:
- T8: Write comprehensive tests

---

## Requirement Traceability Matrix

| Requirement | Story | Task(s) | Status |
|-------------|-------|---------|--------|
| PROC-01 | P1 PDF/DOCX | T2, T3, T7 | In Tasks |
| PROC-02 | P1 PDF/DOCX | T4 | In Tasks |
| PROC-03 | P1 PDF/DOCX | T4 | In Tasks |
| PROC-04 | P1 PDF/DOCX | T4 | In Tasks |
| PROC-05 | P1 PDF/DOCX | T4, T6 | In Tasks |
| PROC-06 | P1 PDF/DOCX | T4 | In Tasks |
| PROC-07 | P1 PDF/DOCX | T3, T7 | In Tasks |
| PROC-08 | P2 XLSX | T5 | In Tasks |
| PROC-09 | P2 XLSX | T5 | In Tasks |
| PROC-10 | P2 XLSX | T5 | In Tasks |
| PROC-11 | P2 XLSX | T5 | In Tasks |
| PROC-12 | P2 XLSX | T5 | In Tasks |
| PROC-13 | P3 Error Handling | T1, T2, T3, T4, T5 | In Tasks |
| PROC-14 | P3 Error Handling | T1, T4 | In Tasks |
| PROC-15 | P3 Error Handling | T1, T4 | In Tasks |
| PROC-16 | P3 Error Handling | T1, T4 | In Tasks |
| PROC-17 | P3 Error Handling | T1, T3 | In Tasks |

---

## Success Criteria Verification

### MVP Verification Checklist

- [ ] **Criterion 1**: User uploads PDF → status `ready` in < 30 seconds (10-page document)
  - Test: Integration test with 10-page PDF
  - Gate: `pytest tests/integration/test_document_processor_pdf.py::test_pdf_10_pages -v`

- [ ] **Criterion 2**: User uploads XLSX → `documents.meta['xlsx_structure']` contains correct metadata
  - Test: Integration test with 3-sheet XLSX
  - Gate: `pytest tests/integration/test_document_processor_xlsx.py::test_xlsx_metadata_extraction -v`

- [ ] **Criterion 3**: Corrupted PDF fails gracefully with clear error message in `error_msg`
  - Test: Error handling test with corrupted file
  - Gate: `pytest tests/unit/documents/test_processor.py::test_corrupted_pdf_error -v`

- [ ] **Criterion 4**: Zero duplicate chunks per document (`UNIQUE(document_id, chunk_index)` enforced)
  - Test: Re-upload same document twice, verify no duplicates
  - Gate: `pytest tests/integration/test_document_processor_pdf.py::test_no_duplicate_chunks -v`

- [ ] **Criterion 5**: Temp files are always cleaned up (verify after 100 uploads)
  - Test: Stress test with cleanup verification
  - Gate: Manual verification + `pytest tests/unit/documents/test_processor.py::test_temp_cleanup -v`

---

## Notes

### Implementation Order Recommendation

1. Start with **T1** (exceptions) as it's foundational
2. **T6** can be done in parallel (independent service method)
3. Continue with **T2** → **T3** (processor foundation)
4. **T4** and **T5** can be done in parallel after T3
5. Finish with **T7** (router integration) and **T8** (tests)

### Risk Areas

- **Embeddings batching**: Ensure batch size of 100 is respected
- **Temp file cleanup**: Must use try/finally to guarantee cleanup
- **XLSX password protection**: Extractor may need update to handle this case
- **Chunk upsert**: Verify unique constraint exists in database schema

### Deferred Considerations

- OCR for scanned PDFs (out of scope per spec)
- Parallel processing within single document (out of scope per spec)
- Real-time progress notifications (out of scope per spec)
- Automatic retry mechanism (out of scope per spec)
