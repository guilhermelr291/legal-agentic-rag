# Specification: Refactor to FastAPI Standards

## Problem Statement

The project currently follows a structure organized by file type (`api/`, `services/`, `my_agent/`) that works, but does not follow FastAPI best practices for projects at scale. Maintaining and evolving the code is becoming harder as the project grows.

Identified issues:
- Structure not organized by domain (bounded contexts)
- Use of legacy `Depends()` (default-arg form) instead of `Annotated[T, Depends(...)]`
- Configuration centralized in a single file instead of `BaseSettings` per domain
- Possibly non-explicit imports across domains
- Lack of naming conventions for SQLAlchemy
- Import structure does not follow the pattern `from src.auth import service as auth_service`

## Goals

- [ ] Reorganize the project into a domain structure (`src/{domain}/`)
- [ ] Modernize dependency injection to `Annotated[T, Depends(...)]`
- [ ] Implement `BaseSettings` per domain
- [ ] Apply SQLAlchemy naming conventions
- [ ] Ensure correct async/await usage across routes
- [ ] Standardize cross-domain imports
- [ ] Maintain 100% functional compatibility (no behavior changes)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Technology changes (switching FastAPI, database, etc.) | Structural refactor only |
| Adding new features | Scope limited to reorganization |
| Changing business logic | Behavior must stay identical |
| Performance optimization | Focus on structure, not performance |
| API documentation beyond FastAPI defaults | Rely on automatic OpenAPI |

---

## User Stories

### P1: Restructure by Domain (Bounded Contexts) ⭐ MVP

**User Story**: As a developer, I want code organized by business domain to simplify maintenance and onboarding.

**Why P1**: The current structure mixes responsibilities. Splitting by domain (documents, agents, storage, embeddings, etc.) makes the codebase more cohesive.

**Acceptance Criteria**:

1. WHEN the project is restructured THEN each domain SHALL have its own folder under `src/{domain}/`
2. WHEN a domain is created THEN it SHALL contain: `router.py`, `schemas.py`, `service.py`, `dependencies.py`, `config.py`, `constants.py`, `exceptions.py`
3. WHEN domains are defined THEN they SHALL be: `documents`, `agents`, `storage`, `embeddings`, `chunking`, `extractors`, `graph`, `common` (shared)
4. WHEN there is shared code THEN it SHALL live in `src/common/` (database, global config, base models)
5. WHEN the project runs after refactoring THEN all endpoints SHALL behave identically to the previous version

**Independent Test**: Run the application and verify `/health`, `/api/v1/documents/*` work; verify documents can be uploaded and processed.

---

### P1: Modern FastAPI Dependencies ⭐ MVP

**User Story**: As a developer, I want modern dependency injection to avoid bugs with default values.

**Why P1**: The pattern `def func(dep = Depends(x))` is legacy and has issues with default values. `Annotated[T, Depends(x)]` is the modern FastAPI 0.95+ idiom.

**Acceptance Criteria**:

1. WHEN dependency injection is used THEN it SHALL use `Annotated[T, Depends(...)]`
2. WHEN dependency aliases exist THEN they SHALL follow `PostDep = Annotated[dict, Depends(valid_post_id)]`
3. WHEN a route needs a dependency THEN there SHALL be no `= Depends(...)` as a default argument
4. WHEN all routes are updated THEN no route SHALL use the legacy form

**Independent Test**: Verify all routes in `src/documents/router.py` use `Annotated`; verify `ruff` does not report legacy patterns.

---

### P1: BaseSettings per Domain ⭐ MVP

**User Story**: As a developer, I want each domain to have isolated settings for better cohesion.

**Why P1**: A single huge global configuration violates single responsibility. Each domain should manage only its own variables.

**Acceptance Criteria**:

1. WHEN a domain needs configuration THEN it SHALL have its own `config.py` with `BaseSettings`
2. WHEN there is a domain-specific variable THEN it SHALL live in that domain’s `BaseSettings`
3. WHEN there is global configuration THEN it SHALL live in `src/common/config.py`
4. WHEN configs are accessed THEN the pattern SHALL be `{domain}_settings = {Domain}Config()`
5. WHEN environment variables are loaded THEN they SHALL respect per-domain `env_prefix` (e.g. `DOCUMENTS_`, `AGENTS_`, `STORAGE_`)

**Independent Test**: Each config can be instantiated in isolation; env vars with correct prefixes are read.

---

### P1: SQLAlchemy Conventions and Naming ⭐ MVP

**User Story**: As a developer, I want clear database naming conventions for easier maintenance.

**Why P1**: Inconsistent names make manual queries and schema understanding harder.

**Acceptance Criteria**:

1. WHEN tables are created THEN they SHALL use `lower_case_snake` and singular names (e.g. `document`, `chunk`)
2. WHEN there are FKs THEN they SHALL use consistent names (e.g. `document_id` everywhere)
3. WHEN there are timestamps THEN they SHALL use the `_at` suffix (e.g. `created_at`, `updated_at`)
4. WHEN there are dates (no time component) THEN they SHALL use the `_date` suffix
5. WHEN SQLAlchemy metadata is configured THEN it SHALL use `POSTGRES_INDEXES_NAMING_CONVENTION`
6. WHEN indexes are created THEN they SHALL follow: `ix: %(column_0_label)s_idx`, `uq: %(table_name)s_%(column_0_name)s_key`

**Independent Test**: Verify generated schema naming is consistent; indexes follow the convention.

---

### P2: Correct Async Patterns

**User Story**: As a developer, I want async code not to block the event loop.

**Why P2**: Async code with blocking calls (`time.sleep`, `requests.get`, etc.) inside `async def` freezes the entire event loop.

**Acceptance Criteria**:

1. WHEN a route performs non-blocking I/O THEN it SHALL use `async def` + `await`
2. WHEN a route performs blocking I/O (no async client) THEN it SHALL use `def` (sync, runs in threadpool)
3. WHEN there is mixed I/O THEN the route SHALL use `async def` + `run_in_threadpool` for the blocking part
4. WHEN there is no I/O (light CPU only) THEN the route may use `def` or `async def`
5. WHEN a sync call runs inside async THEN it SHALL use `await run_in_threadpool(fn, *args)`

**Independent Test**: Application keeps similar throughput; no blocking calls inside `async def`.

---

### P2: Cross-Domain Import Standardization

**User Story**: As a developer, I want explicit cross-domain imports to avoid circular dependencies.

**Why P2**: Deep-path imports (`from src.auth.service.user import ...`) create tight coupling. The project pattern is to import whole modules.

**Acceptance Criteria**:

1. WHEN importing from another domain THEN the import SHALL be `from src.{domain} import service as {domain}_service`
2. WHEN importing constants from another domain THEN the import SHALL be `from src.{domain} import constants as {domain}_constants`
3. WHEN importing schemas from another domain THEN the import SHALL be `from src.{domain} import schemas as {domain}_schemas`
4. WHEN there is a wildcard import (`*`) THEN it SHALL be removed (except deliberate `__init__.py` exports)
5. WHEN there is an absolute import of a specific file THEN it SHALL be converted to a module import

**Independent Test**: No imports like `from src.x.y.z import specific_func`; all use module aliases.

---

### P3: Pydantic v2 Modernization

**User Story**: As a developer, I want modern Pydantic v2 patterns to avoid deprecations.

**Why P3**: `json_encoders` is deprecated in Pydantic v2. `@field_serializer` is the modern approach.

**Acceptance Criteria**:

1. WHEN there is `model_config = ConfigDict(json_encoders=...)` THEN it SHALL be converted to `@field_serializer`
2. WHEN there is custom datetime serialization THEN it SHALL use `@field_serializer` with `when_used="json"`
3. WHEN there is `Field(ge=18, default=None)` THEN it SHALL be fixed (constraint vs default contradiction)
4. WHEN all schemas are checked THEN none SHALL use deprecated Pydantic v1 APIs

**Independent Test**: Pydantic emits no deprecation warnings; `ruff` reports no Pydantic issues.

---

## Edge Cases

- WHEN a file fits no clear domain THEN it SHALL go to `src/common/`
- WHEN there is dead code (imported by nothing) during refactoring THEN it SHALL be documented and removed if confirmed
- WHEN two domains share the same model THEN the model SHALL go to `src/common/schemas.py` or `src/common/models.py`
- WHEN a dependency has a complex chain THEN the chain SHALL be preserved with chained `Annotated`
- WHEN a domain has multiple sub-components (e.g. agents with nodes, retrievers, rerankers) THEN they SHALL be subfolders of the domain

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----------- | ------ | ------ |
| REFAC-01 | P1: Restructure by Domain | Design | Pending |
| REFAC-02 | P1: Restructure by Domain | Design | Pending |
| REFAC-03 | P1: Restructure by Domain | Design | Pending |
| REFAC-04 | P1: Restructure by Domain | Design | Pending |
| REFAC-05 | P1: Restructure by Domain | Design | Pending |
| REFAC-06 | P1: Modern Dependencies | Design | Pending |
| REFAC-07 | P1: Modern Dependencies | Design | Pending |
| REFAC-08 | P1: Modern Dependencies | Design | Pending |
| REFAC-09 | P1: Modern Dependencies | Design | Pending |
| REFAC-10 | P1: BaseSettings per Domain | Design | Pending |
| REFAC-11 | P1: BaseSettings per Domain | Design | Pending |
| REFAC-12 | P1: BaseSettings per Domain | Design | Pending |
| REFAC-13 | P1: BaseSettings per Domain | Design | Pending |
| REFAC-14 | P1: BaseSettings per Domain | Design | Pending |
| REFAC-15 | P1: SQLAlchemy Conventions | Design | Pending |
| REFAC-16 | P1: SQLAlchemy Conventions | Design | Pending |
| REFAC-17 | P1: SQLAlchemy Conventions | Design | Pending |
| REFAC-18 | P1: SQLAlchemy Conventions | Design | Pending |
| REFAC-19 | P1: SQLAlchemy Conventions | Design | Pending |
| REFAC-20 | P1: SQLAlchemy Conventions | Design | Pending |
| REFAC-21 | P2: Async Patterns | Design | Pending |
| REFAC-22 | P2: Async Patterns | Design | Pending |
| REFAC-23 | P2: Async Patterns | Design | Pending |
| REFAC-24 | P2: Async Patterns | Design | Pending |
| REFAC-25 | P2: Async Patterns | Design | Pending |
| REFAC-26 | P2: Import Standardization | Design | Pending |
| REFAC-27 | P2: Import Standardization | Design | Pending |
| REFAC-28 | P2: Import Standardization | Design | Pending |
| REFAC-29 | P2: Import Standardization | Design | Pending |
| REFAC-30 | P2: Import Standardization | Design | Pending |
| REFAC-31 | P3: Pydantic Modernization | Design | Pending |
| REFAC-32 | P3: Pydantic Modernization | Design | Pending |
| REFAC-33 | P3: Pydantic Modernization | Design | Pending |
| REFAC-34 | P3: Pydantic Modernization | Design | Pending |

**Coverage:** 34 total, 0 mapped to tasks, 34 unmapped

---

## Success Criteria

- [ ] Application starts without errors with the new structure
- [ ] All documented endpoints respond identically
- [ ] Document upload works end-to-end
- [ ] Document processing (chunking, embeddings) works
- [ ] RAG agent queries return equivalent results
- [ ] `ruff check src` passes with no errors
- [ ] No Pydantic deprecation warnings
- [ ] Tests (if any) pass
