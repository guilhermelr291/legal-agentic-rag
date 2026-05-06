# Phase 2 — Document Ingestion Specification (Vector RAG + Graph RAG Ready)

## Problem Statement

The system must process legal documents (PDF, DOCX, XLSX) uploaded by users so they become queryable by the RAG agent. Without a reliable ingestion pipeline, the agent has no access to the user’s document knowledge.

**Why now:** Phase 1 (Supabase schema) is complete. Ingestion is a prerequisite for:

- Agent retrieval (Phase 3)
- Router decisions for redirecting to the XLSX tool (Phase 4)
- Evolving toward **Graph RAG** (entity/relation linking, multi-hop questions, and global synthesis).
  References:
- Microsoft GraphRAG docs: [https://microsoft.github.io/graphrag/](https://microsoft.github.io/graphrag/)
- GraphRAG local-to-global paper: [https://arxiv.org/abs/2404.16130](https://arxiv.org/abs/2404.16130)

---

## Goals

### Core (MVP — required)

- User can upload documents via Streamlit and track processing status
- System extracts text from PDF/DOCX (no OCR)
- System extracts structured metadata from XLSX (sheets, columns) for the XLSX tool and routing
- Documents are chunked using a legal-first, structure-preserving strategy (sections/clauses/articles) with overlap
- Chunks are embedded with OpenAI embeddings and persisted to Supabase with idempotent upsert
- On failure, document is marked as `failed` with an error message; user must re-upload to retry

### Graph RAG Ready (v1 — recommended, does not block MVP)

- Add an optional graph indexing track:
  - Extract minimal viable entities and relations per document
  - Persist nodes/edges with **evidence** pointing back to chunks

- Degrade gracefully: graph indexing failure does not prevent `ready` status for vector RAG

---

## Out of Scope (this phase)

| Feature                                           | Reason                                                                                     |
| ------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| OCR for scanned PDFs                              | MVP targets digital PDFs; OCR adds cost and complexity                                     |
| Table extraction as structured data from PDF/DOCX | Text-only extraction; XLSX is handled structurally via dedicated tool                      |
| Parallel processing of multiple files per worker  | BackgroundTasks processes one document at a time per worker; horizontal scaling is not MVP |
| Real-time status notifications                    | Streamlit polling is sufficient; SSE/WebSockets is later                                   |
| Document versioning                               | Re-upload creates a new record                                                             |
| Automatic retry / retry endpoint                  | User must re-upload failed documents                                                       |
| Full legal ontology in the graph                  | Start with a minimal schema; avoid over-modeling                                           |
| Perfect incremental graph updates                 | Re-upload regenerates graph for new `document_id`                                          |

---

## Definitions (operational)

### Document

A file uploaded by a user (PDF/DOCX/XLSX) with processing status and metadata.

### Chunk

A structure-preserving text unit with metadata and an embedding used for retrieval.

### Graph RAG (in this product)

An additional indexing layer that builds a **graph** from document text:

- **Node (Entity):** Party, Clause/Section, Obligation, Deadline/Date, Amount, Penalty, Definition, Reference
- **Edge (Relation):** OBLIGATES, HAS_DEADLINE, HAS_AMOUNT, HAS_PENALTY, DEFINES, REFERENCES, EXCEPTION_OF, etc.
- **Evidence:** pointers to text (chunk + page/offsets + short snippet).
  GraphRAG “local-to-global” concept reference: [https://arxiv.org/abs/2404.16130](https://arxiv.org/abs/2404.16130)

---

## User Stories

### P1: Document Upload ⭐ MVP

**User Story:** As a legal user, I want to upload my documents (PDF/DOCX/XLSX) so the agent can answer questions about them.

**Acceptance Criteria**

1. WHEN user selects a PDF/DOCX/XLSX in Streamlit THEN system SHALL validate allowed type and max size (50MB)
2. WHEN valid THEN system SHALL upload to Supabase Storage, create a record in `documents` with `status='processing'`, and return `document_id`
3. WHEN upload completes THEN system SHALL trigger a BackgroundTask for async processing
4. WHEN processing starts THEN system SHALL download the file from Storage
5. WHEN PDF/DOCX THEN system SHALL extract text and basic metadata (pages; heading hints if available)
6. WHEN text is extracted THEN system SHALL apply legal-first chunking with overlap
7. WHEN chunks are ready THEN system SHALL generate embeddings and upsert into `chunks`
8. WHEN embeddings are persisted THEN system SHALL update document `status='ready'`
9. WHEN an error occurs at any stage THEN system SHALL update `status='failed'`, save `error_msg`, and require re-upload to retry

**Independent Test**

- Upload a PDF via Streamlit → status transitions `processing → ready` → verify `chunks` contains records with embeddings for that `document_id`

---

### P2: XLSX Metadata Extraction ⭐ MVP

**User Story:** As a user, I want the system to recognize the structure of my Excel files (sheets and columns) for precise routing to the XLSX tool.

**Acceptance Criteria**

1. WHEN an XLSX file is uploaded THEN system SHALL extract sheet names and column names for each sheet
2. WHEN metadata is extracted THEN system SHALL save it into `documents.meta` (jsonb) before `status='ready'`
3. WHEN XLSX is processed THEN system SHALL skip text extraction/chunking/embeddings and go straight to `status='ready'` (XLSX tool reads directly from Storage)

**Independent Test**

- Upload an XLSX → verify `documents.meta` has correct sheets/columns → verify no `chunks` exist for that `document_id`

---

### P3: Status Tracking in UI ⭐ MVP

**User Story:** As a user, I want to see document status in Streamlit (processing/ready/failed).

**Acceptance Criteria**

1. WHEN user opens the documents page THEN system SHALL list documents with current status
2. WHEN a document has been processing for >2 minutes THEN system SHALL display “processing for X minutes”
3. WHEN a document is failed THEN system SHALL display an error icon and “Upload failed. Please try again.” (re-upload required)

---

### P4: Graph Indexing (Legal Graph) ⭐ v1 (recommended, feature-flagged)

**User Story:** As a legal user, I want the system to connect parties, obligations, deadlines, penalties, and references so it can answer multi-hop questions across the document.

**Acceptance Criteria**

1. WHEN PDF/DOCX ingestion completes (vector is ready) THEN system SHALL (optionally) run graph indexing asynchronously
2. Graph indexing SHALL create nodes for: Document, Section/Clause, Party, Obligation, Deadline/Date, Amount, Penalty, Definition, Reference
3. Graph indexing SHALL create edges with **at least one evidence pointer** containing:
   - `document_id`, `chunk_index`, `page` (if available), `start_char/end_char` (if available), `snippet`

4. WHEN graph indexing fails THEN system SHALL set `documents.meta.graph_status='failed'` and keep document `status='ready'`
5. Graph indexing SHALL be idempotent per `(document_id, graph_version)`

**Independent Test**

- Upload a contract containing “as per clause X / Annex Y” → verify `REFERENCES` edges exist with evidence pointing to the correct chunks

---

## Functional Requirements

### Validation & Upload

- Allowed extensions: `pdf`, `docx`, `xlsx`
- Max size: 50MB
- Storage path format: `{user_id}/{document_id}/{filename}`
- Create `documents` record first (`status='processing'`), then upload to Storage
  - If upload fails: delete partial file (if any), set `status='failed'`, return 500

### Processing Orchestration

- Each worker processes one document at a time
- Pipeline is re-entrant and idempotent by design (unique keys + upsert)
- Final vector readiness is independent from graph readiness

### Text Extraction

- PDF: LangChain `PyPDFLoader`
- DOCX: `python-docx` (or an equivalent loader)
- Minimal normalization:
  - collapse excessive line breaks
  - remove repeating headers/footers (simple heuristic)
  - preserve numbering and legal markers (clauses/articles)

### Chunking (Legal-First)

- Goal: preserve legal units and maintain traceability
- Each chunk SHALL persist:
  - `chunk_index` (sequential)
  - `section_hint` (e.g., “Clause 12”, “Article 5”, “SECTION II”)
  - `section_path` (hierarchy, if detected)
  - `page_start/page_end` (if available)
  - `anchors` (references detected, e.g., “Clause 10”, “Annex A”, “Article 20”)

### Embeddings & Persistence

- Embedding model: `text-embedding-3-small` (1536 dims)
- Batch size: 100 chunks per call
- Upsert: `INSERT ... ON CONFLICT (document_id, chunk_index) DO UPDATE`
- Guarantee zero duplicates per `(document_id, chunk_index)` via UNIQUE constraint

### Graph Indexing (v1)

- Optional and controlled by feature flag/config
- Graph storage can be:
  - Supabase Postgres tables (`graph_nodes`, `graph_edges`) **or**
  - External graph store (future)

- Must be scoped by `user_id` and `document_id`
- Must attach evidence to every persisted edge (otherwise drop the edge)
- Must not block `documents.status='ready'`

---

## Non-Functional Requirements

- Minimum observability:
  - log each stage: download, extract, chunk, embed, upsert, graph-index
  - record duration per stage

- Performance:
  - Vector RAG target: 10-page PDF reaches `ready` in < 30 seconds (best effort)
  - Graph indexing may complete after vector readiness

- Security:
  - strict `user_id` isolation for storage and DB queries
  - never expose data across users

- Cost controls:
  - embedding batching
  - graph indexing asynchronous + feature-flagged

---

## Edge Cases

### Validation & Upload

- Unsupported extension → 400 “Unsupported file type”
- File > 50MB → 413 “File too large (max 50MB)”
- Storage upload fails → delete partial file (if any) + 500

### Processing

- PDF parse failure → `failed`, `error_msg="Text extraction failed"`
- 0 chunks after chunking → `failed`, `error_msg="Document contains no extractable text"`
- Embeddings API failure → retry once with 2s backoff; if still fails → `failed`
- Re-upload after failure → create a new `documents` record (no reuse)

### Concurrency & Timeouts

- Worker restarts during processing → document remains `processing`; user must re-upload (no automatic recovery)
- Multiple simultaneous uploads for the same user → process independently

### Graph RAG Specific

- Graph extraction yields no nodes/edges but text chunks exist → `documents.meta.graph_status='ready_empty'`
- Relation without evidence → drop relation (do not persist)
- Graph indexing exceeds time threshold (e.g., 60s) → `graph_status='timeout'` (vector remains ready)

---

## Requirement Traceability

| Requirement ID | Story             | Phase  | Status         |
| -------------- | ----------------- | ------ | -------------- |
| INGEST-01      | P1 Upload         | Tasks  | **In Tasks**   |
| INGEST-02      | P1 Upload         | Tasks  | **In Tasks**   |
| INGEST-03      | P1 Upload         | Tasks  | **In Tasks**   |
| INGEST-04      | P1 Upload         | Tasks  | **In Tasks**   |
| INGEST-05      | P1 Upload         | Tasks  | **In Tasks**   |
| INGEST-06      | P1 Upload         | Tasks  | **In Tasks**   |
| INGEST-07      | P1 Upload         | Tasks  | **In Tasks**   |
| INGEST-08      | P2 XLSX Meta      | Tasks  | **In Tasks**   |
| INGEST-09      | P2 XLSX Meta      | Tasks  | **In Tasks**   |
| INGEST-10      | P2 XLSX Meta      | Tasks  | **In Tasks**   |
| INGEST-11      | P3 UI Status      | Tasks  | **In Tasks**   |
| INGEST-12      | P3 UI Status      | Tasks  | **In Tasks**   |
| INGEST-13      | P3 UI Status      | Tasks  | **In Tasks**   |
| INGEST-14      | P4 Graph Indexing | Tasks  | **In Tasks**   |
| INGEST-15      | P4 Graph Indexing | Tasks  | **In Tasks**   |
| INGEST-16      | P4 Graph Indexing | Tasks  | **In Tasks**   |

**ID format:** `INGEST-[NUMBER]`
**Status values:** Pending → In Design → In Tasks → Implementing → Verified

---

## Success Criteria

### Vector RAG (MVP)

- User uploads a 10-page PDF and sees `status='ready'` in < 30 seconds (best effort)
- Zero duplicate chunks per document (`UNIQUE(document_id, chunk_index)` works)
- XLSX metadata is correct in 100% of tested cases
- Corrupted/invalid PDFs fail gracefully with clear error message
- User can re-upload after failure and a new document record is created successfully

### Graph RAG Ready (v1)

- `documents.meta.graph_status` is present with values: `ready`, `failed`, `timeout`, `ready_empty`
- All persisted relations have evidence attached
- Graph data is isolated by `user_id` and `document_id`

---

## Technical Notes

### Dependencies

```txt
langchain-community>=0.4.1  # PyPDFLoader
openpyxl>=3.1.5
python-docx>=1.1.0
sqlalchemy>=2.0
pgvector
```

> Graph RAG storage and libraries remain a design decision:

- Supabase Postgres tables for graph (`graph_nodes`, `graph_edges`) **or**
- External graph store (e.g., Neo4j) later

### PDF Text Extraction (PyPDFLoader)

```python
from langchain_community.document_loaders import PyPDFLoader

loader = PyPDFLoader(file_path)
pages = loader.load()
```

### Chunking Strategy (Legal-First)

1. Detect headings/titles (regex/heuristics), English-oriented markers only:
   - `^(?:\d+\.\s*|Article\s+\d+|Art\.\s*\d+|Clause\s+\d+|SECTION|CHAPTER|TITLE)`

2. Create chunks by section, keeping the heading as a prefix
3. If chunk > 800 tokens: split by paragraph
4. If chunk < 100 tokens: merge with the next chunk
5. Overlap: 50 tokens from the previous chunk
6. `section_hint` = detected heading
7. `section_path` = detected hierarchy (if available)
8. `anchors` = detected references (Clause X / Article Y / Annex Z)

### Embeddings

- Model: `text-embedding-3-small`
- Batch: 100
- Upsert: `INSERT ... ON CONFLICT (document_id, chunk_index) DO UPDATE`

### Storage Paths

```
{user_id}/{document_id}/{filename}
a1b2c3d4/550e8400-e29b-41d4-a716-446655440000/contract.pdf
```

---

## Graph RAG (v1) — Strategy Placeholder (to be refined during study)

### v1 Goals

- Connect obvious, high-value legal structures (Parties, Clauses, References, Obligations, Deadlines, Penalties)
- Require evidence for every edge
- Avoid deep ontology until real question patterns are known

### Recommended incremental approach

1. **Heuristics first (cheap):**

- Detect anchors/references → create `REFERENCES` edges and `Clause/Reference` nodes

2. **LLM only where it adds value (controlled):**

- Extract parties and roles
- Extract obligation/deadline/penalty tuples when explicit
- Return evidence (snippet + chunk_index) for each extracted relation

3. **Summaries (optional, later):**

- Section summaries or “community summaries” for global questions
  Reference: [https://arxiv.org/abs/2404.16130](https://arxiv.org/abs/2404.16130)

---

## References

- Microsoft GraphRAG docs: [https://microsoft.github.io/graphrag/](https://microsoft.github.io/graphrag/)
- GraphRAG local-to-global paper: [https://arxiv.org/abs/2404.16130](https://arxiv.org/abs/2404.16130)
- LangChain Graph RAG retriever: [https://docs.langchain.com/oss/python/integrations/retrievers/graph_rag](https://docs.langchain.com/oss/python/integrations/retrievers/graph_rag)
- Neo4j GraphRAG contracts example: [https://github.com/neo4j-product-examples/graphrag-contract-review](https://github.com/neo4j-product-examples/graphrag-contract-review)
- Phase 1 (Supabase Schema): `to-do-list.md:59-230`
- Project Context: `to-do-list.md:1-58`
- Architecture: `.specs/codebase/ARCHITECTURE.md`
- Stack: `.specs/codebase/STACK.md`
