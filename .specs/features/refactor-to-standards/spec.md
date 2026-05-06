# Especificação: Refatoração para Padrões FastAPI

## Problem Statement

O projeto atual possui uma estrutura organizada por tipo de arquivo (api/, services/, my_agent/) que funciona, mas não segue as melhores práticas do FastAPI para projetos em escala. A manutenção e evolução do código estão ficando mais difíceis à medida que o projeto cresce.

Problemas identificados:
- Estrutura não organizada por domínio (bounded contexts)
- Uso de `Depends()` no formato legado (default-arg) ao invés de `Annotated[T, Depends(...)]`
- Configuração centralizada em um único arquivo ao invés de `BaseSettings` por domínio
- Possíveis imports não explícitos entre domínios
- Falta de convenções de naming para SQLAlchemy
- Estrutura de imports não segue o padrão `from src.auth import service as auth_service`

## Goals

- [ ] Reorganizar projeto em estrutura por domínio (`src/{domain}/`)
- [ ] Modernizar uso de dependências para padrão `Annotated[T, Depends(...)]`
- [ ] Implementar `BaseSettings` por domínio
- [ ] Aplicar convenções de naming SQLAlchemy
- [ ] Garantir async/await correto em todas as rotas
- [ ] Padronizar imports cross-domain
- [ ] Manter 100% de compatibilidade funcional (nenhum comportamento alterado)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Mudança de tecnologia (trocar FastAPI, banco, etc) | Refatoração estrutural apenas |
| Adicionar novas funcionalidades | Manter escopo apenas em reorganização |
| Alterar lógica de negócio | Manter comportamento idêntico |
| Otimização de performance | Foco em estrutura, não performance |
| Documentação de API além do padrão FastAPI | Usar OpenAPI automático |

---

## User Stories

### P1: Reestruturação por Domínio (Bounded Contexts) ⭐ MVP

**User Story**: Como desenvolvedor, quero que o código seja organizado por domínio de negócio para facilitar manutenção e onboarding.

**Why P1**: A estrutura atual mistura responsabilidades. Separar por domínio (documents, agents, storage, embeddings, etc) torna o código mais coeso.

**Acceptance Criteria**:

1. WHEN o projeto for reestruturado THEN cada domínio SHALL ter sua própria pasta em `src/{domain}/`
2. WHEN um domínio for criado THEN ele SHALL conter: `router.py`, `schemas.py`, `service.py`, `dependencies.py`, `config.py`, `constants.py`, `exceptions.py`
3. WHEN os domínios forem definidos THEN eles SHALL ser: `documents`, `agents`, `storage`, `embeddings`, `chunking`, `extractors`, `graph`, `common` (shared)
4. WHEN houver código compartilhado THEN ele SHALL ficar em `src/common/` (database, config global, base models)
5. WHEN o projeto for executado após refatoração THEN todos os endpoints SHALL responder identicamente à versão anterior

**Independent Test**: Subir a aplicação e verificar que `/health`, `/api/v1/documents/*` funcionam; verificar que documentos podem ser uploadados e processados.

---

### P1: Modernização de Dependências FastAPI ⭐ MVP

**User Story**: Como desenvolvedor, quero usar o padrão moderno de injeção de dependências para evitar bugs com defaults.

**Why P1**: O padrão `def func(dep = Depends(x))` é legado e tem problemas com valores default. O padrão `Annotated[T, Depends(x)]` é o idioma moderno FastAPI 0.95+.

**Acceptance Criteria**:

1. WHEN houver injeção de dependência THEN ela SHALL usar `Annotated[T, Depends(...)]` format
2. WHEN houver dependency aliases THEN eles SHALL seguir padrão `PostDep = Annotated[dict, Depends(valid_post_id)]`
3. WHEN uma rota precisar de dependência THEN não SHALL haver uso de `= Depends(...)` como default argument
4. WHEN todas as rotas forem atualizadas THEN nenhuma rota SHALL usar o formato legado

**Independent Test**: Verificar que todas as rotas em `src/documents/router.py` usam `Annotated`; verificar que `ruff` não reporta patterns legados.

---

### P1: BaseSettings por Domínio ⭐ MVP

**User Story**: Como desenvolvedor, quero que cada domínio tenha suas próprias configurações isoladas para melhor coesão.

**Why P1**: Uma configuração global enorme viola o princípio de responsabilidade única. Cada domínio deve gerenciar apenas suas variáveis.

**Acceptance Criteria**:

1. WHEN um domínio precisar de config THEN ele SHALL ter seu próprio `config.py` com `BaseSettings`
2. WHEN houver variável específica de domínio THEN ela SHALL estar no `BaseSettings` daquele domínio
3. WHEN houver config global THEN ela SHALL ficar em `src/common/config.py`
4. WHEN as configs forem acessadas THEN o padrão SHALL ser `{domain}_settings = {Domain}Config()`
5. WHEN variáveis de ambiente forem carregadas THEN elas SHALL respeitar `env_prefix` por domínio (ex: `DOCUMENTS_`, `AGENTS_`, `STORAGE_`)

**Independent Test**: Cada config pode ser instanciada isoladamente; variáveis de ambiente com prefixos corretos são lidas.

---

### P1: Convenções SQLAlchemy e Naming ⭐ MVP

**User Story**: Como desenvolvedor, quero convenções claras de naming para banco de dados para facilitar manutenção.

**Why P1**: Nomes inconsistentes dificultam queries manuais e entendimento do schema.

**Acceptance Criteria**:

1. WHEN tabelas forem criadas THEN elas SHALL usar `lower_case_snake` e singular (ex: `document`, `chunk`)
2. WHEN houver FKs THEN elas SHALL ter nome consistente (ex: `document_id` em todas as tabelas)
3. WHEN houver timestamps THEN eles SHALL usar sufixo `_at` (ex: `created_at`, `updated_at`)
4. WHEN houver datas (sem hora) THEN elas SHALL usar sufixo `_date`
5. WHEN metadata SQLAlchemy for configurado THEN ele SHALL usar `POSTGRES_INDEXES_NAMING_CONVENTION`
6. WHEN índices forem criados THEN eles SHALL seguir o padrão: `ix: %(column_0_label)s_idx`, `uq: %(table_name)s_%(column_0_name)s_key`

**Independent Test**: Verificar schema gerado tem naming consistente; índices seguem convenção.

---

### P2: Async Patterns Corretos

**User Story**: Como desenvolvedor, quero garantir que código async não bloqueie o event loop.

**Why P2**: Código async com chamadas bloqueantes (time.sleep, requests.get, etc) dentro de `async def` congela todo o event loop.

**Acceptance Criteria**:

1. WHEN uma rota fizer I/O não-bloqueante THEN ela SHALL usar `async def` + `await`
2. WHEN uma rota fizer I/O bloqueante (sem cliente async) THEN ela SHALL usar `def` (sync, roda em threadpool)
3. WHEN houver mix de I/O THEN a rota SHALL usar `async def` + `run_in_threadpool` para parte bloqueante
4. WHEN não houver I/O (apenas CPU leve) THEN a rota pode usar `def` ou `async def`
5. WHEN houver chamada sync dentro de async THEN ela SHALL usar `await run_in_threadpool(fn, *args)`

**Independent Test**: Aplicação mantém throughput similar; não há chamadas bloqueantes dentro de `async def`.

---

### P2: Padronização de Imports Cross-Domain

**User Story**: Como desenvolvedor, quero imports cross-domain explícitos para evitar circular dependencies.

**Why P2**: Imports via deep paths (`from src.auth.service.user import ...`) criam acoplamento forte. O padrão do projeto é importar módulos completos.

**Acceptance Criteria**:

1. WHEN importar de outro domínio THEN o import SHALL ser `from src.{domain} import service as {domain}_service`
2. WHEN importar constantes de outro domínio THEN o import SHALL ser `from src.{domain} import constants as {domain}_constants`
3. WHEN importar schemas de outro domínio THEN o import SHALL ser `from src.{domain} import schemas as {domain}_schemas`
4. WHEN houver import wildcard (`*`) THEN ele SHALL ser removido (exceto em `__init__.py` de propósito)
5. WHEN houver import absoluto de arquivo específico THEN ele SHALL ser convertido para import de módulo

**Independent Test**: Não há imports do tipo `from src.x.y.z import specific_func`; todos usam alias de módulo.

---

### P3: Modernização Pydantic v2

**User Story**: Como desenvolvedor, quero usar patterns Pydantic v2 modernos para evitar deprecations.

**Why P3**: `json_encoders` é deprecated em Pydantic v2. Usar `@field_serializer` é o padrão moderno.

**Acceptance Criteria**:

1. WHEN houver `model_config = ConfigDict(json_encoders=...)` THEN ele SHALL ser convertido para `@field_serializer`
2. WHEN houver serialização customizada de datetime THEN ela SHALL usar `@field_serializer` com `when_used="json"`
3. WHEN houver `Field(ge=18, default=None)` THEN ele SHALL ser corrigido (contradiction entre constraint e default)
4. WHEN todos os schemas forem verificados THEN nenhum SHALL usar API deprecated do Pydantic v1

**Independent Test**: Pydantic não emite deprecation warnings; `ruff` não reporta issues de Pydantic.

---

## Edge Cases

- WHEN um arquivo não couber em nenhum domínio claro THEN ele SHALL ir para `src/common/`
- WHEN houver código morto (não importado por ninguém) durante refatoração THEN ele SHALL ser documentado e removido se confirmado
- WHEN dois domínios precisarem compartilhar o mesmo modelo THEN o modelo SHALL ir para `src/common/schemas.py` ou `src/common/models.py`
- WHEN uma dependência tiver cadeia complexa THEN a cadeia SHALL ser preservada com `Annotated` encadeado
- WHEN um domínio tiver múltiplos sub-componentes (ex: agents com nodes, retrievers, rerankers) THEN eles SHALL ser sub-pastas do domínio

---

## Requirement Traceability

| Requirement ID | Story | Phase | Status |
| -------------- | ----------- | ------ | ------ |
| REFAC-01 | P1: Reestruturação por Domínio | Design | Pending |
| REFAC-02 | P1: Reestruturação por Domínio | Design | Pending |
| REFAC-03 | P1: Reestruturação por Domínio | Design | Pending |
| REFAC-04 | P1: Reestruturação por Domínio | Design | Pending |
| REFAC-05 | P1: Reestruturação por Domínio | Design | Pending |
| REFAC-06 | P1: Modernização de Dependências | Design | Pending |
| REFAC-07 | P1: Modernização de Dependências | Design | Pending |
| REFAC-08 | P1: Modernização de Dependências | Design | Pending |
| REFAC-09 | P1: Modernização de Dependências | Design | Pending |
| REFAC-10 | P1: BaseSettings por Domínio | Design | Pending |
| REFAC-11 | P1: BaseSettings por Domínio | Design | Pending |
| REFAC-12 | P1: BaseSettings por Domínio | Design | Pending |
| REFAC-13 | P1: BaseSettings por Domínio | Design | Pending |
| REFAC-14 | P1: BaseSettings por Domínio | Design | Pending |
| REFAC-15 | P1: Convenções SQLAlchemy | Design | Pending |
| REFAC-16 | P1: Convenções SQLAlchemy | Design | Pending |
| REFAC-17 | P1: Convenções SQLAlchemy | Design | Pending |
| REFAC-18 | P1: Convenções SQLAlchemy | Design | Pending |
| REFAC-19 | P1: Convenções SQLAlchemy | Design | Pending |
| REFAC-20 | P1: Convenções SQLAlchemy | Design | Pending |
| REFAC-21 | P2: Async Patterns | Design | Pending |
| REFAC-22 | P2: Async Patterns | Design | Pending |
| REFAC-23 | P2: Async Patterns | Design | Pending |
| REFAC-24 | P2: Async Patterns | Design | Pending |
| REFAC-25 | P2: Async Patterns | Design | Pending |
| REFAC-26 | P2: Padronização de Imports | Design | Pending |
| REFAC-27 | P2: Padronização de Imports | Design | Pending |
| REFAC-28 | P2: Padronização de Imports | Design | Pending |
| REFAC-29 | P2: Padronização de Imports | Design | Pending |
| REFAC-30 | P2: Padronização de Imports | Design | Pending |
| REFAC-31 | P3: Modernização Pydantic | Design | Pending |
| REFAC-32 | P3: Modernização Pydantic | Design | Pending |
| REFAC-33 | P3: Modernização Pydantic | Design | Pending |
| REFAC-34 | P3: Modernização Pydantic | Design | Pending |

**Coverage:** 34 total, 0 mapped to tasks, 34 unmapped

---

## Success Criteria

- [ ] Aplicação inicia sem erros com nova estrutura
- [ ] Todos os endpoints documentados respondem identicamente
- [ ] Upload de documentos funciona (fluxo end-to-end)
- [ ] Processamento de documentos (chunking, embeddings) funciona
- [ ] Consulta ao agente RAG retorna resultados equivalentes
- [ ] `ruff check src` passa sem erros
- [ ] Nenhum warning de deprecation do Pydantic
- [ ] Testes (se existirem) passam
