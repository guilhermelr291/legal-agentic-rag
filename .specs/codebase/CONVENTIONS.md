# Coding Conventions

## Source of Truth

The `.cursor/rules/agentic-rag-standards.mdc` file contains the authoritative coding standards. This document summarizes and supplements those rules.

## Quick Reference

### Import Order (Strict)

```python
# 1. Standard library
from typing import List, Optional, Literal
from abc import ABC, abstractmethod

# 2. Third-party (langchain, pydantic)
from pydantic import BaseModel, Field
from langchain_core.documents import Document
from langgraph.graph import StateGraph

# 3. Project internals
from my_agent.state import GraphState
from my_agent.registry import get_llm, get_retriever
```

### Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Files | snake_case | `query_generation.py` |
| Classes | PascalCase | `EnsembleRetriever` |
| Functions | snake_case | `multi_query_generation_node` |
| Constants | UPPER_SNAKE_CASE | `PER_QUERY_K = 50` |

### Type Hints

Always use type hints in public functions:

```python
# ✅ Correct
def retrieve(self, query: str, k: int = 10) -> List[Document]:
    pass

class GraphState(TypedDict):
    messages: Annotated[list[AnyMessage], operator.add]
    documents: List[str]
```

### Graph Node Pattern

Always return partial state dictionary:

```python
# ✅ Correct
async def retrieval_node(state: GraphState) -> dict:
    queries = state["queries_for_retrieval"]
    retriever = get_retriever()
    documents = await retriever.abatch_retrieve(queries, k=PER_QUERY_K)
    return {"documents": documents}  # ← only what changed
```

### Structured LLM Outputs

All LLM nodes must define Pydantic schemas:

```python
class RouteQuery(BaseModel):
    datasource: Literal["vectorstore", "web_search"] = Field(
        description="Route to vectorstore for Python topics or web_search for general"
    )

structured_llm = get_llm().with_structured_output(RouteQuery)
```

### Registry Access

Never instantiate LLM/Retriever directly:

```python
# ✅ Correct
from my_agent.registry import get_llm, get_retriever

llm = get_llm()
retriever = get_retriever()

# ❌ Wrong
llm = ChatOpenAI(api_key="...")  # NEVER do this
```

### Configuration Access

Use `get_settings()` for all configuration:

```python
from my_agent.config.settings import get_settings

settings = get_settings()
model = settings.openai_lightweight_model
```

### Async Pattern

Use `abatch` for parallel operations:

```python
# ✅ Correct
ranked_per_query = await retriever.abatch_retrieve(queries, k=PER_QUERY_K)

# Or with asyncio.gather for multiple LLM calls
results = await asyncio.gather(*tasks)
```

### Abstract Base Classes

Retrievers must inherit from base class:

```python
from my_agent.retrievers.base import Retriever

class EnsembleRetriever(Retriever):
    def retrieve(self, query: str, k: int = 10) -> List[Document]:
        # implementation
```

### Constants Placement

Define constants at module top:

```python
# ✅ Correct
PER_QUERY_K = 50
RRF_TOP_K = 50
DEFAULT_HYBRID_WEIGHTS = [0.7, 0.3]

async def retrieval_node(state: GraphState) -> dict:
    ...
```

## New Code Checklist

Before committing, verify:

- [ ] Type hints in all public functions
- [ ] Pydantic schema for LLM outputs
- [ ] Access via registry (get_llm, get_retriever)
- [ ] Partial state return in nodes
- [ ] Imports in correct order (stdlib → third-party → internal)
- [ ] Naming following conventions
- [ ] Use get_settings() for configuration
- [ ] Async when there are parallel operations
