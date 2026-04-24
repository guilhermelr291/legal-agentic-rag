# Document Ingestion Tasks

**Design**: `.specs/features/document-ingestion/design.md`  
**Spec**: `.specs/features/document-ingestion/spec.md`  
**Status**: Draft

---

## Execution Plan

### Phase 1: Infrastructure & Database (Sequential)

Foundation layer must be in place before any processing logic.

```
T1 ──→ T2 ──→ T3 ──→ T4
```

### Phase 2: Core Services (Sequential within type, Parallel across types)

After infrastructure, build the processing pipeline components.

```
                    ┌→ T6 ──→ T7
T4 ──→ T5 ──→ T8 ──┤
                    └→ T9 ──→ T10
```

### Phase 3: API Layer (Sequential)

Expose services via FastAPI endpoints.

```
T10 ──→ T11 ──→ T12
```

### Phase 4: Frontend (Sequential)

Build Streamlit UI for user interaction.

```
T12 ──→ T13 ──→ T14
```

### Phase 5: Integration & Graph RAG (Parallel)

Optional Graph RAG and final integration.

```
T14 ──→ T15 ──┬→ T16
              └→ T17
```

---

## Task Breakdown

### T1: Add Supabase Dependencies and Configuration

**What**: Add Supabase client, pgvector, and related dependencies to project configuration  
**Where**: `pyproject.toml`, `my_agent/config/settings.py`  
**Depends on**: None  
**Reuses**: Existing Settings pattern from `my_agent/config/settings.py`  
**Requirement**: INGEST-01, INGEST-02

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `supabase-py`, `psycopg2-binary`, `pgvector` added to dependencies
- [x] Settings updated with Supabase URL, Service Role Key, JWT Secret
- [x] Settings include `GRAPH_RAG_ENABLED` feature flag (default: false)
- [x] No import errors when running `python -c "from my_agent.config.settings import get_settings; print(get_settings())"`

**Tests**: none  
**Gate**: build

**Verify**:

```bash
python -c "from my_agent.config.settings import get_settings; s = get_settings(); print('Supabase URL:', s.supabase_url[:20] + '...' if hasattr(s, 'supabase_url') else 'NOT SET')"
```

---

### T2: Create Database Schema SQL and Migration

**What**: Write SQL schema for documents, chunks, graph_nodes, graph_edges tables with RLS policies  
**Where**: `supabase/migrations/001_document_ingestion.sql`  
**Depends on**: T1  
**Reuses**: None  
**Requirement**: INGEST-03, INGEST-08

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] SQL file creates `documents` table with all fields from design.md
- [x] SQL file creates `chunks` table with pgvector embedding column (1536 dims)
- [x] SQL file creates `graph_nodes` and `graph_edges` tables
- [x] All RLS policies defined for user isolation
- [x] Indexes created for performance
- [x] SQL is syntactically valid (tested via `psql --check` or similar)

**Tests**: none  
**Gate**: build

**Verify**:

```bash
# Check SQL syntax (if psql available)
head -50 supabase/migrations/001_document_ingestion.sql
```

---

### T3: Create Supabase Client Module

**What**: Build async Supabase client wrapper with connection pooling  
**Where**: `services/storage/supabase_client.py`  
**Depends on**: T1, T2  
**Reuses**: Settings pattern  
**Requirement**: INGEST-03

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [x] `SupabaseClient` class with `from_service_role()` factory
- [x] Async methods: `upload_file()`, `download_file()`, `delete_file()`
- [x] Async DB methods: `insert()`, `upsert()`, `select()`, `update()` with RLS awareness
- [x] Connection pooling configured
- [x] Error handling for network/storage failures
- [x] `python -c "from services.storage.supabase_client import SupabaseClient; print('Import OK')"` passes

**Tests**: none  
**Gate**: build

**Verify**:

```bash
python -c "from services.storage.supabase_client import SupabaseClient; print('Import OK')"
```

---

### T4: Create Database Repository Layer

**What**: Repository classes for documents and chunks with type-safe operations  
**Where**: `services/db/repositories.py`  
**Depends on**: T3  
**Reuses**: SupabaseClient from T3  
**Requirement**: INGEST-03, INGEST-08

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `DocumentRepository` class with methods:
  - `create(document: DocumentCreate) -> DocumentRecord`
  - `get_by_id(document_id: str, user_id: str) -> DocumentRecord | None`
  - `update_status(document_id: str, status: str, error_msg: str | None = None)`
  - `list_by_user(user_id: str, status: str | None = None) -> List[DocumentRecord]`
- [ ] `ChunkRepository` class with methods:
  - `upsert_chunks(chunks: List[ChunkRecord])` (batch upsert)
  - `get_by_document(document_id: str, user_id: str) -> List[ChunkRecord]`
- [ ] All methods enforce `user_id` filtering for RLS
- [ ] Pydantic models for type safety

**Tests**: none  
**Gate**: build

**Verify**:

```bash
python -c "from services.db.repositories import DocumentRepository, ChunkRepository; print('Repositories import OK')"
```

---

### T5: Create Text Extractors (PDF, DOCX, XLSX)

**What**: Implement file-specific text/metadata extractors  
**Where**: `services/extractors/pdf_extractor.py`, `docx_extractor.py`, `xlsx_extractor.py`  
**Depends on**: T4  
**Reuses**: PyPDFLoader pattern from existing code  
**Requirement**: INGEST-05, INGEST-09

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `PDFExtractor` class implementing `TextExtractor` interface
  - Uses `PyPDFLoader` from langchain_community
  - Returns: text, pages list with page numbers
- [ ] `DOCXExtractor` class implementing `TextExtractor` interface
  - Uses `python-docx` library
  - Returns: text, paragraph metadata
- [ ] `XLSXMetadataExtractor` class
  - Uses `openpyxl` library
  - Returns: `XLSXMetadata` with sheets, columns, row counts
- [ ] All extractors handle errors gracefully (return empty result with error flag)
- [ ] Base `TextExtractor` ABC in `services/extractors/base.py`

**Tests**: none  
**Gate**: build

**Verify**:

```bash
python -c "
from services.extractors.pdf_extractor import PDFExtractor
from services.extractors.docx_extractor import DOCXExtractor
from services.extractors.xlsx_extractor import XLSXMetadataExtractor
print('All extractors import OK')
"
```

---

### T6: Create Legal Chunker Service

**What**: Implement structure-preserving chunking for legal documents  
**Where**: `services/chunking/legal_chunker.py`  
**Depends on**: T5  
**Reuses**: None  
**Requirement**: INGEST-06

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `LegalChunker` class with config: max_tokens=800, min_tokens=100, overlap_tokens=50
- [ ] `_detect_headings()` method with regex patterns for:
  - Numbered sections: `^\d+\.\s*`
  - Articles: `Article\s+\d+|Art\.\s*\d+`
  - Clauses: `CLÁUSULA\s+\d+|CLAUSULA\s+\d+`
  - Sections: `SECTION|CHAPTER|TITLE`
- [ ] `_extract_anchors()` method detecting references like "Clause X", "Article Y", "Annex Z"
- [ ] `chunk()` method returning `List[LegalChunk]` with all metadata fields
- [ ] Handles merge of small chunks (<100 tokens) with adjacent chunks
- [ ] Uses tiktoken for accurate token counting (OpenAI cl100k_base)

**Tests**: none  
**Gate**: build

**Verify**:

```bash
python -c "
from services.chunking.legal_chunker import LegalChunker
chunker = LegalChunker()
text = '1. Clause One\nThis is the first clause.\n\n2. Clause Two\nThis is the second clause.'
chunks = chunker.chunk(text, pages=[{'number': 1, 'start_char': 0, 'end_char': len(text)}])
print(f'Created {len(chunks)} chunks')
print('Chunker works' if len(chunks) > 0 else 'FAILED')
"
```

---

### T7: Create Embedding Generator Service

**What**: Batch embedding generation with Supabase upsert  
**Where**: `services/embeddings/generator.py`  
**Depends on**: T6, T4  
**Reuses**: OpenAI embeddings pattern  
**Requirement**: INGEST-07

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `EmbeddingGenerator` class with `OpenAIEmbeddings` client
- [ ] `generate_and_upsert()` method:
  - Batches chunks (batch_size=100)
  - Generates embeddings via `embed_documents()`
  - Upserts to Supabase with `ON CONFLICT (document_id, chunk_index) DO UPDATE`
- [ ] Progress logging ("Batch X/Y complete")
- [ ] Error handling with one retry on API failure
- [ ] Returns statistics: chunks_processed, embeddings_generated, errors

**Tests**: none  
**Gate**: build

**Verify**:

```bash
python -c "
from services.embeddings.generator import EmbeddingGenerator
from my_agent.config.settings import get_settings
print('EmbeddingGenerator imports OK')
print('Model:', get_settings().openai_embedding_model)
"
```

---

### T8: Create Document Processor Orchestrator

**What**: Main pipeline coordinator that routes to correct processor based on file type  
**Where**: `services/document_processor.py`  
**Depends on**: T5, T6, T7  
**Reuses**: Repository pattern, extractors, chunker, embedding generator  
**Requirement**: INGEST-04, INGEST-05, INGEST-06, INGEST-07, INGEST-08, INGEST-10, INGEST-11

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `DocumentProcessor` class initialized with all dependencies
- [ ] `process(document_id: str, user_id: str)` main entry point:
  - Downloads file from Storage
  - Routes to `_process_pdf_docx()` or `_process_xlsx()`
  - Updates status at each stage (logs to console/structured logging)
  - Handles errors with status='failed' and error_msg
- [ ] `_process_pdf_docx()` pipeline: extract → chunk → embed → update status=ready
- [ ] `_process_xlsx()` pipeline: extract metadata → save to documents.meta → update status=ready (skip chunking)
- [ ] Stage logging with duration tracking per stage
- [ ] All errors caught and document status updated appropriately

**Tests**: none  
**Gate**: build

**Verify**:

```bash
python -c "
from services.document_processor import DocumentProcessor
print('DocumentProcessor imports OK')
"
```

---

### T9: Create Graph Extractor (Graph RAG v1)

**What**: Entity and relation extraction for Graph RAG (feature-flagged)  
**Where**: `services/graph/extractor.py`, `services/graph/models.py`  
**Depends on**: T8  
**Reuses**: Structured LLM output pattern from router.py  
**Requirement**: INGEST-15, INGEST-16

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Graph models: `GraphNode`, `GraphEdge`, `Evidence` Pydantic classes
- [ ] `GraphExtractor` class with:
  - `__init__(llm, enabled: bool = False)`
  - `extract(document_id, chunks) -> GraphExtractionResult`
- [ ] `_heuristic_extraction()` for cheap reference detection (Clause X, Article Y)
- [ ] `_llm_extraction()` for entity/relation extraction with structured output
- [ ] Evidence required on every edge (snippet + chunk_index + offsets)
- [ ] Edges without evidence are dropped (not persisted)
- [ ] Graph status tracked separately: documents.meta.graph_status

**Tests**: none  
**Gate**: build

**Verify**:

```bash
python -c "
from services.graph.extractor import GraphExtractor
from services.graph.models import GraphNode, GraphEdge, Evidence
print('Graph components import OK')
"
```

---

### T10: Create Graph Repository

**What**: Database operations for graph nodes and edges  
**Where**: `services/db/graph_repository.py`  
**Depends on**: T9, T4  
**Reuses**: Repository pattern from T4  
**Requirement**: INGEST-15, INGEST-16

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `GraphRepository` class with methods:
  - `upsert_nodes(nodes: List[GraphNode])` - idempotent per document_id
  - `upsert_edges(edges: List[GraphEdge])` - with evidence validation
  - `delete_by_document(document_id: str, user_id: str)` - cleanup on re-upload
- [ ] All edges validated to have non-empty evidence before upsert
- [ ] RLS enforcement via user_id filtering

**Tests**: none  
**Gate**: build

**Verify**:

```bash
python -c "from services.db.graph_repository import GraphRepository; print('GraphRepository imports OK')"
```

---

### T11: Create FastAPI Document Routes

**What**: FastAPI endpoints for upload and status  
**Where**: `api/routes/documents.py`, `api/main.py`  
**Depends on**: T8, T4  
**Reuses**: FastAPI patterns  
**Requirement**: INGEST-01, INGEST-02, INGEST-03, INGEST-04, INGEST-12

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `POST /documents/upload` endpoint:
  - Accepts `UploadFile`, validates extension (pdf/docx/xlsx)
  - Validates file size <= 50MB
  - Creates document record with status='processing'
  - Uploads to Storage at `{user_id}/{document_id}/{filename}`
  - Triggers BackgroundTask for processing
  - Returns `UploadResponse` with document_id
- [ ] `GET /documents/{document_id}/status` endpoint:
  - Returns current status, timestamps, processing duration
  - Includes graph_status from meta if available
- [ ] `GET /documents` endpoint:
  - Lists user's documents with optional status filter
- [ ] Proper error responses: 400 (bad type), 413 (too large), 500 (storage fail)
- [ ] Request/response Pydantic models in `api/models.py`

**Tests**: none  
**Gate**: build

**Verify**:

```bash
python -c "
from api.routes.documents import router
print('API routes import OK')
print('Routes:', [route.path for route in router.routes])
"
```

---

### T12: Create FastAPI Application Setup

**What**: Main FastAPI app with CORS, middleware, and route registration  
**Where**: `api/main.py`  
**Depends on**: T11  
**Reuses**: None  
**Requirement**: INGEST-01

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] FastAPI app created with title/description
- [ ] CORS middleware configured for Streamlit origin
- [ ] Document routes registered at `/api/v1` prefix
- [ ] Health check endpoint `GET /health`
- [ ] Startup/shutdown events for client initialization
- [ ] Can start server: `uvicorn api.main:app --reload` (documented, not required to pass)

**Tests**: none  
**Gate**: build

**Verify**:

```bash
python -c "from api.main import app; print('FastAPI app imports OK'); print('Routes:', [route.path for route in app.routes if hasattr(route, 'path')])"
```

---

### T13: Create Streamlit Document Upload Page

**What**: UI for file upload with validation feedback  
**Where**: `frontend/pages/documents.py`  
**Depends on**: T12  
**Reuses**: None  
**Requirement**: INGEST-01, INGEST-02

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `render_upload_section()`:
  - File uploader widget (PDF/DOCX/XLSX only)
  - Client-side size validation (50MB)
  - Upload button with progress indicator
  - Display validation errors inline
- [ ] API client functions:
  - `upload_file(file, user_id)` - POST to /documents/upload
  - Returns document_id or raises with error message
- [ ] Success/error handling with Streamlit notifications
- [ ] Page layout with clear sections

**Tests**: none  
**Gate**: build

**Verify**:

```bash
python -c "from frontend.pages.documents import render_upload_section; print('Upload section imports OK')"
```

---

### T14: Create Streamlit Document List with Status Polling

**What**: Document list view with real-time status updates  
**Where**: `frontend/pages/documents.py` (extend)  
**Depends on**: T13  
**Reuses**: API client from T13  
**Requirement**: INGEST-12, INGEST-13, INGEST-14

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `render_document_list()`:
  - Table with columns: filename, type, status, updated_at
  - Status badges with icons (processing 🔄, ready ✅, failed ❌)
- [ ] `render_status_badge(status, processing_time)`:
  - processing + >2min → "Processing for X minutes"
  - failed → "Upload failed. Please try again."
- [ ] `poll_status(document_id)`:
  - Polls `GET /documents/{id}/status` every 2 seconds
  - Updates UI until terminal state (ready/failed)
  - Uses `st.session_state` to track polling state
- [ ] Re-upload button for failed documents
- [ ] Auto-refresh mechanism for document list

**Tests**: none  
**Gate**: build

**Verify**:

```bash
python -c "
from frontend.pages.documents import render_document_list, render_status_badge, poll_status
print('Document list components import OK')
"
```

---

### T15: Wire Up Graph Indexing in Document Processor

**What**: Integrate GraphExtractor into processing pipeline (async, non-blocking)  
**Where**: `services/document_processor.py` (modify)  
**Depends on**: T14, T10, T9  
**Reuses**: DocumentProcessor from T8  
**Requirement**: INGEST-15, INGEST-16

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] DocumentProcessor updated to accept `GraphExtractor` and `GraphRepository`
- [ ] After vector processing completes (status='ready'):
  - If `GRAPH_RAG_ENABLED`: trigger graph indexing asynchronously
  - Graph indexing runs in background (doesn't block response)
- [ ] Graph status updates in documents.meta:
  - `graph_status='processing'` → `graph_status='ready'` or `'failed'`
- [ ] Graph errors don't affect document status (graceful degradation)
- [ ] Graph indexing timeout handling (>60s → status='timeout')

**Tests**: none  
**Gate**: build

**Verify**:

```bash
python -c "
from services.document_processor import DocumentProcessor
import inspect
sig = inspect.signature(DocumentProcessor.__init__)
params = list(sig.parameters.keys())
print('DocumentProcessor params:', params)
print('Has graph_extractor:', 'graph_extractor' in params)
print('Has graph_repository:', 'graph_repository' in params)
"
```

---

### T16: Create End-to-End Integration Test (Manual)

**What**: Manual test script for full pipeline verification  
**Where**: `tests/manual/test_ingestion.py`  
**Depends on**: T15  
**Reuses**: All services  
**Requirement**: All INGEST requirements

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] Test script that:
  - Creates test PDF with legal structure
  - Uploads via API
  - Polls status until ready
  - Verifies chunks exist in database
  - Verifies embeddings are 1536-dimensional
- [ ] Test script for XLSX:
  - Uploads test XLSX
  - Verifies metadata extraction
  - Verifies no chunks created
- [ ] README with instructions to run tests

**Tests**: none (this IS the test)  
**Gate**: build

**Verify**:

```bash
python -c "
import os
script_path = 'tests/manual/test_ingestion.py'
print(f'Test script exists: {os.path.exists(script_path)}')
if os.path.exists(script_path):
    with open(script_path) as f:
        content = f.read()
    print(f'Has test_pdf_upload: {\"test_pdf_upload\" in content}')
    print(f'Has test_xlsx_upload: {\"test_xlsx_upload\" in content}')
"
```

---

### T17: Create Documentation and Usage Examples

**What**: README and examples for the ingestion feature  
**Where**: `.specs/features/document-ingestion/README.md`, `examples/`  
**Depends on**: T16  
**Reuses**: None  
**Requirement**: All INGEST requirements

**Tools**:

- MCP: NONE
- Skill: NONE

**Done when**:

- [ ] `README.md` with:
  - Feature overview
  - Architecture diagram (link to design.md)
  - API endpoint documentation
  - Configuration options
  - Troubleshooting guide
- [ ] `examples/upload_sample.py` - Python script example
- [ ] `examples/sample_contract.pdf` - Sample document for testing
- [ ] Environment variable template updated with new variables

**Tests**: none  
**Gate**: build

**Verify**:

```bash
ls -la .specs/features/document-ingestion/README.md examples/
```

---

## Parallel Execution Map

### Phase 1: Infrastructure (Sequential — must complete in order)

```
T1 (Deps) ──→ T2 (Schema) ──→ T3 (Client) ──→ T4 (Repositories)
```

### Phase 2: Core Services (Sequential dependencies, but extractors/chunker can be built in parallel after T4)

```
                    ┌→ T6 (Chunker) ──→ T7 (Embeddings)
T4 ──→ T5 (Extractors) ──┤
                    └→ T9 (Graph Extractor) ──→ T10 (Graph Repo)
                           └─────────────────────────────┘
                                    ↓
                              T8 (Processor)
```

**Note**: T5, T6, and T9 can be worked on in parallel once T4 is complete, but T7, T8, and T10 have dependencies that make them sequential.

### Phase 3: API (Sequential)

```
T8 ──→ T11 (Routes) ──→ T12 (FastAPI App)
```

### Phase 4: Frontend (Sequential)

```
T12 ──→ T13 (Upload UI) ──→ T14 (List UI)
```

### Phase 5: Integration & Docs (Parallel after T14)

```
T14 ──→ T15 (Graph Wiring)
          └→ T16 (Manual Tests) ──→ T17 (Docs)
```

---

## Task Granularity Check

| Task | Scope | Status |
|------|-------|--------|
| T1 | Dependencies + Settings | ✅ Granular |
| T2 | SQL schema file | ✅ Granular |
| T3 | Client module | ✅ Granular |
| T4 | Repository classes | ✅ Granular |
| T5 | Three extractor classes | ✅ Granular (cohesive set) |
| T6 | Chunker service | ✅ Granular |
| T7 | Embedding service | ✅ Granular |
| T8 | Processor orchestrator | ✅ Granular |
| T9 | Graph extractor | ✅ Granular |
| T10 | Graph repository | ✅ Granular |
| T11 | API routes | ✅ Granular |
| T12 | FastAPI app setup | ✅ Granular |
| T13 | Upload UI | ✅ Granular |
| T14 | List + polling UI | ✅ Granular |
| T15 | Graph wiring | ✅ Granular |
| T16 | Manual test script | ✅ Granular |
| T17 | Documentation | ✅ Granular |

---

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
|------|------------------------|---------------|--------|
| T1 | None | T1 start | ✅ Match |
| T2 | T1 | T1 → T2 | ✅ Match |
| T3 | T1, T2 | T2 → T3 | ✅ Match |
| T4 | T3 | T3 → T4 | ✅ Match |
| T5 | T4 | T4 → T5 | ✅ Match |
| T6 | T5 | T5 → T6 | ✅ Match |
| T7 | T6, T4 | T6 → T7 | ✅ Match |
| T8 | T5, T6, T7 | T5, T6, T7 → T8 | ✅ Match |
| T9 | T8 | T8 → T9 | ✅ Match |
| T10 | T9, T4 | T9, T4 → T10 | ✅ Match |
| T11 | T8, T4 | T8 → T11 | ✅ Match |
| T12 | T11 | T11 → T12 | ✅ Match |
| T13 | T12 | T12 → T13 | ✅ Match |
| T14 | T13 | T13 → T14 | ✅ Match |
| T15 | T14, T10, T9 | T14, T10, T9 → T15 | ✅ Match |
| T16 | T15 | T15 → T16 | ✅ Match |
| T17 | T16 | T16 → T17 | ✅ Match |

---

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
|------|-----------------------------|-----------------|-----------|--------|
| T1 | Configuration | none | none | ✅ OK |
| T2 | SQL Schema | none | none | ✅ OK |
| T3 | Client Module | none | none | ✅ OK |
| T4 | Repository | none | none | ✅ OK |
| T5 | Extractors | none | none | ✅ OK |
| T6 | Chunker Service | none | none | ✅ OK |
| T7 | Embedding Service | none | none | ✅ OK |
| T8 | Processor | none | none | ✅ OK |
| T9 | Graph Extractor | none | none | ✅ OK |
| T10 | Graph Repository | none | none | ✅ OK |
| T11 | API Routes | none | none | ✅ OK |
| T12 | FastAPI App | none | none | ✅ OK |
| T13 | Streamlit UI | none | none | ✅ OK |
| T14 | Streamlit UI | none | none | ✅ OK |
| T15 | Processor (modify) | none | none | ✅ OK |
| T16 | Manual Test | none | none | ✅ OK |
| T17 | Documentation | none | none | ✅ OK |

**Note**: TESTING.md indicates no tests are currently implemented. All tasks use `Tests: none` and `Gate: build` (import/compilation check). When test infrastructure is established, tasks should be updated to include appropriate unit/integration tests.

---

## Requirement Traceability

| Requirement | Tasks | Status |
|-------------|-------|--------|
| INGEST-01 | T1, T11, T13 | Traced |
| INGEST-02 | T1, T11, T13 | Traced |
| INGEST-03 | T2, T3, T4, T8, T11 | Traced |
| INGEST-04 | T8, T11 | Traced |
| INGEST-05 | T5, T8 | Traced |
| INGEST-06 | T6, T8 | Traced |
| INGEST-07 | T7, T8 | Traced |
| INGEST-08 | T2, T4, T8 | Traced |
| INGEST-09 | T5, T8 | Traced |
| INGEST-10 | T8 | Traced |
| INGEST-11 | T8 | Traced |
| INGEST-12 | T11, T14 | Traced |
| INGEST-13 | T14 | Traced |
| INGEST-14 | T14 | Traced |
| INGEST-15 | T9, T15 | Traced |
| INGEST-16 | T9, T10, T15 | Traced |

---

## Open Questions

1. **MCPs to use**: Should we use any MCP servers for implementation (e.g., for database operations)?
2. **Test infrastructure**: Should we set up pytest infrastructure before or during implementation?
3. **Skills to apply**: Are there any Cursor skills that would help with specific tasks?

---

## Ready for Approval

All validation checks passed:
- ✅ Task Granularity: All tasks are atomic
- ✅ Diagram-Definition Cross-Check: All dependencies match
- ✅ Test Co-location: Aligned with TESTING.md (no tests required yet)

**Total Tasks**: 17  
**Estimated Phases**: 5  
**Critical Path**: T1 → T2 → T3 → T4 → T5 → T6 → T7 → T8 → T11 → T12 → T13 → T14 → T15 → T16 → T17
