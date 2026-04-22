# Architecture Overview

## System Context

This is an **Adaptive RAG (Retrieval-Augmented Generation)** system built with LangGraph. It dynamically routes queries between vectorstore retrieval and web search, with document grading and reranking.

## High-Level Flow

```
┌─────────┐     ┌─────────────┐     ┌──────────────────┐
│  START  │────▶│ router_node  │────▶│ generate_queries │
└─────────┘     └─────────────┘     └──────────────────┘
                            │                  │
                            ▼                  ▼
                    ┌──────────────┐    ┌───────────┐
                    │  web_search  │    │  retrieve  │
                    └──────────────┘    └───────────┘
                            │                  │
                            └────────┬─────────┘
                                     ▼
                            ┌───────────────┐
                            │  grade_docs   │───No docs?──▶ web_search
                            └───────────────┘
                                     │
                                     ▼
                            ┌───────────────┐
                            │   generate    │
                            └───────────────┘
                                     │
                                     ▼
                                   [END]
```

## Core Components

### 1. State Management (`state.py`)

```python
class GraphState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    documents: List[str]
    generation: str
    queries_for_retrieval: List[str]
```

**Note:** Current state is minimal. The to-do list indicates a planned expansion:
- `route`: Routing decision
- `user_id`, `thread_id`: Session tracking
- `doc_ids`: Document scope
- `citations`: Source tracking
- `chat_history`: Conversation memory
- `trace_id`: Observability

### 2. Registry Pattern (`registry.py`)

Uses Python `ContextVar` for dependency injection:

- `get_llm()` / `set_llm()` - LLM access
- `get_retriever()` / `set_retriever()` - Retriever access
- `get_reranker()` / `set_reranker()` - Optional reranker

**Purpose:** Avoid direct instantiation in nodes; enable testing and configuration flexibility.

### 3. Graph Nodes

| Node | File | Purpose | Async |
|------|------|---------|-------|
| `router_node` | `nodes/router.py` | Routes to vectorstore or web_search | No |
| `multi_query_generation_node` | `nodes/query_generation.py` | Generates 5 sub-queries for retrieval | No |
| `retrieval_node` | `nodes/retrieval.py` | Hybrid retrieval + RRF + rerank | Yes |
| `documents_grader_node` | `nodes/grading.py` | Filters irrelevant documents | Yes |
| `generate_answer_node` | `nodes/generation.py` | Produces final answer | No |
| `web_search_node` | `nodes/web_search.py` | Tavily web search fallback | No |

### 4. Retriever System

**Base Class:** `retrievers/base.py`
- Abstract `Retriever` with `retrieve()` and `batch_retrieve()` methods

**Implementations:**
- `EnsembleRetriever` - LangChain ensemble with configurable weights (0.7 dense / 0.3 BM25 default)
- Factory functions for Chroma and BM25

**Fusion:** `retrievers/rrf.py`
- Reciprocal Rank Fusion (RRF) for merging multi-query results
- Constant c=60 for smoothing

### 5. Reranking (Optional)

**Base Class:** `rerankers/base.py`
- Abstract `Reranker` with sync/async methods

**Implementation:** `rerankers/cohere.py`
- Cohere Rerank API (model: rerank-v3.5)
- Graceful degradation if not configured

## Data Flow

1. **Input:** User question via `messages` in state
2. **Route:** LLM decides vectorstore vs web search
3. **Query Generation:** LLM generates 5 diverse sub-queries
4. **Retrieval:** 
   - Batch retrieve with hybrid ensemble
   - RRF fusion across queries
   - Cohere rerank (if available)
5. **Grading:** LLM filters irrelevant documents
6. **Generation:** LLM produces cited answer
7. **Output:** Response in `generation` field

## Known Architectural Issues

1. **Router Double Execution:** The `router_node` is called directly in `add_conditional_edges`, which can execute it twice. The planned fix (Fase 0) is to have the node write to state and a separate function read the decision.

2. **State Mismatch:** Current `state.py` doesn't match the planned state in to-do list. The router expects `MessagesState` while the graph uses `GraphState`.

3. **Missing Async Consistency:** Some nodes are async, others sync - should standardize.

## Planned Architecture (from to-do)

```
Streamlit UI ──▶ FastAPI ──▶ LangGraph Agent
                  │              │
                  ▼              ▼
            Supabase (Auth, Storage, Postgres+pgvector)
                  │
                  ▼
            LangSmith (Tracing)
```

Key planned additions:
- **Memory Node:** Summarization every 4 messages
- **Excel Tool:** Predefined operations on XLSX files
- **Citation System:** Structured source tracking
- **Feedback Loop:** Thumbs up/down with trace linking
