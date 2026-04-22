# Project Structure

## Directory Tree

```
Agentic RAG/
├── .cursor/
│   └── rules/
│       └── agentic-rag-standards.mdc    # Coding standards
├── .specs/                               # Specification-driven docs (this dir)
│   └── codebase/                         # Brownfield mapping
│       ├── STACK.md
│       ├── ARCHITECTURE.md
│       ├── CONVENTIONS.md
│       ├── STRUCTURE.md
│       ├── TESTING.md
│       ├── INTEGRATIONS.md
│       └── CONCERNS.md
├── my_agent/                             # Main application package
│   ├── __init__.py
│   ├── graph.py                          # LangGraph definition
│   ├── state.py                          # Graph state TypedDict
│   ├── registry.py                       # ContextVar DI container
│   ├── config/                           # Configuration
│   │   ├── __init__.py
│   │   └── settings.py                   # Pydantic Settings
│   ├── nodes/                            # Graph nodes
│   │   ├── __init__.py
│   │   ├── router.py                     # Routing logic
│   │   ├── query_generation.py           # Multi-query generation
│   │   ├── retrieval.py                  # Document retrieval
│   │   ├── grading.py                    # Document grading
│   │   ├── generation.py                 # Answer generation
│   │   └── web_search.py                 # Web search fallback
│   ├── retrievers/                       # Retrieval implementations
│   │   ├── __init__.py
│   │   ├── base.py                       # Abstract base class
│   │   ├── ensemble.py                   # Hybrid ensemble
│   │   ├── rrf.py                        # Reciprocal Rank Fusion
│   │   └── factories.py                  # Retriever factories
│   └── rerankers/                        # Reranking implementations
│       ├── __init__.py
│       ├── base.py                       # Abstract base class
│       └── cohere.py                     # Cohere reranker
├── vector_store/                         # Vector store implementations
│   └── faiss.py                          # FAISS wrapper
├── document_loaders/                     # Document loading
│   └── pdf_loader.py                     # PDF loader wrapper
├── pyproject.toml                        # Project metadata & deps
├── requirements.txt                      # Additional dependencies
└── .gitignore                            # Git ignore rules
```

## Module Descriptions

### Core Modules

| Module | Purpose | Key Exports |
|--------|---------|-------------|
| `graph.py` | LangGraph flow definition | `create_graph()` |
| `state.py` | State schema | `GraphState`, `MessagesState` |
| `registry.py` | Dependency injection | `get_llm()`, `get_retriever()`, `get_reranker()` |

### Nodes (`my_agent/nodes/`)

| Node | File | Purpose |
|------|------|---------|
| Router | `router.py` | Routes queries to vectorstore or web_search |
| Query Generation | `query_generation.py` | Generates multiple sub-queries |
| Retrieval | `retrieval.py` | Hybrid retrieval with RRF and rerank |
| Grading | `grading.py` | Filters irrelevant documents |
| Generation | `generation.py` | Produces final answer |
| Web Search | `web_search.py` | Tavily web search |

### Retrievers (`my_agent/retrievers/`)

| Module | Purpose |
|--------|---------|
| `base.py` | Abstract `Retriever` base class |
| `ensemble.py` | LangChain ensemble with configurable weights |
| `rrf.py` | Reciprocal Rank Fusion algorithm |
| `factories.py` | Factory functions for creating retrievers |

### Rerankers (`my_agent/rerankers/`)

| Module | Purpose |
|--------|---------|
| `base.py` | Abstract `Reranker` base class |
| `cohere.py` | Cohere API reranker implementation |

### Support Modules

| Module | Purpose |
|--------|---------|
| `config/settings.py` | Pydantic Settings for environment variables |
| `vector_store/faiss.py` | FAISS vector store wrapper |
| `document_loaders/pdf_loader.py` | PDF document loader |

## Import Patterns

### From Package Root

```python
from my_agent import create_graph, GraphState
from my_agent.nodes import router_node, retrieval_node
from my_agent.retrievers import Retriever, EnsembleRetriever
from my_agent.rerankers import Reranker, CohereReranker
```

### Internal Module Imports

```python
# Within my_agent/nodes/retrieval.py
from my_agent.config.settings import get_settings
from my_agent.registry import get_retriever, get_reranker
from my_agent.retrievers.rrf import reciprocal_rank_fusion_documents
from my_agent.state import GraphState
```

## Planned Additions (from to-do)

Based on the roadmap, the following structure additions are planned:

```
my_agent/
├── nodes/
│   ├── memory.py           # Memory/summarization node
│   └── xlsx_tool.py        # Excel analysis tool
├── api/                    # FastAPI endpoints
│   └── main.py
└── utils/                  # Utility functions
    └── chunking.py         # Legal document chunking

frontend/                   # Streamlit UI
└── app.py

evaluation/                 # RAGAS evaluation
└── dataset.json

supabase/                   # Database migrations
└── schema.sql
```
