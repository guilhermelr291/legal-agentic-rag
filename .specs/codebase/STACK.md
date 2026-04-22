# Tech Stack

## Core Framework

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Language | Python | >=3.12 | Primary development language |
| Agent Framework | LangGraph | >=1.1.6 | State graph orchestration |
| LLM Framework | LangChain | >=1.2.15 | LLM abstractions and chains |
| LLM Provider | OpenAI | gpt-5-nano, gpt-5-mini | Generation and routing |

## Dependencies

### Required (from pyproject.toml)

```toml
[dependencies]
langchain>=1.2.15
langchain-community>=0.4.1
langchain-openai>=1.1.12
langchain-tavily>=0.2.17
langgraph>=1.1.6
pypdf>=6.10.0
```

### Additional (from requirements.txt)

```
langchain-chroma>=0.0.5
chromadb>=0.4.18
tavily-python>=0.3.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
python-dotenv>=1.0.0
cohere  # for reranking (optional)
```

## Key Libraries

| Domain | Library | Purpose |
|--------|---------|---------|
| Settings | pydantic-settings | Environment-based configuration |
| Search | langchain-tavily | Web search fallback |
| Embeddings | langchain-openai | OpenAI embedding models |
| Vector Store | ChromaDB (planned), FAISS (current) | Document storage and retrieval |
| PDF Loading | PyPDFLoader | Document ingestion |
| Reranking | Cohere API | Document reranking (optional) |

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `OPENAI_API_KEY` | Yes | OpenAI API access |
| `OPENAI_LIGHTWEIGHT_MODEL` | No | Lightweight model (default: gpt-5-nano) |
| `OPENAI_MODEL_GENERATION` | No | Generation model (default: gpt-5-mini) |
| `TAVILY_API_KEY` | No | Web search capability |
| `TAVILY_MAX_RESULTS` | No | Web search limit (default: 5) |
| `COHERE_API_KEY` | No | Reranking capability |
| `COHERE_RERANK_MODEL` | No | Rerank model (default: rerank-v3.5) |
| `RERANK_TOP_K` | No | Number of docs after rerank (default: 10) |

## Planned Stack (from to-do list)

| Component | Technology | Purpose |
|-----------|------------|---------|
| Frontend | Streamlit | User interface |
| Backend API | FastAPI | REST endpoints |
| Database | Supabase (Postgres + pgvector) | Persistent storage |
| Storage | Supabase Storage | File storage |
| Auth | Supabase Auth | User authentication |
| Observability | LangSmith | Tracing and monitoring |
| Evaluation | RAGAS | RAG evaluation metrics |
| Deployment | Railway | Hosting platform |
