# Tech Stack

**Analyzed:** 2026-05-06

## Core

| Component | Technology | Notes |
|-----------|------------|--------|
| Language | Python | `>=3.12` (`pyproject.toml`) |
| Package manager | uv | Described in README; `pyproject.toml` is source of truth |
| Project name | `adaptive-rag` | `pyproject.toml` `[project].name` |

## Backend

| Component | Technology | Purpose |
|-----------|------------|---------|
| API | FastAPI `>=0.115` | REST API under `/api/v1`, lifespan, CORS for Streamlit |
| Settings | Pydantic v2 + `pydantic-settings` `>=2.4` | Per-domain `BaseSettings` (e.g. `APP_*`, domain prefixes) |
| Database access | SQLAlchemy `>=2.0` async + `asyncpg` | `AsyncSession`, `postgresql+asyncpg://` URL |
| Migrations | Alembic `>=1.13` | Listed in `pyproject.toml`; **no `alembic/` tree** in repo at analysis — migrations may be pending |

## Agent / RAG

| Component | Technology | Purpose |
|-----------|------------|---------|
| Orchestration | LangGraph `>=1.1.6` | RAG graph: route → multi-query → retrieve → grade → generate / web search |
| LLM toolkit | LangChain `>=1.2.15` + `langchain-openai`, `langchain-community`, `langchain-tavily` | Chains, tools, Tavily |
| Embeddings / chunking | `langchain-text-splitters`, OpenAI embeddings | Document pipeline (see `src/embeddings`, `src/chunking`) |

## Document processing

| Format | Library |
|--------|---------|
| PDF | `pypdf`, LangChain loaders |
| DOCX | `python-docx` |
| XLSX | `openpyxl` |

## Frontend

| Component | Technology |
|-----------|------------|
| UI | Streamlit `>=1.40` (`frontend/`) |

## Storage & integrations

| Component | Technology |
|-----------|------------|
| Object storage | Supabase Storage (`supabase` Python client, async) — `src/storage/` |
| Vectors | `pgvector` client dependency; vectors used with Postgres/Supabase per README |

## HTTP / auth libs (standards alignment)

| Library | Version | Notes |
|---------|---------|--------|
| httpx | `>=0.27` | Async HTTP |
| PyJWT | `>=2.9` | JWT validation (when auth is wired) |

## Development tools

| Tool | Purpose |
|------|---------|
| ruff `>=0.6` | Lint + format (`[dependency-groups] dev`) |

## Legacy / duplicate manifest

- **`requirements.txt`** still lists older LangChain/LangGraph/Chroma versions and **does not match** `pyproject.toml`. Treat **`pyproject.toml` as authoritative** for the current app; reconcile or remove `requirements.txt` to avoid confusion.

## Testing

- **pytest** is not declared in `pyproject.toml` at time of analysis; **no `tests/` tree** present. See `TESTING.md`.
