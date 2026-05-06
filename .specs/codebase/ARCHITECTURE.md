# Architecture

**Pattern:** Modular monolith — single FastAPI app + optional Streamlit frontend, domain packages under `src/`.

**Analyzed:** 2026-05-06

## High-level structure

```text
Client (Streamlit / HTTP) → FastAPI (`src/main.py`)
    ├── /api/v1/documents → documents domain (DB + storage + pipeline)
    └── /api/v1/agents   → LangGraph RAG (`create_graph()`)

Shared: SQLAlchemy async (`src/common/database.py`), domain-specific settings, exception types.
```

## LangGraph RAG flow

Defined in `src/agents/graph.py`:

1. **START** → `router_node` (structured LLM route: `vectorstore` | `web_search`).
2. **vectorstore** → `generate_queries` → `retrieve` → `grade_docs` → if no docs → `web_search`, else `generate` → **END**.
3. **web_search** (from start or fallback) → `generate` → **END**.

Router implementation (`src/agents/nodes/router.py`) returns a `Literal` for `add_conditional_edges` (no separate `MessagesState`; graph state is `GraphState` in `src/agents/state.py`).

## Identified patterns

### Domain-oriented packages

**Location:** `src/{agents,documents,storage,...}/`  
**Purpose:** Boundaries by feature; each area can expose `router.py`, `service.py`, `config.py`, `dependencies.py` where needed.  
**Example:** `src/documents/router.py` uses `Annotated[..., Depends(...)]` for `DbDep`, `StorageDep`, `UserIdDep`.

### ContextVar registry for agent dependencies

**Location:** `src/agents/registry.py`  
**Purpose:** `get_llm()` / `get_retriever()` / `get_reranker()` without wiring globals in every node; supports tests by swapping setters.  
**Example:** Lifespan in `src/main.py` calls `init_default_llm()`.

### Hybrid retrieval and fusion

**Location:** `src/agents/retrievers/ensemble.py`, `src/agents/retrievers/rrf.py`  
**Purpose:** Ensemble dense + lexical weights; Reciprocal Rank Fusion across multi-query results.  
**Optional rerank:** `src/agents/rerankers/cohere.py` with degradation if no API key.

### Async Supabase storage service

**Location:** `src/storage/service.py`  
**Purpose:** Encapsulate `supabase` async client + bucket operations; map failures to `StorageError`.

### SQLAlchemy 2.0 async for application data

**Location:** `src/common/database.py`, `src/documents/models.py`  
**Purpose:** Document metadata and processing state in Postgres (URL from `APP_DATABASE_URL` / `DATABASE_URL` in `CommonConfig`).

## Document ingestion (high level)

Upload API stores files via Supabase Storage and records metadata in the DB; background tasks drive extraction → chunking → embedding and vector persistence (details in `src/documents/service.py` and related packages). *Exact vector store wiring should be read from implementation when changing retrieval.*

## Data flow: RAG query

1. HTTP `POST /api/v1/agents/query` builds initial `GraphState` (messages + optional overrides per `src/agents/router.py`).
2. Compiled graph runs nodes; retrieval uses registry-provided retriever; optional Cohere rerank.
3. Response mapped to Pydantic `QueryResponse` with answer and sources.

## Code organization

| Approach | Description |
|----------|-------------|
| **Layout** | Domain folders under `src/`, not a single `my_agent` package |
| **API** | Versioned prefix `/api/v1` in `main.py` |
| **Config** | Split settings per domain + `src/common/config.py` for shared app/env |

## Historical note

Older internal docs referenced `my_agent/` and Chroma as primary vector store; the current codebase uses the layout above and Postgres/pgvector direction per README. Update feature specs when migration work completes.
