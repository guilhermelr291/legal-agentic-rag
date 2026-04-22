# Testing Patterns

## Current State

**No tests are currently implemented.** This document outlines the testing strategy to be adopted.

## Planned Testing Strategy

### Test Categories

| Category | Tool | Purpose |
|----------|------|---------|
| Unit Tests | pytest | Test individual nodes and functions |
| Integration Tests | pytest | Test graph flows end-to-end |
| RAG Evaluation | RAGAS | Measure retrieval and generation quality |

### RAGAS Evaluation Plan (from to-do)

Planned metrics for the evaluation pipeline:

```python
from ragas import evaluate
from ragas.metrics import (
    faithfulness,           # Is answer supported by context?
    answer_relevancy,       # Is answer relevant to question?
    context_precision,      # Are retrieved chunks relevant?
    context_recall          # Were necessary chunks retrieved?
)
```

### Ablations to Document

Planned comparison of configurations:

| Config | Dense | Lexical | Rerank |
|--------|-------|---------|--------|
| Baseline | ✅ | ❌ | ❌ |
| + Lexical | ✅ | ✅ | ❌ |
| + Rerank | ✅ | ❌ | ✅ |
| Full System | ✅ | ✅ | ✅ |

### Dataset Generation

Synthetic dataset generation planned:

```python
# Generate Q&A pairs from legal documents
prompt = """
Given this legal document excerpt, generate 10 question-answer pairs.
For each pair include: question, expected_answer, supporting_quotes.
Return JSON only.
"""
```

## Testing Conventions

### Test File Structure (Proposed)

```
tests/
├── __init__.py
├── conftest.py              # Shared fixtures
├── unit/
│   ├── test_nodes.py        # Node unit tests
│   ├── test_retrievers.py   # Retriever tests
│   └── test_rerankers.py    # Reranker tests
├── integration/
│   └── test_graph.py        # Graph flow tests
└── evaluation/
    ├── test_ragas.py        # RAGAS metrics
    └── fixtures/
        └── dataset.json     # Synthetic Q&A pairs
```

### Fixtures Needed

```python
# conftest.py suggestions

import pytest
from my_agent.registry import set_llm, set_retriever, clear_registry

@pytest.fixture(autouse=True)
def reset_registry():
    """Clear registry before each test."""
    clear_registry()
    yield

@pytest.fixture
def mock_llm():
    """Mock LLM for unit tests."""
    # Use langchain's fake LLM or mock
    pass

@pytest.fixture
def mock_retriever():
    """Mock retriever that returns fixed documents."""
    pass
```

## Gate Check Commands (Planned)

```bash
# Run unit tests
pytest tests/unit/ -v

# Run integration tests
pytest tests/integration/ -v

# Run RAGAS evaluation
python -m evaluation.run_ragas

# Coverage report
pytest --cov=my_agent --cov-report=html
```

## Continuous Integration (Planned)

```yaml
# .github/workflows/test.yml (suggested)
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - run: pip install -e ".[dev]"
      - run: pytest --cov=my_agent
```

## Known Testing Debt

1. No unit tests for nodes
2. No integration tests for graph flows
3. No RAGAS evaluation setup
4. No synthetic dataset created
5. No mock/stub implementations for external APIs
