# Codebase Concerns

**Analysis date:** 2026-05-06

## Tech debt

**Dual dependency manifests**

- **Issue:** `requirements.txt` pins older `langchain` / `langgraph` / Chroma stacks that conflict with modern `pyproject.toml` (LangChain 1.x / LangGraph 1.x).
- **Files:** `requirements.txt`, `pyproject.toml`
- **Impact:** Install docs or tooling that use `requirements.txt` can create broken or duplicate environments.
- **Fix:** Single source of truth — drop legacy file or regenerate it from `pyproject.toml` / `uv lock`; update README install steps once.

**Supabase settings split across domains**

- **Issue:** `AgentsConfig` and `StorageConfig` both carry Supabase-related fields with different env prefixes (`AGENTS_*` vs `STORAGE_*`).
- **Files:** `src/agents/config.py`, `src/storage/config.py`
- **Impact:** Misconfigured `.env` (populating only one prefix) causes confusing partial failures between upload and agent features.
- **Fix:** Document required vars per deploy path, or consolidate Supabase URL/keys into one domain config re-exported elsewhere.

**Retriever factories stub**

- **Issue:** `create_chroma_retriever` raises `NotImplementedError`; ensemble is the active path.
- **Files:** `src/agents/retrievers/factories.py`
- **Impact:** Confusing API surface; copy-paste integrations may hit dead ends.
- **Fix:** Implement with real store wiring or remove/export only working factories; document the supported retriever setup in README.

## Security considerations

**Secrets in environment**

- **Risk:** `STORAGE_SUPABASE_SERVICE_KEY`, `AGENTS_SUPABASE_SERVICE_ROLE_KEY` (if used), OpenAI keys (`AGENTS_*`, `EMBEDDINGS_*`), and `APP_DATABASE_URL` grant broad access if leaked.
- **Files:** `src/storage/config.py`, `src/agents/config.py`, `src/embeddings/config.py`, `src/common/config.py`, deployment `.env`
- **Current mitigation:** Keys loaded via settings, not committed (verify `.gitignore` for `.env`).
- **Recommendations:** Never expose service role to Streamlit client; use short-lived user JWT + RLS patterns as auth matures; rotate keys if `.env` was ever committed.

**Broad exception on startup**

- **Risk:** LLM init failures in lifespan are swallowed with a warning — app may run in a degraded state without clear failure mode for operators.
- **Files:** `src/main.py` (`init_default_llm` in `lifespan`)
- **Recommendations:** Fail fast in production when agent routes are required, or expose health/readiness that reflects LLM initialization.

## Fragile areas

**Registry globals**

- **Files:** `src/agents/registry.py`, all `src/agents/nodes/*`
- **Why fragile:** Missing `set_retriever` / `set_llm` before invoking the graph causes `RuntimeError` at runtime, not at import.
- **Safe modification:** Always wire registry in lifespan, tests, or scripts before `create_graph().invoke(...)`.
- **Test coverage:** None today (`TESTING.md`).

**Supabase client import compatibility**

- **Files:** `src/storage/service.py` (`try/except` between `supabase` submodules)
- **Why fragile:** Library layout changes across `supabase-py` versions can break imports.
- **Safe modification:** Pin `supabase` major/minor in `pyproject.toml`; add a smoke test that constructs `StorageService`.

## Performance / scaling (not measured)

- **Issue:** No p95 metrics captured in this audit for retrieval, embedding batch jobs, or upload pipeline.
- **Improvement path:** Add timing logs around `DocumentService` background work and agent `retrieve`; watch DB pool size and Supabase rate limits.

## Dependencies at risk

**`requirements.txt` drift**

- **Risk:** Developers install conflicting stacks.
- **Migration:** Standardize on `uv sync` / `pyproject.toml` only.

## Test coverage gaps

- **What’s missing:** Entire `src/` tree lacks an automated test suite (`tests/` absent; pytest not in project deps at analysis).
- **Risk:** Regressions in document ingestion, storage errors, and LangGraph routing go undetected.
- **Priority:** High for `documents/router.py` + `storage/service.py` + `agents/graph.py` paths.
- **Difficulty:** Medium — requires httpx ASGI tests + mocked OpenAI/Supabase.

---

_Updated as part of brownfield mapping. Remove or rewrite items when resolved._
