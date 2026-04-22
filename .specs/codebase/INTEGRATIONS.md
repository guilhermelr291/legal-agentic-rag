# External Integrations

## Current Integrations

### 1. OpenAI

**Purpose:** LLM provider for generation, routing, and query transformation

**Configuration:**
```python
# settings.py
openai_api_key: str
openai_lightweight_model: str = "gpt-5-nano"  # For routing, grading
openai_model_generation: str = "gpt-5-mini"   # For answer generation
```

**Usage:**
```python
from my_agent.registry import get_llm
from my_agent.config.settings import get_settings

# Lightweight tasks (routing, grading, query gen)
llm = get_llm()  # gpt-5-nano

# Generation
settings = get_settings()
llm = ChatOpenAI(model=settings.openai_model_generation)
```

**Nodes using:**
- `router_node` - Structured output routing
- `multi_query_generation_node` - Query generation
- `documents_grader_node` - Relevance grading
- `generate_answer_node` - Answer generation

### 2. Tavily Search

**Purpose:** Web search fallback for general knowledge queries

**Configuration:**
```python
# settings.py
tavily_api_key: str | None = None
tavily_max_results: int = 5
```

**Usage:**
```python
from langchain_tavily import TavilySearch
from my_agent.config.settings import get_settings

settings = get_settings()
tavily_tool = TavilySearch(max_results=settings.tavily_max_results)
```

**Node:** `web_search_node`

**Flow:**
```
User question → LLM optimizes query → Tavily search → Documents to state
```

### 3. Cohere Rerank (Optional)

**Purpose:** Document reranking for improved retrieval quality

**Configuration:**
```python
# settings.py
cohere_api_key: str | None = None
cohere_rerank_model: str = "rerank-v3.5"
rerank_top_k: int = 10
```

**Usage:**
```python
from my_agent.rerankers.cohere import CohereReranker

reranker = CohereReranker(api_key=settings.cohere_api_key)
```

**Graceful Degradation:**
```python
# retrieval_node.py
try:
    reranker = get_reranker()
    fused = await reranker.arerank(user_query, fused, top_k=final_k)
except RuntimeError:
    # Reranker not configured, use simple slice
    fused = fused[:final_k]
```

**Node:** `retrieval_node`

## Planned Integrations (from to-do)

### 4. Supabase

**Purpose:** Database, storage, and authentication

**Components:**
- **Postgres + pgvector:** Chunk storage and vector search
- **Storage:** File storage for PDFs/DOCXs/XLSXs
- **Auth:** JWT-based user authentication
- **RLS:** Row-level security for data isolation

**Tables Planned:**
- `documents` - File metadata
- `chunks` - Document chunks with embeddings
- `messages` - Chat history
- `thread_summaries` - Conversation summaries
- `user_preferences` - User preferences
- `feedback` - Thumbs up/down feedback

**Environment Variables:**
```
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
SUPABASE_JWT_SECRET
```

### 5. LangSmith

**Purpose:** Tracing and observability

**Configuration:**
```python
LANGCHAIN_API_KEY
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=legal-rag-portfolio
```

**Usage:**
- Automatic tracing via LangGraph
- Manual `trace_id` capture for feedback linking

### 6. RAGAS

**Purpose:** RAG evaluation framework

**Metrics:**
- Faithfulness
- Answer relevancy
- Context precision
- Context recall

## Integration Health

| Integration | Status | Config Required | Graceful Degradation |
|-------------|--------|-----------------|---------------------|
| OpenAI | ✅ Required | `OPENAI_API_KEY` | No |
| Tavily | ⚠️ Optional | `TAVILY_API_KEY` | Yes (vectorstore only) |
| Cohere | ⚠️ Optional | `COHERE_API_KEY` | Yes (skip rerank) |
| Supabase | 🔲 Planned | Multiple | TBD |
| LangSmith | 🔲 Planned | `LANGCHAIN_API_KEY` | Yes |
| RAGAS | 🔲 Planned | Dataset | N/A (eval only) |

## Error Handling Patterns

### Missing Optional Integration

```python
from my_agent.registry import get_reranker

try:
    reranker = get_reranker()
except RuntimeError as e:
    # Log and continue without reranking
    logger.warning(f"Reranker not available: {e}")
    reranker = None
```

### API Failures

```python
# In nodes, wrap external calls
try:
    results = await external_api_call()
except ExternalAPIError as e:
    # Return empty or fallback
    return {"documents": []}
```

## Security Considerations

1. **API Keys:** All keys stored in environment variables, never in code
2. **Service Role Key:** Supabase service role key only on backend, never exposed to frontend
3. **RLS:** All queries filtered by `auth.uid()` from JWT
