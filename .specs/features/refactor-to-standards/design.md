# Refatoração para Padrões FastAPI - Design

**Spec**: `.specs/features/refactor-to-standards/spec.md`  
**Status**: Draft

---

## Architecture Overview

A arquitetura alvo segue o padrão **Domain-Driven Design** com organização por **Bounded Contexts**. Cada domínio é autônomo, com suas próprias configurações, schemas, serviços e dependências.

### Target Structure

```
src/
├── main.py                    # FastAPI app factory + lifespan
├── common/                    # Shared infrastructure
│   ├── __init__.py
│   ├── config.py             # Global BaseSettings (cross-domain)
│   ├── database.py           # Async engine + session factory
│   ├── models.py             # Shared Pydantic base models
│   ├── exceptions.py         # Global exceptions
│   └── dependencies.py       # Shared deps (db session, etc)
├── documents/                # Document domain (upload, status, list, delete)
│   ├── __init__.py
│   ├── router.py             # API endpoints
│   ├── schemas.py            # Pydantic models
│   ├── service.py            # Business logic
│   ├── dependencies.py       # Route dependencies
│   ├── config.py             # DocumentsConfig (BaseSettings)
│   ├── constants.py          # Error codes, constants
│   ├── exceptions.py         # Domain exceptions
│   └── models.py             # SQLAlchemy ORM models
├── agents/                   # LangGraph RAG agent
│   ├── __init__.py
│   ├── router.py             # Agent query endpoints
│   ├── schemas.py            # Agent request/response
│   ├── service.py            # Agent orchestration
│   ├── dependencies.py       # Agent deps
│   ├── config.py             # AgentsConfig
│   ├── constants.py
│   ├── exceptions.py
│   ├── graph.py              # LangGraph state machine
│   ├── state.py              # GraphState
│   ├── registry.py           # ContextVar registry
│   ├── nodes/                # Graph nodes
│   │   ├── __init__.py
│   │   ├── router.py
│   │   ├── retrieval.py
│   │   ├── query_generation.py
│   │   ├── grading.py
│   │   ├── generation.py
│   │   └── web_search.py
│   ├── retrievers/           # Retriever implementations
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── ensemble.py
│   │   ├── rrf.py
│   │   └── factories.py
│   └── rerankers/            # Reranker implementations
│       ├── __init__.py
│       ├── base.py
│       └── cohere.py
├── storage/                  # Supabase storage operations
│   ├── __init__.py
│   ├── service.py            # Supabase client wrapper
│   ├── dependencies.py       # Storage service injection
│   ├── config.py             # StorageConfig
│   ├── constants.py
│   └── exceptions.py
├── embeddings/               # OpenAI embeddings generation
│   ├── __init__.py
│   ├── service.py            # Embedding generator
│   ├── dependencies.py
│   ├── config.py             # EmbeddingsConfig
│   └── constants.py
├── chunking/                 # Document chunking
│   ├── __init__.py
│   ├── service.py            # LegalChunker
│   ├── dependencies.py
│   └── constants.py
├── extractors/               # Document text extractors
│   ├── __init__.py
│   ├── service.py            # Unified extractor service
│   ├── base.py               # TextExtractor ABC
│   ├── pdf.py                # PDF extractor
│   ├── docx.py               # DOCX extractor
│   └── xlsx.py               # XLSX extractor
└── graph/                    # Graph RAG (optional)
    ├── __init__.py
    ├── service.py            # Graph extractor/indexer
    ├── models.py             # Graph node/edge models
│   ├── dependencies.py
│   └── config.py
```

### Mapping from Current to Target

| Current Location | Target Location | Notes |
|-----------------|-----------------|-------|
| `api/main.py` | `src/main.py` | Adaptar imports |
| `api/models.py` | Split por domínio | `documents/schemas.py`, etc |
| `api/routes/documents.py` | `src/documents/router.py` | Modernizar Depends |
| `services/document_processor.py` | `src/documents/service.py` | Refatorar em serviços menores |
| `services/db/repositories.py` | `src/documents/` + `src/common/` | Separar Document/Chunk |
| `services/storage/supabase_client.py` | `src/storage/service.py` | Renomear para semanticamente correto |
| `services/embeddings/generator.py` | `src/embeddings/service.py` | Renomear |
| `services/chunking/legal_chunker.py` | `src/chunking/service.py` | Renomear |
| `services/extractors/*.py` | `src/extractors/` | Manter estrutura |
| `services/graph/*.py` | `src/graph/` | Manter estrutura |
| `my_agent/*.py` | `src/agents/` | Renomear domínio |
| `my_agent/nodes/` | `src/agents/nodes/` | Manter |
| `my_agent/retrievers/` | `src/agents/retrievers/` | Manter |
| `my_agent/rerankers/` | `src/agents/rerankers/` | Manter |
| `my_agent/config/settings.py` | Split por domínio | Distribuir configs |
| `frontend/` | Manter fora de `src/` | Frontend é separado |
| `vector_store/` | Avaliar - pode ir para `src/agents/retrievers/` | Ou criar `src/vector_store/` |

---

## Code Reuse Analysis

### Existing Components to Leverage

| Component | Current Location | Target Location | How to Use |
|-----------|-----------------|-----------------|------------|
| FastAPI app factory | `api/main.py` | `src/main.py` | Copiar e adaptar imports |
| Document routes | `api/routes/documents.py` | `src/documents/router.py` | Refatorar para Annotated Depends |
| Pydantic models | `api/models.py` | Split por domínio | Distribuir schemas apropriadamente |
| Document processor | `services/document_processor.py` | `src/documents/service.py` | Refatorar, manter lógica |
| Supabase client | `services/storage/supabase_client.py` | `src/storage/service.py` | Renomear, manter código |
| Repositories | `services/db/repositories.py` | `src/documents/models.py` | Converter para SQLAlchemy models |
| Embedding generator | `services/embeddings/generator.py` | `src/embeddings/service.py` | Renomear |
| Legal chunker | `services/chunking/legal_chunker.py` | `src/chunking/service.py` | Renomear |
| Extractors | `services/extractors/*.py` | `src/extractors/` | Manter, ajustar imports |
| LangGraph agent | `my_agent/` | `src/agents/` | Renomear pasta, manter código |

### Integration Points

| System | Integration Method |
|--------|-------------------|
| Supabase (DB + Storage) | Via `src/storage/service.py` - cliente async já existente |
| OpenAI (Embeddings + LLM) | Via `src/embeddings/service.py` e `src/agents/` - já implementado |
| FastAPI Router | Mount no `src/main.py` - padrão já existente |
| Pydantic Settings | Novo - criar BaseSettings por domínio |

---

## Components

### Common Domain (`src/common/`)

**Purpose**: Infrastructure compartilhada entre domínios

**Location**: `src/common/`

**Components**:
- `config.py`: `CommonConfig` com variáveis globais (ambiente, debug)
- `database.py`: `create_async_engine`, `AsyncSession`, `get_db()`
- `models.py`: `CustomModel` base com `@field_serializer` para datetimes
- `exceptions.py`: `BaseAppException`, `NotFoundError`, `ValidationError`
- `dependencies.py`: `DbDep = Annotated[AsyncSession, Depends(get_db)]`

**Naming Convention for SQLAlchemy**:
```python
POSTGRES_INDEXES_NAMING_CONVENTION = {
    "ix": "%(column_0_label)s_idx",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}
```

---

### Documents Domain (`src/documents/`)

**Purpose**: Gestão de documentos (upload, processamento, listagem, deleção)

**Location**: `src/documents/`

**Interfaces**:
```python
# router.py
@router.post("/upload", status_code=status.HTTP_202_ACCEPTED)
async def upload_document(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    storage: StorageDep,
    db: DbDep,
    user_id: str,  # from auth
) -> UploadResponse: ...

@router.get("/{document_id}/status")
async def get_document_status(
    document_id: UUID4,
    doc: DocumentDep,  # validated dependency
) -> DocumentStatusResponse: ...

@router.get("/")
async def list_documents(
    db: DbDep,
    user_id: str,
    skip: int = 0,
    limit: int = 100,
) -> DocumentListResponse: ...

@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc: DocumentDep,
    storage: StorageDep,
    db: DbDep,
) -> None: ...
```

**Dependencies**:
```python
# dependencies.py
from typing import Annotated
from fastapi import Depends, Path

async def valid_document_id(
    document_id: UUID4,
    db: DbDep,
    user_id: str,
) -> DocumentRecord:
    doc = await service.get_document(db, document_id, user_id)
    if not doc:
        raise DocumentNotFound()
    return doc

DocumentDep = Annotated[DocumentRecord, Depends(valid_document_id)]
```

**Config**:
```python
# config.py
class DocumentsConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DOCUMENTS_")
    
    MAX_FILE_SIZE: int = 50 * 1024 * 1024  # 50MB
    ALLOWED_EXTENSIONS: set[str] = {"pdf", "docx", "xlsx", "txt"}
    PROCESSING_TIMEOUT_SECONDS: int = 300
```

**Reuses**: `common.database`, `common.dependencies`, `storage.service`

---

### Agents Domain (`src/agents/`)

**Purpose**: LangGraph RAG agent para consultas contextuais

**Location**: `src/agents/`

**Interfaces**:
```python
# router.py
@router.post("/query")
async def query_agent(
    request: AgentQueryRequest,
    agent: AgentDep,  # compiled graph from registry
) -> AgentQueryResponse: ...

@router.get("/graph/status")  # se graph_rag habilitado
async def get_graph_status(
    config: AgentsConfigDep,
) -> GraphStatusResponse: ...
```

**Dependencies**:
```python
# dependencies.py
from typing import Annotated
from fastapi import Depends
from .registry import get_compiled_graph

AgentDep = Annotated[CompiledGraph, Depends(get_compiled_graph)]
AgentsConfigDep = Annotated[AgentsConfig, Depends(get_agents_config)]
```

**Config**:
```python
# config.py
class AgentsConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AGENTS_")
    
    OPENAI_API_KEY: str
    OPENAI_MODEL: str = "gpt-4o-mini"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    GRAPH_RAG_ENABLED: bool = False
    COHERE_API_KEY: str | None = None
    TAVILY_API_KEY: str | None = None
```

**Reuses**: Toda a estrutura existente de `my_agent/` migrada

---

### Storage Domain (`src/storage/`)

**Purpose**: Operações de storage Supabase (upload, download, delete)

**Location**: `src/storage/`

**Interfaces**:
```python
# service.py
class StorageService:
    async def upload_file(
        self,
        bucket: str,
        path: str,
        data: bytes,
        content_type: str,
    ) -> str: ...  # returns URL
    
    async def download_file(
        self,
        bucket: str,
        path: str,
    ) -> bytes: ...
    
    async def delete_file(
        self,
        bucket: str,
        path: str,
    ) -> None: ...
    
    async def get_public_url(
        self,
        bucket: str,
        path: str,
    ) -> str: ...

# dependencies.py
StorageDep = Annotated[StorageService, Depends(get_storage_service)]
```

**Config**:
```python
# config.py
class StorageConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="STORAGE_")
    
    SUPABASE_URL: str
    SUPABASE_SERVICE_KEY: str
    SUPABASE_STORAGE_BUCKET: str = "documents"
```

**Reuses**: Código existente de `services/storage/supabase_client.py`

---

### Embeddings Domain (`src/embeddings/`)

**Purpose**: Geração de embeddings OpenAI

**Location**: `src/embeddings/`

**Interfaces**:
```python
# service.py
class EmbeddingsService:
    async def generate_embeddings(
        self,
        texts: list[str],
        batch_size: int = 100,
    ) -> list[list[float]]: ...
    
    async def generate_single(
        self,
        text: str,
    ) -> list[float]: ...

# dependencies.py
EmbeddingsDep = Annotated[EmbeddingsService, Depends(get_embeddings_service)]
```

**Config**:
```python
# config.py
class EmbeddingsConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EMBEDDINGS_")
    
    OPENAI_API_KEY: str
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSIONS: int = 1536
    BATCH_SIZE: int = 100
    REQUEST_TIMEOUT: int = 60
```

---

### Chunking Domain (`src/chunking/`)

**Purpose**: Chunking estruturado de documentos jurídicos

**Location**: `src/chunking/`

**Interfaces**:
```python
# service.py
class ChunkingService:
    def chunk_document(
        self,
        text: str,
        metadata: dict,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ) -> list[Chunk]: ...

# dependencies.py  
ChunkingDep = Annotated[ChunkingService, Depends(get_chunking_service)]
```

**Reuses**: Código de `services/chunking/legal_chunker.py`

---

### Extractors Domain (`src/extractors/`)

**Purpose**: Extração de texto de diferentes formatos de documento

**Location**: `src/extractors/`

**Interfaces**:
```python
# service.py
class ExtractionService:
    async def extract(
        self,
        file_path: str,
        mime_type: str,
    ) -> ExtractionResult: ...

# base.py (abstract)
class TextExtractor(ABC):
    @abstractmethod
    async def extract(self, file_path: str) -> str: ...
```

**Reuses**: Código de `services/extractors/*.py`

---

### Graph Domain (`src/graph/`)

**Purpose**: Graph RAG - extração e indexação de grafo de conhecimento

**Location**: `src/graph/`

**Interfaces**:
```python
# service.py
class GraphService:
    async def extract_graph(
        self,
        document_id: str,
        chunks: list[Chunk],
    ) -> GraphExtractionResult: ...
    
    async def index_graph(
        self,
        graph: GraphExtractionResult,
    ) -> None: ...
```

**Reuses**: Código de `services/graph/*.py`

---

## Data Models

### Common Base Model

```python
# src/common/models.py
from datetime import datetime
from zoneinfo import ZoneInfo
from pydantic import BaseModel, ConfigDict, field_serializer

class CustomModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    @field_serializer("*", when_used="json", check_fields=False)
    def _serialize_datetimes(self, value):
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=ZoneInfo("UTC"))
            return value.strftime("%Y-%m-%dT%H:%M:%S%z")
        return value
```

### Document Models (SQLAlchemy)

```python
# src/documents/models.py
from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from common.database import Base

class Document(Base):
    __tablename__ = "document"
    
    id = Column(UUID(as_uuid=True), primary_key=True)
    user_id = Column(String, nullable=False, index=True)  # RLS
    filename = Column(String, nullable=False)
    original_name = Column(String, nullable=False)
    mime_type = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    storage_path = Column(String, nullable=False)
    status = Column(String, nullable=False, default="processing")
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    chunk_count = Column(Integer, default=0)
    graph_status = Column(String, nullable=True)

class Chunk(Base):
    __tablename__ = "chunk"
    
    id = Column(UUID(as_uuid=True), primary_key=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("document.id"), nullable=False)
    user_id = Column(String, nullable=False, index=True)  # RLS
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1536), nullable=True)  # pgvector
    metadata = Column(JSON, nullable=True)
    index = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)
```

### Pydantic Schemas (Documents)

```python
# src/documents/schemas.py
from typing import Annotated
from pydantic import BaseModel, Field, UUID4
from datetime import datetime
from common.models import CustomModel

class UploadResponse(CustomModel):
    document_id: UUID4
    status: str = "processing"
    message: str = "Document upload received and queued for processing"

class DocumentStatusResponse(CustomModel):
    document_id: UUID4
    filename: str
    status: str
    created_at: datetime
    updated_at: datetime
    processed_at: datetime | None
    chunk_count: int
    graph_status: str | None
    error_message: str | None

class DocumentSummary(CustomModel):
    document_id: UUID4 = Field(alias="id")
    filename: str
    status: str
    created_at: datetime
    size_bytes: int
    chunk_count: int

class DocumentListResponse(CustomModel):
    documents: list[DocumentSummary]
    total: int
    skip: int
    limit: int
```

---

## Error Handling Strategy

| Error Scenario | Handling | User Impact |
|---------------|----------|-------------|
| Document not found (404) | Raise `DocumentNotFound()` → HTTP 404 | JSON: `{"error": "Document not found", "code": "DOC_NOT_FOUND"}` |
| Invalid file type (400) | Raise `InvalidFileType()` → HTTP 400 | JSON: `{"error": "File type not allowed", "allowed": [...]}` |
| File too large (413) | Raise `FileTooLarge()` → HTTP 413 | JSON: `{"error": "File exceeds max size", "max_size": 50MB}` |
| Storage upload fail (502) | Raise `StorageError()` → HTTP 502 | JSON: `{"error": "Storage operation failed"}` |
| Processing fail (500) | Update doc status to "error", log | JSON: `{"error": "Processing failed", "document_id": "..."}` |
| Auth fail (401) | Raise `InvalidCredentials()` → HTTP 401 | JSON: `{"error": "Invalid or missing token"}` |

---

## Tech Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Estrutura de pastas | `src/{domain}/` | Padrão definido no `agentic-rag-standards.mdc` |
| Dependências | `Annotated[T, Depends(...)]` | Padrão idiomatico FastAPI 0.95+, evita bugs com defaults |
| Configuração | `BaseSettings` por domínio | Separação de concerns, cada domínio gerencia suas variáveis |
| Env prefixes | `DOCUMENTS_`, `AGENTS_`, `STORAGE_`, etc | Evita colisão de nomes, clareza |
| SQLAlchemy naming | `POSTGRES_INDEXES_NAMING_CONVENTION` | Consistência com schema PostgreSQL |
| Pydantic base | `CustomModel` com `@field_serializer` | Padrão Pydantic v2, substitui `json_encoders` deprecated |
| Async DB | `AsyncSession` + `async_sessionmaker` | Padrão SQLAlchemy 2.0 async |
| Cross-domain imports | `from src.x import service as x_service` | Evita circular deps, clareza |

---

## Migration Path

A refatoração será feita em fases para minimizar risco:

1. **Fase 1**: Criar estrutura `src/` vazia com `__init__.py`
2. **Fase 2**: Migrar `common/` (database, config, models base)
3. **Fase 3**: Migrar `storage/` (serviço independente)
4. **Fase 4**: Migrar `embeddings/` (serviço independente)
5. **Fase 5**: Migrar `extractors/` e `chunking/` (serviços independentes)
6. **Fase 6**: Migrar `documents/` (depende de storage, db, embeddings, chunking, extractors)
7. **Fase 7**: Migrar `agents/` (depende de quase tudo)
8. **Fase 8**: Migrar `graph/` (opcional)
9. **Fase 9**: Atualizar `main.py` e testar end-to-end
10. **Fase 10**: Limpar código antigo após validação

Cada fase é independente (pode ser testada) e builda sobre as anteriores.
