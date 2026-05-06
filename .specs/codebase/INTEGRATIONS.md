# External Integrations

**Analyzed:** 2026-05-06

## OpenAI

**Purpose:** Chat models (routing, multi-query, grading, generation), embeddings for ingestion.

**Implementation:** `src/agents/registry.py`, `src/agents/nodes/*`, `src/embeddings/service.py` (and related config).

**Configuration:**
- Agent LLM: `AGENTS_OPENAI_API_KEY`, `AGENTS_OPENAI_LIGHTWEIGHT_MODEL`, `AGENTS_OPENAI_MODEL_GENERATION`, `AGENTS_OPENAI_EMBEDDING_MODEL` — `src/agents/config.py`.
- Ingestion embeddings: `EMBEDDINGS_OPENAI_API_KEY`, `EMBEDDINGS_EMBEDDING_MODEL`, etc. — `src/embeddings/config.py`.

**Authentication:** API key from environment; never hard-coded.

## Tavily (web search)

**Purpose:** Web search path when routing selects `web_search` or when graded documents are empty.

**Implementation:** `langchain-tavily` — `src/agents/nodes/web_search.py`.

**Configuration:** `src/agents/config.py` — env vars use prefix `AGENTS_` (e.g. `AGENTS_TAVILY_API_KEY`, `AGENTS_TAVILY_MAX_RESULTS`).

**Degradation:** Optional; vector-only flows work if Tavily is not configured (routing may still send traffic to web search — verify behavior when key missing).

## Cohere (reranking)

**Purpose:** Rerank fused documents after retrieval.

**Implementation:** `src/agents/rerankers/cohere.py`; used from `src/agents/nodes/retrieval.py` with try/except / optional registry.

**Configuration:** `AGENTS_COHERE_API_KEY`, `AGENTS_COHERE_RERANK_MODEL`, `AGENTS_RERANK_TOP_K` (`src/agents/config.py`).

**Degradation:** **Yes** — retrieval can proceed without reranker.

## Supabase

**Purpose:**

- **Storage:** User uploads, bucket operations — `src/storage/service.py`, `src/storage/config.py`.
- **Backend data:** Project direction is Postgres + pgvector via Supabase; app DB URL also supplied through `CommonConfig.DATABASE_URL` (async Postgres).

**Configuration (storage domain):** `STORAGE_SUPABASE_URL`, `STORAGE_SUPABASE_SERVICE_KEY`, optional `STORAGE_SUPABASE_STORAGE_BUCKET` — `src/storage/config.py`.

**Authentication:** Service role key for server-side Storage client (must not ship to frontend). Agents config also defines `AGENTS_SUPABASE_*` for non-storage Supabase use — confirm which module owns each concern when debugging env issues.

**Python client:** `supabase` package with async client (imports guarded for version differences in `storage/service.py`).

## Postgres (SQLAlchemy)

**Purpose:** Document metadata, processing status, and related application tables.

**Implementation:** `src/common/database.py`, ORM models e.g. `src/documents/models.py`.

**Configuration:** Field `DATABASE_URL` on `CommonConfig` with `env_prefix="APP_"` → env var **`APP_DATABASE_URL`** (`src/common/config.py`).

## Planned / documentation-only

| Item | Status |
|------|--------|
| LangSmith tracing | Named in README / plans — enable via LangChain env when adopted |
| RAGAS | Evaluation — not integrated as runnable tests in repo |

## Integration health summary

| Integration | Required? | Graceful without? |
|-------------|-----------|-------------------|
| OpenAI | Yes for agent + embeddings | No for full RAG |
| Supabase Storage | Yes for upload API as implemented | Upload flows fail without credentials |
| Postgres | Yes for document DB features | API paths using `DbDep` need DB |
| Tavily | No | Partial (avoid web path or handle errors) |
| Cohere | No | Yes |
