# Testing Infrastructure

**Analyzed:** 2026-05-06

## Current state

| Item | Status |
|------|--------|
| `tests/` directory | **Absent** |
| `pytest` in `pyproject.toml` | **Not declared** in `[project]` or `dev` group at analysis time |
| CI workflow (e.g. GitHub Actions) | Not verified in this pass — add path if present |

## Intended stack (recommended)

| Layer | Tool | Notes |
|-------|------|-------|
| Unit / integration | pytest + pytest-asyncio | Async routes and SQLAlchemy async need asyncio mode |
| HTTP | httpx `AsyncClient` + `ASGITransport` | Per workspace standards; target `src.main.app` |
| Overrides | FastAPI `app.dependency_overrides` | Prefer over monkeypatching DB internals |

## Test organization (proposed)

```text
tests/
├── conftest.py
├── unit/
│   ├── test_retrievers_rrf.py
│   └── test_storage_service.py   # mock Supabase client
└── integration/
    ├── test_health.py
    ├── test_documents_upload.py  # test DB + mocked storage
    └── test_agents_query.py      # mock graph or registry
```

## Test coverage matrix

| Code layer | Test type | Location pattern | Run command |
|------------|-----------|------------------|-------------|
| FastAPI routers (`src/*/router.py`) | Integration (ASGI) | `tests/integration/test_*.py` | `pytest tests/integration` *(once added)* |
| LangGraph nodes | Unit (mocked LLM/registry) | `tests/unit/test_nodes_*.py` | `pytest tests/unit` |
| Retrieval / RRF | Unit (pure logic + fake docs) | `tests/unit/test_rrf.py` | `pytest tests/unit` |
| Storage service | Unit (mock HTTP/client) | `tests/unit/test_storage.py` | `pytest tests/unit` |
| SQLAlchemy models / migrations | Integration (real DB or testcontainers) | `tests/integration/test_db_*.py` | *(TBD)* |

Layers with **no tests today** — treat as **high risk** for regressions; see `CONCERNS.md`.

## Parallelism assessment

| Test type | Parallel-safe? | Notes |
|-----------|----------------|--------|
| Future integration with shared `DATABASE_URL` | **Risky** without isolation | Use transactional rollbacks, per-test schema, or Testcontainers |
| Unit tests with mocked I/O | **Yes** | No shared mutable global state |

## Gate check commands

| Gate | When | Command |
|------|------|---------|
| Lint | After any Python change | `uv run ruff check src` and `uv run ruff format src` *(or `python -m ruff`)* |
| Quick | After adding tests | `pytest -q` *(once pytest is configured)* |
| Full | Pre-release | Lint + tests + manual smoke against local API |

*Extract exact commands from your Task runner / CI once added; do not assume `uv` is on PATH in all environments.*

## Known testing debt

1. No automated regression suite for document upload pipeline.
2. No tests for LangGraph branching (`router_node`, `should_continue`, web search fallback).
3. No contract tests for Supabase Storage error mapping (`StorageError`).
4. RAG quality (RAGAS) mentioned in README/plans — not wired in repo as executable tests.
