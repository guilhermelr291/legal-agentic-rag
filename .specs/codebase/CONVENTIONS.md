# Code Conventions

**Source of truth:** `.cursor/rules/agentic-rag-standards.mdc` (FastAPI, Pydantic v2, SQLAlchemy async, `Annotated` dependencies, PyJWT, httpx testing).

This document reflects **what the repo does today**, not an ideal state.

## Naming

| Element | Convention | Examples from repo |
|---------|------------|-------------------|
| Packages / dirs | `snake_case` | `src/agents/nodes/` |
| Modules | `snake_case` | `query_generation.py`, `documents/router.py` |
| Classes | `PascalCase` | `GraphState`, `StorageService`, `DocumentService` |
| Functions | `snake_case` | `multi_query_generation_node`, `create_graph` |
| Constants | `UPPER_SNAKE` | `ALLOWED_EXTENSIONS`, `STORAGE_BUCKET` in routers |

## Imports

Observed pattern: **stdlib → third-party → `src.*`**, grouped logically.

```python
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from src.common.database import DbDep
from src.documents.service import DocumentService
```

Cross-domain imports use **explicit module paths** (`from src.agents import ...`), consistent with workspace standards.

## FastAPI

- Prefer **`Annotated[T, Depends(...)]`** for injectables (e.g. `DbDep`, `StorageDep`, domain-specific deps in `dependencies.py`).
- Routers use **`APIRouter`** with `prefix` and `tags`; app mounts under **`/api/v1`** in `src/main.py`.

## Configuration

- **Shared app settings:** `src/common/config.py` — `CommonConfig` with `SettingsConfigDict(env_prefix="APP_", env_file=".env")`.
- **Domain settings:** e.g. `src/documents/config.py`, `src/agents/config.py`, `src/storage/config.py` — separate `BaseSettings` subclasses with their own prefixes where used.

Do **not** assume a single global `get_settings()` for all domains; use the appropriate config module.

## Agent / LangGraph nodes

- Nodes take **`GraphState`** (or compatible dict) and return **partial state updates** (e.g. `{"documents": ...}`).
- LLM routing / grading uses **Pydantic `BaseModel` + `with_structured_output`** (e.g. `RouteQuery` in `src/agents/nodes/router.py`).
- Dependencies: access LLM / retriever / reranker via **`src/agents/registry.py`**, not ad-hoc client construction inside nodes (keeps tests and wiring consistent).

## Persistence

- Use **SQLAlchemy 2.0 async** (`AsyncSession`, `async_sessionmaker`) via `src/common/database.py`.
- Shared metadata naming convention is defined on `metadata` in `database.py`.

## Error handling

- Domain and HTTP layers raise or map to **`src/common/exceptions.py`** types (`NotFoundError`, `ValidationError`, `StorageError`, etc.); `main.py` registers handlers for `BaseAppException`.
- Avoid bare `except Exception` in business logic; **`main.py`** still has a generic handler for truly unexpected errors (log + 500 JSON).

## Language / comments

- **English only** for docstrings, comments, specs, and user-facing API messages unless an external spec mandates otherwise.

## Lint / format

- **Ruff** targeting Python 3.12, line length 100 — see `pyproject.toml`.
