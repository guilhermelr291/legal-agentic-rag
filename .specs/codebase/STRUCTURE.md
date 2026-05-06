# Project Structure

**Root:** `Agentic RAG/` (workspace)

## Directory tree (representative)

```
Agentic RAG/
├── .cursor/rules/          # IDE standards (e.g. agentic-rag-standards.mdc)
├── .specs/
│   ├── codebase/           # Brownfield docs (this folder)
│   ├── project/            # PROJECT.md, ROADMAP.md, STATE.md (if present)
│   └── features/           # Feature specs (e.g. document-ingestion, refactor-to-standards)
├── frontend/               # Streamlit pages
│   └── pages/
│       └── documents.py
├── src/                    # Main Python package (setuptools: packages under src/)
│   ├── main.py             # FastAPI factory + `app` instance
│   ├── common/             # Shared config, DB, models, exceptions
│   ├── agents/             # LangGraph RAG: graph, nodes, retrievers, rerankers, router API
│   ├── documents/        # Document upload, processing, DB models, FastAPI router
│   ├── storage/            # Supabase Storage service + FastAPI deps
│   ├── embeddings/       # Embedding service + config
│   ├── chunking/         # Chunking service + config
│   ├── extractors/       # PDF/DOCX/XLSX extraction
│   └── graph/            # Package placeholder / future graph RAG
├── pyproject.toml
├── requirements.txt        # Legacy; see STACK.md
└── README.md
```

## Module organization

### `src/common/`

**Purpose:** Cross-cutting concerns.  
**Key files:** `config.py` (`CommonConfig`, `DATABASE_URL`, `APP_*`), `database.py` (async engine, `get_db`, `DbDep`), `exceptions.py`, `models.py`.

### `src/agents/`

**Purpose:** LangGraph RAG agent and HTTP surface for queries.  
**Key files:** `graph.py` (`create_graph`), `state.py` (`GraphState`), `registry.py` (ContextVar DI for LLM/retriever/reranker), `router.py` (FastAPI `/api/v1/agents/*`), `config.py`, `nodes/*`, `retrievers/*`, `rerankers/*`.

### `src/documents/`

**Purpose:** Document lifecycle: upload, background processing, status, listing, delete.  
**Key files:** `router.py` (`/api/v1/documents/*`), `service.py`, `models.py`, `schemas.py`, `dependencies.py`, `config.py`.

### `src/storage/`

**Purpose:** Supabase Storage (async client, upload/download/delete, public URL).  
**Key files:** `service.py`, `config.py`, `dependencies.py`.

### `src/embeddings/`, `src/chunking/`, `src/extractors/`

**Purpose:** Ingestion pipeline pieces: embed text, chunk content, extract per file type.  
**Key files:** `service.py` and `config.py` in each; extractors include `pdf.py`, `docx.py`, `xlsx.py`.

### `frontend/`

**Purpose:** Streamlit UI entry points / pages (e.g. document flows).

## Where things live

| Capability | API / UI | Business logic | Persistence / external |
|------------|----------|----------------|-------------------------|
| RAG query | `src/agents/router.py` | `src/agents/graph.py`, `src/agents/nodes/*` | OpenAI, Tavily, retriever backend (registry) |
| Document upload & status | `src/documents/router.py` | `src/documents/service.py` | SQLAlchemy models + Supabase Storage via `src/storage/` |
| App shell | `src/main.py` | lifespan, CORS, exception handlers | — |
| DB sessions | — | — | `src/common/database.py` |

## Special directories

| Path | Purpose |
|------|---------|
| `.specs/features/` | Spec-driven feature work (spec/design/tasks) |
| `src/graph/` | Reserved / future graph-RAG related code |
