# Refatoração para Padrões FastAPI - Tasks

**Design**: `.specs/features/refactor-to-standards/design.md`  
**Status**: Draft

---

## Execution Plan

### Phase 1: Estrutura Base e Common (Sequential)

Criar a estrutura `src/` e o domínio `common/` que outros domínios dependem.

```
T1 ──→ T2 ──→ T3 ──→ T4 ──→ T5
```

### Phase 2: Domínios Independentes (Parallel OK)

Domínios que não dependem uns dos outros, apenas de `common`.

```
                    ┌→ T6 ──→ T7  [storage]
                    │
T5 complete, then:  ├→ T8 ──→ T9  [embeddings]
                    │
                    ├→ T10 ─→ T11 [extractors]
                    │
                    └→ T12 ─→ T13 [chunking]
```

### Phase 3: Domínios Dependentes (Sequential)

Domínios que dependem dos anteriores.

```
T7, T9, T11, T13 complete, then:

T14 ──→ T15 ──→ T16  [documents - router completo]
       │
       └──→ T17 ──→ T18  [agents - graph completo]
```

### Phase 4: Main e Integração (Sequential)

Montar tudo no ponto de entrada.

```
T18 complete, then:

T19 ──→ T20 ──→ T21
       │
       └──→ T22 (parallel with T21)
```

### Phase 5: Limpeza e Validação (Sequential)

```
T21, T22 complete, then:

T23 ──→ T24
```

---

## Task Breakdown

### Phase 1: Estrutura Base e Common

#### T1: Criar estrutura de pastas src/

**What**: Criar toda a estrutura de diretórios vazia para `src/` com `__init__.py`  
**Where**: `src/` (novo diretório raiz)  
**Depends on**: None  
**Reuses**: N/A (estrutura nova)  
**Requirement**: REFAC-01

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] Diretório `src/` criado
- [ ] Subdiretórios criados: `common/`, `documents/`, `agents/`, `agents/nodes/`, `agents/retrievers/`, `agents/rerankers/`, `storage/`, `embeddings/`, `extractors/`, `chunking/`, `graph/`
- [ ] Arquivos `__init__.py` vazios em cada pasta
- [ ] `main.py` vazio criado em `src/`

**Tests**: none  
**Gate**: build  

**Verify**:
```bash
ls -la src/*/
tree src/
```

---

#### T2: Criar configuração global (common/config.py)

**What**: Configurações compartilhadas entre domínios (ambiente, debug)  
**Where**: `src/common/config.py`  
**Depends on**: T1  
**Reuses**: Código de `my_agent/config/settings.py` (variáveis globais)  
**Requirement**: REFAC-12

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `CommonConfig(BaseSettings)` criado
- [ ] Variáveis: `ENVIRONMENT`, `DEBUG`, `LOG_LEVEL`
- [ ] `env_prefix="APP_"` configurado
- [ ] Instância `common_settings` exportada
- [ ] Import funciona: `from src.common.config import common_settings`

**Tests**: none  
**Gate**: build  

**Verify**:
```bash
cd src && python -c "from common.config import common_settings; print(common_settings)"
```

---

#### T3: Criar base de dados (common/database.py)

**What**: Configuração SQLAlchemy async com naming conventions  
**Where**: `src/common/database.py`  
**Depends on**: T1, T2  
**Reuses**: Padrões de `services/db/repositories.py` (conexão Supabase)  
**Requirement**: REFAC-15, REFAC-19

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `POSTGRES_INDEXES_NAMING_CONVENTION` definido
- [ ] `metadata = MetaData(naming_convention=...)` criado
- [ ] `Base = declarative_base(metadata=metadata)`
- [ ] `create_async_engine` configurado com `pool_pre_ping=True`
- [ ] `SessionFactory = async_sessionmaker(..., expire_on_commit=False)`
- [ ] `async def get_db() -> AsyncSession` dependency
- [ ] `DbDep = Annotated[AsyncSession, Depends(get_db)]` alias exportado

**Tests**: none  
**Gate**: build  

**Verify**:
```bash
cd src && python -c "from common.database import Base, engine, SessionFactory, DbDep; print('OK')"
```

---

#### T4: Criar modelos base Pydantic (common/models.py)

**What**: Base model com `@field_serializer` para datetimes  
**Where**: `src/common/models.py`  
**Depends on**: T1  
**Reuses**: Padrão do standards (`@field_serializer` moderno)  
**Requirement**: REFAC-31

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `CustomModel(BaseModel)` criado
- [ ] `model_config = ConfigDict(populate_by_name=True)`
- [ ] `@field_serializer("*", when_used="json")` para datetimes
- [ ] Formato ISO: `%Y-%m-%dT%H:%M:%S%z`
- [ ] Timezone UTC aplicado se datetime for naive

**Tests**: none  
**Gate**: build  

**Verify**:
```python
cd src && python -c "
from common.models import CustomModel
from datetime import datetime
from pydantic import Field

class Test(CustomModel):
    dt: datetime = Field(default_factory=datetime.utcnow)

t = Test()
print(t.model_dump_json())
"
```

---

#### T5: Criar exceções globais (common/exceptions.py)

**What**: Hierarquia de exceções da aplicação  
**Where**: `src/common/exceptions.py`  
**Depends on**: T1  
**Reuses**: Padrões de `api/main.py` (exception handlers)  
**Requirement**: REFAC-01

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `BaseAppException(Exception)` criado
- [ ] `NotFoundError(BaseAppException)`
- [ ] `ValidationError(BaseAppException)`
- [ ] `UnauthorizedError(BaseAppException)`
- [ ] `StorageError(BaseAppException)`
- [ ] `ProcessingError(BaseAppException)`
- [ ] Cada exceção tem `message` e opcional `code`

**Tests**: none  
**Gate**: build  

**Verify**:
```bash
cd src && python -c "from common.exceptions import BaseAppException, NotFoundError; raise NotFoundError('test')"
```

---

### Phase 2: Domínios Independentes

#### T6: Criar config storage (storage/config.py) [P]

**What**: BaseSettings para storage (Supabase)  
**Where**: `src/storage/config.py`  
**Depends on**: T5  
**Reuses**: Variáveis de `my_agent/config/settings.py`  
**Requirement**: REFAC-10, REFAC-14

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `StorageConfig(BaseSettings)` criado
- [ ] `env_prefix="STORAGE_"`
- [ ] Variáveis: `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `SUPABASE_STORAGE_BUCKET`
- [ ] Instância `storage_settings` exportada

**Tests**: none  
**Gate**: build  

**Verify**:
```bash
cd src && python -c "from storage.config import storage_settings; print(storage_settings.SUPABASE_STORAGE_BUCKET)"
```

---

#### T7: Migrar serviço storage (storage/service.py)

**What**: Mover e adaptar código de `services/storage/supabase_client.py`  
**Where**: `src/storage/service.py`  
**Depends on**: T6  
**Reuses**: Todo código de `services/storage/supabase_client.py`  
**Requirement**: REFAC-26, REFAC-27

**Tools**:
- MCP: filesystem
- Skill: NONE

**Done when**:
- [ ] `StorageService` classe criada
- [ ] Métodos: `upload_file`, `download_file`, `delete_file`, `get_public_url`
- [ ] Usa `storage_settings` para configuração
- [ ] Async/await preservado
- [ ] `StorageDep = Annotated[StorageService, Depends(get_storage_service)]` em `dependencies.py`
- [ ] Não há imports circulares

**Tests**: none  
**Gate**: build  

**Verify**:
```bash
cd src && python -c "from storage.service import StorageService; from storage.dependencies import StorageDep; print('OK')"
```

---

#### T8: Criar config embeddings (embeddings/config.py) [P]

**What**: BaseSettings para embeddings (OpenAI)  
**Where**: `src/embeddings/config.py`  
**Depends on**: T5  
**Reuses**: Variáveis de `my_agent/config/settings.py`  
**Requirement**: REFAC-10, REFAC-14

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `EmbeddingsConfig(BaseSettings)` criado
- [ ] `env_prefix="EMBEDDINGS_"`
- [ ] Variáveis: `OPENAI_API_KEY`, `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS`, `BATCH_SIZE`, `REQUEST_TIMEOUT`

**Tests**: none  
**Gate**: build  

**Verify**:
```bash
cd src && python -c "from embeddings.config import EmbeddingsConfig; c = EmbeddingsConfig(); print(c.EMBEDDING_MODEL)"
```

---

#### T9: Migrar serviço embeddings (embeddings/service.py)

**What**: Mover código de `services/embeddings/generator.py`  
**Where**: `src/embeddings/service.py`  
**Depends on**: T8  
**Reuses**: Código de `services/embeddings/generator.py`  
**Requirement**: REFAC-26

**Tools**:
- MCP: filesystem
- Skill: NONE

**Done when**:
- [ ] `EmbeddingsService` classe criada
- [ ] Métodos: `generate_embeddings`, `generate_single`
- [ ] Usa `EmbeddingsConfig` para config
- [ ] Batch processing preservado
- [ ] `EmbeddingsDep` em `dependencies.py`

**Tests**: none  
**Gate**: build  

**Verify**:
```bash
cd src && python -c "from embeddings.service import EmbeddingsService; from embeddings.dependencies import EmbeddingsDep; print('OK')"
```

---

#### T10: Criar config extractors (extractors/config.py) [P]

**What**: Configuração para extractors (se necessário)  
**Where**: `src/extractors/config.py`  
**Depends on**: T5  
**Reuses**: Padrão de outros domínios  
**Requirement**: REFAC-10

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `ExtractorsConfig(BaseSettings)` criado (se houver variáveis específicas)
- [ ] Ou arquivo vazio/omitido se não houver config específica

**Tests**: none  
**Gate**: build  

**Verify**:
```bash
cd src && python -c "from extractors.config import ExtractorsConfig; print('OK')"
```

---

#### T11: Migrar extractors (extractors/)

**What**: Mover código de `services/extractors/*.py` para `src/extractors/`  
**Where**: `src/extractors/{base,pdf,docx,xlsx,service}.py`  
**Depends on**: T10  
**Reuses**: Todo código de `services/extractors/`  
**Requirement**: REFAC-26, REFAC-28

**Tools**:
- MCP: filesystem
- Skill: NONE

**Done when**:
- [ ] `base.py` com `TextExtractor` ABC
- [ ] `pdf.py` com `PDFExtractor`
- [ ] `docx.py` com `DocxExtractor`
- [ ] `xlsx.py` com `XlsxExtractor`
- [ ] `service.py` com `ExtractionService` unificado
- [ ] `ExtractionDep` em `dependencies.py`
- [ ] Imports ajustados para novo path

**Tests**: none  
**Gate**: build  

**Verify**:
```bash
cd src && python -c "from extractors.service import ExtractionService; from extractors.pdf import PDFExtractor; print('OK')"
```

---

#### T12: Criar config chunking (chunking/config.py) [P]

**What**: Configuração para chunking  
**Where**: `src/chunking/config.py`  
**Depends on**: T5  
**Reuses**: Padrão de outros domínios  
**Requirement**: REFAC-10

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `ChunkingConfig(BaseSettings)` criado
- [ ] `env_prefix="CHUNKING_"`
- [ ] Variáveis: `DEFAULT_CHUNK_SIZE`, `DEFAULT_CHUNK_OVERLAP`

**Tests**: none  
**Gate**: build  

**Verify**:
```bash
cd src && python -c "from chunking.config import ChunkingConfig; c = ChunkingConfig(); print(c.DEFAULT_CHUNK_SIZE)"
```

---

#### T13: Migrar serviço chunking (chunking/service.py)

**What**: Mover código de `services/chunking/legal_chunker.py`  
**Where**: `src/chunking/service.py`  
**Depends on**: T12  
**Reuses**: Código de `services/chunking/legal_chunker.py`  
**Requirement**: REFAC-26

**Tools**:
- MCP: filesystem
- Skill: NONE

**Done when**:
- [ ] `ChunkingService` classe criada
- [ ] Método: `chunk_document(text, metadata, ...)`
- [ ] Usa `ChunkingConfig` para defaults
- [ ] `ChunkingDep` em `dependencies.py`
- [ ] Preserva lógica de chunking jurídico

**Tests**: none  
**Gate**: build  

**Verify**:
```bash
cd src && python -c "from chunking.service import ChunkingService; from chunking.dependencies import ChunkingDep; print('OK')"
```

---

### Phase 3: Domínios Dependentes

#### T14: Criar config documents (documents/config.py)

**What**: BaseSettings para documents  
**Where**: `src/documents/config.py`  
**Depends on**: T5  
**Reuses**: Valores de hardcoded em rotas atuais  
**Requirement**: REFAC-10, REFAC-14

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `DocumentsConfig(BaseSettings)` criado
- [ ] `env_prefix="DOCUMENTS_"`
- [ ] Variáveis: `MAX_FILE_SIZE`, `ALLOWED_EXTENSIONS`, `PROCESSING_TIMEOUT_SECONDS`

**Tests**: none  
**Gate**: build  

**Verify**:
```bash
cd src && python -c "from documents.config import DocumentsConfig; c = DocumentsConfig(); print(c.ALLOWED_EXTENSIONS)"
```

---

#### T15: Criar models SQLAlchemy documents (documents/models.py)

**What**: SQLAlchemy ORM models para Document e Chunk  
**Where**: `src/documents/models.py`  
**Depends on**: T3, T14  
**Reuses**: Estrutura de `services/db/repositories.py` (classes Pydantic)  
**Requirement**: REFAC-15, REFAC-16, REFAC-17, REFAC-18, REFAC-19, REFAC-20

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `class Document(Base)` com todos os campos
- [ ] `class Chunk(Base)` com todos os campos
- [ ] Nomes de tabela em singular: `document`, `chunk`
- [ ] FK: `chunk.document_id` → `document.id`
- [ ] Campos datetime com sufixo `_at`: `created_at`, `updated_at`, `processed_at`
- [ ] Índices: `user_id` indexado (RLS)
- [ ] Coluna `embedding` como `Vector(1536)` (pgvector)

**Tests**: none  
**Gate**: build  

**Verify**:
```bash
cd src && python -c "from documents.models import Document, Chunk; print(Document.__tablename__, Chunk.__tablename__)"
```

---

#### T16: Migrar router documents com Annotated Depends (documents/router.py)

**What**: Mover e modernizar rotas de `api/routes/documents.py`  
**Where**: `src/documents/router.py`  
**Depends on**: T7, T9, T11, T13, T15  
**Reuses**: Código de `api/routes/documents.py` e `services/document_processor.py`  
**Requirement**: REFAC-06, REFAC-07, REFAC-08, REFAC-09, REFAC-26, REFAC-27, REFAC-28, REFAC-29, REFAC-30

**Tools**:
- MCP: filesystem
- Skill: NONE

**Done when**:
- [ ] Router criado: `router = APIRouter(prefix="/documents", tags=["documents"])`
- [ ] `POST /upload` com `Annotated[..., Depends(...)]` para: `storage`, `db`, `background_tasks`
- [ ] `GET /{id}/status` com `DocumentDep` (dependency que valida e retorna doc)
- [ ] `GET /` com `DbDep`, paginação
- [ ] `DELETE /{id}` com `DocumentDep`, `StorageDep`
- [ ] Nenhuma rota usa `= Depends(...)` formato legado
- [ ] `DocumentDep = Annotated[Document, Depends(valid_document_id)]` em `dependencies.py`
- [ ] `valid_document_id` valida existência e ownership
- [ ] Todos os schemas usam `CustomModel` base

**Tests**: none  
**Gate**: build  

**Verify**:
```bash
# Verificar formato Annotated
grep -n "Annotated\[" src/documents/router.py | head -5
grep -n "= Depends" src/documents/router.py  # Deve retornar vazio ou só em Annotated

# Verificar schemas
python -c "from documents.schemas import UploadResponse; from common.models import CustomModel; assert issubclass(UploadResponse, CustomModel)"
```

---

#### T17: Criar schemas documents (documents/schemas.py)

**What**: Pydantic schemas para request/response  
**Where**: `src/documents/schemas.py`  
**Depends on**: T4, T14  
**Reuses**: Modelos de `api/models.py`  
**Requirement**: REFAC-31, REFAC-32

**Tools**:
- MCP: filesystem
- Skill: NONE

**Done when**:
- [ ] `UploadResponse` herda de `CustomModel`
- [ ] `DocumentStatusResponse` com todos os campos
- [ ] `DocumentSummary` para listagem
- [ ] `DocumentListResponse` com paginação
- [ ] Nenhum uso de `json_encoders` (deprecated)
- [ ] Uso de `@field_serializer` se necessário

**Tests**: none  
**Gate**: build  

**Verify**:
```bash
cd src && python -c "from documents.schemas import UploadResponse, DocumentStatusResponse, DocumentListResponse; print('OK')"
```

---

#### T18: Migrar domínio agents (agents/)

**What**: Mover e adaptar todo `my_agent/` para `src/agents/`  
**Where**: `src/agents/` (todos os arquivos)  
**Depends on**: T5, T16 (para patterns de router)  
**Reuses**: Todo código de `my_agent/`  
**Requirement**: REFAC-02, REFAC-06, REFAC-10, REFAC-26

**Tools**:
- MCP: filesystem
- Skill: NONE

**Done when**:
- [ ] `agents/config.py` com `AgentsConfig(BaseSettings)` (env_prefix="AGENTS_")
- [ ] `agents/router.py` com endpoints de query (se exposto via API)
- [ ] `agents/schemas.py` com request/response models
- [ ] `agents/graph.py`, `agents/state.py`, `agents/registry.py` migrados
- [ ] `agents/nodes/` todos os nodes migrados
- [ ] `agents/retrievers/` todos os retrievers migrados
- [ ] `agents/rerankers/` todos os rerankers migrados
- [ ] Imports atualizados para novo path
- [ ] Se houver API endpoints, usar `Annotated[...]` pattern

**Tests**: none  
**Gate**: build  

**Verify**:
```bash
cd src && python -c "from agents.graph import create_graph; from agents.config import AgentsConfig; print('OK')"
```

---

### Phase 4: Main e Integração

#### T19: Criar main.py com lifespan e routers

**What**: Ponto de entrada FastAPI com todos os routers  
**Where**: `src/main.py`  
**Depends on**: T16, T18  
**Reuses**: Código de `api/main.py` (adaptado)  
**Requirement**: REFAC-01

**Tools**:
- MCP: filesystem
- Skill: NONE

**Done when**:
- [ ] `create_app()` factory function
- [ ] Lifespan context manager (startup/shutdown)
- [ ] CORS middleware para Streamlit (port 8501)
- [ ] Include routers: `app.include_router(documents.router, prefix="/api/v1")`
- [ ] Health check endpoint: `GET /health`
- [ ] Global exception handlers usando `common.exceptions`
- [ ] `SHOW_DOCS_IN` logic para desabilitar docs em prod

**Tests**: none  
**Gate**: build  

**Verify**:
```bash
cd src && python -c "from main import create_app; app = create_app(); print('OK')"
```

---

#### T20: Criar pyproject.toml atualizado (ou requirements)

**What**: Atualizar configuração de projeto para nova estrutura  
**Where**: `pyproject.toml` (atualizar)  
**Depends on**: T19  
**Reuses**: `pyproject.toml` existente  
**Requirement**: REFAC-01

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] Seção `[tool.setuptools.packages.find]` aponta para `src`
- [ ] Ou `package-dir = {"" = "src"}` configurado
- [ ] Imports funcionam: `from src.documents.router import router`

**Tests**: none  
**Gate**: build  

**Verify**:
```bash
python -c "from src.main import create_app; print('Imports OK')"
```

---

#### T21: Testar end-to-end upload de documento

**What**: Teste manual completo do fluxo de upload  
**Where**: N/A (teste manual)  
**Depends on**: T20  
**Reuses**: Testes manuais existentes  
**Requirement**: REFAC-05 (Success Criteria)

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] API inicia sem erros: `python -m uvicorn src.main:app --reload`
- [ ] `GET /health` retorna 200
- [ ] `POST /api/v1/documents/upload` aceita PDF
- [ ] Status retorna "processing" ou "ready"
- [ ] Listagem funciona: `GET /api/v1/documents/`
- [ ] Deleção funciona: `DELETE /api/v1/documents/{id}`

**Tests**: e2e  
**Gate**: full  

**Verify**:
```bash
# Terminal 1
cd d:\Cursos\TI\Projetos\Agentic RAG && python -m uvicorn src.main:create_app --factory --reload

# Terminal 2
curl http://localhost:8000/health
curl -X POST -F "file=@test.pdf" http://localhost:8000/api/v1/documents/upload
curl http://localhost:8000/api/v1/documents/
```

---

#### T22: Validar código com ruff (parallel com T21)

**What**: Linting com ruff para garantir padrões  
**Where**: Todo `src/`  
**Depends on**: T20  
**Reuses**: N/A  
**Requirement**: REFAC-06, REFAC-31

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] `ruff check src` passa sem erros
- [ ] `ruff format src` aplicado
- [ ] Nenhum import não usado
- [ ] Nenhum padrão `= Depends(...)` legado detectado
- [ ] Nenhum `json_encoders` deprecated detectado

**Tests**: none  
**Gate**: build  

**Verify**:
```bash
ruff check src
ruff format src --check
```

---

### Phase 5: Limpeza e Validação

#### T23: Remover código antigo (backup first)

**What**: Remover pastas antigas após validação  
**Where**: `api/`, `services/`, `my_agent/` (remover)  
**Depends on**: T21, T22  
**Reuses**: N/A (limpeza)  
**Requirement**: REFAC-05

**Tools**:
- MCP: filesystem
- Skill: NONE

**Done when**:
- [ ] Backup criado (ou commit git feito)
- [ ] `api/` removido (exceto se `frontend/` depender - verificar)
- [ ] `services/` removido
- [ ] `my_agent/` removido
- [ ] `vector_store/` avaliado (mover para `src/` se necessário)
- [ ] `document_loaders/` avaliado (mover para `src/extractors/` se necessário)
- [ ] Aplicação continua funcionando após remoção

**Tests**: e2e  
**Gate**: full  

**Verify**:
```bash
# Verificar que não há imports quebrados
python -c "from src.main import create_app; app = create_app(); print('OK')"

# Verificar estrutura
ls -la src/
```

---

#### T24: Atualizar README com nova estrutura

**What**: Documentar nova estrutura de projeto  
**Where**: `README.md`  
**Depends on**: T23  
**Reuses**: README existente  
**Requirement**: REFAC-01

**Tools**:
- MCP: NONE
- Skill: NONE

**Done when**:
- [ ] Seção "Project Structure" atualizada
- [ ] Explicação da organização por domínio
- [ ] Exemplos de imports: `from src.documents import service as documents_service`
- [ ] Instruções de execução atualizadas

**Tests**: none  
**Gate**: build  

**Verify**:
```bash
cat README.md | grep -A 20 "Project Structure"
```

---

## Parallel Execution Map

```
Phase 1 (Sequential - Foundation):
  T1 ──→ T2 ──→ T3 ──→ T4 ──→ T5
       
       Após T5 completo:

Phase 2 (Parallel - Independent Domains):
                    ┌→ T6 ──→ T7  [storage]
                    │
                    ├→ T8 ──→ T9  [embeddings]
                    │
                    ├→ T10 ─→ T11 [extractors]
                    │
                    └→ T12 ─→ T13 [chunking]

       Após T7, T9, T11, T13 completos:

Phase 3 (Sequential - Dependent Domains):
  T14 ──→ T15 ──→ T16 ──→ T17
                 │
                 └──→ T18 [agents]

       Após T17, T18 completos:

Phase 4 (Sequential + Parallel):
  T19 ──→ T20 ──→ T21 (end-to-end test)
                 │
                 └──→ T22 [P] (ruff check - parallel com T21)

       Após T21, T22 completos:

Phase 5 (Sequential):
  T23 ──→ T24
```

---

## Task Granularity Check

| Task | Scope | Status |
|------|-------|--------|
| T1: Criar estrutura src/ | Múltiplas pastas (estrutura) | ⚠️ OK - estruturação inicial necessária |
| T2: Common config | 1 arquivo | ✅ Granular |
| T3: Database | 1 arquivo | ✅ Granular |
| T4: Models base | 1 arquivo | ✅ Granular |
| T5: Exceptions | 1 arquivo | ✅ Granular |
| T6: Storage config | 1 arquivo | ✅ Granular |
| T7: Storage service | 1 arquivo | ✅ Granular |
| T8: Embeddings config | 1 arquivo | ✅ Granular |
| T9: Embeddings service | 1 arquivo | ✅ Granular |
| T10: Extractors config | 1 arquivo | ✅ Granular |
| T11: Extractors migrate | Múltiplos arquivos | ⚠️ OK - domínio coeso |
| T12: Chunking config | 1 arquivo | ✅ Granular |
| T13: Chunking service | 1 arquivo | ✅ Granular |
| T14: Documents config | 1 arquivo | ✅ Granular |
| T15: Documents models | 1 arquivo | ✅ Granular |
| T16: Documents router | 1 arquivo (complexo) | ⚠️ OK - router completo |
| T17: Documents schemas | 1 arquivo | ✅ Granular |
| T18: Agents migrate | Múltiplos arquivos | ⚠️ OK - domínio inteiro |
| T19: Main app | 1 arquivo | ✅ Granular |
| T20: pyproject.toml | 1 arquivo | ✅ Granular |
| T21: E2E test | N/A (teste) | ✅ Granular |
| T22: Ruff check | N/A (check) | ✅ Granular |
| T23: Cleanup | N/A (cleanup) | ✅ Granular |
| T24: README | 1 arquivo | ✅ Granular |

---

## Diagram-Definition Cross-Check

| Task | Depends On (task body) | Diagram Shows | Status |
|------|------------------------|---------------|--------|
| T1 | None | Start | ✅ Match |
| T2 | T1 | After T1 | ✅ Match |
| T3 | T1, T2 | After T2 | ✅ Match |
| T4 | T1 | After T3 | ✅ Match |
| T5 | T1 | After T4 | ✅ Match |
| T6 | T5 | Parallel after T5 | ✅ Match |
| T7 | T6 | After T6 | ✅ Match |
| T8 | T5 | Parallel after T5 | ✅ Match |
| T9 | T8 | After T8 | ✅ Match |
| T10 | T5 | Parallel after T5 | ✅ Match |
| T11 | T10 | After T10 | ✅ Match |
| T12 | T5 | Parallel after T5 | ✅ Match |
| T13 | T12 | After T12 | ✅ Match |
| T14 | T5 | After T5 | ✅ Match |
| T15 | T3, T14 | After T14 | ✅ Match |
| T16 | T7, T9, T11, T13, T15 | After T15 | ✅ Match |
| T17 | T4, T14 | After T15 | ✅ Match |
| T18 | T5, T16 | After T16 | ✅ Match |
| T19 | T16, T18 | After T18 | ✅ Match |
| T20 | T19 | After T19 | ✅ Match |
| T21 | T20 | After T20 | ✅ Match |
| T22 | T20 | Parallel with T21 | ✅ Match |
| T23 | T21, T22 | After T21, T22 | ✅ Match |
| T24 | T23 | After T23 | ✅ Match |

---

## Test Co-location Validation

| Task | Code Layer Created/Modified | Matrix Requires | Task Says | Status |
|------|---------------------------|-----------------|-----------|--------|
| T1-T20 | Setup/Infrastructure | none | none | ✅ OK |
| T21 | End-to-end flow | e2e | e2e | ✅ OK |
| T22 | Linting | none | none | ✅ OK |
| T23 | Cleanup | e2e | e2e | ✅ OK |
| T24 | Docs | none | none | ✅ OK |

---

## Commit Message Format

Cada task deve ter um commit atômico:

```
feat(refactor): T{N} - {descrição breve}

- Detalhe 1
- Detalhe 2

Refs: REFAC-{XX}, REFAC-{YY}
```

Exemplos:
- `feat(refactor): T1 - create src/ directory structure`
- `feat(refactor): T3 - add common/database.py with SQLAlchemy async`
- `feat(refactor): T16 - migrate documents router with Annotated Depends`
- `feat(refactor): T21 - validate end-to-end document upload`
