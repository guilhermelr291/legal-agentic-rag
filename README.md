# Legal Agentic RAG

An intelligent document analysis system powered by Retrieval-Augmented Generation (RAG) for legal documents. This project combines Vector RAG and Graph RAG techniques to enable advanced document querying and multi-hop reasoning across legal contracts.

## Overview

Legal Agentic RAG is designed to process, index, and query legal documents (PDF, DOCX, XLSX) through an intelligent agent interface. The system extracts semantic meaning from documents using vector embeddings while building a knowledge graph to capture relationships between entities, enabling sophisticated question answering across document collections.

> **Current Status:** This project is under active development. The current phase focuses on document ingestion and processing. Future phases will implement the conversational chatbot interface with full RAG capabilities.

## Features (Current & Planned)

### Phase 1: Document Ingestion (In Progress)

- **Multi-format Support:** Upload and process PDF, DOCX, and XLSX files
- **Legal-first Chunking:** Structure-preserving text segmentation optimized for legal documents (sections, clauses, articles)
- **Vector Embeddings:** OpenAI `text-embedding-3-small` for semantic search
- **XLSX Metadata Extraction:** Structured extraction of sheet names and column headers
- **Processing Pipeline:** Async background processing with status tracking
- **Storage:** Supabase for file storage and vector database

### Phase 2+: Agent & Chatbot (Planned)

- **Conversational Interface:** Streamlit-based chat for document Q&A
- **Hybrid RAG Retrieval:** Combine vector similarity with graph traversal
- **Multi-hop Reasoning:** Answer complex questions requiring connections across multiple documents
- **Entity-aware Responses:** Leverage extracted entities (parties, obligations, deadlines, penalties)

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Streamlit UI  │────▶│   FastAPI Backend  │────▶│  Async Workers  │
│  (Upload/Chat)  │     │   (REST API)       │     │  (Background)   │
└─────────────────┘     └──────────────────┘     └─────────────────┘
                                                        │
        ┌─────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  Supabase       │     │  OpenAI          │     │  Graph Store    │
│  (Storage +     │     │  (Embeddings +   │     │  (Future)       │
│   Vector DB)    │     │   LLM)           │     │                 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

## Tech Stack

- **Frontend:** Streamlit
- **Backend:** FastAPI, Python 3.11+
- **Database:** Supabase (PostgreSQL + pgvector)
- **Embeddings:** OpenAI `text-embedding-3-small`
- **LLM:** OpenAI GPT models
- **Document Processing:**
  - PDF: PyPDFLoader (LangChain)
  - DOCX: python-docx
  - XLSX: openpyxl
- **Package Manager:** uv

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) package manager
- Supabase account
- OpenAI API key

### Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd legal-agentic-rag
```

1. Install dependencies:

```bash
uv sync
```

1. Set up environment variables:

```bash
cp .env.example .env
# Edit .env with your credentials
```

Required environment variables:

- `SUPABASE_URL` - Your Supabase project URL
- `SUPABASE_KEY` - Your Supabase service role key
- `SUPABASE_JWT_SECRET` - JWT secret for token validation
- `OPENAI_API_KEY` - Your OpenAI API key

1. Run the API server:

```bash
uv run python -m api.main
```

1. Run the Streamlit frontend:

```bash
uv run streamlit run frontend/app.py
```

## Document Processing Pipeline

1. **Upload** → File validation and storage in Supabase
2. **Extract** → Text extraction (PDF/DOCX) or metadata extraction (XLSX)
3. **Chunk** → Legal-first segmentation with overlap
4. **Embed** → OpenAI embedding generation (batch: 100 chunks)
5. **Persist** → Upsert to Supabase vector store
6. **Status Update** → Document marked as `ready` for querying

## Project Structure

```
.
├── api/                    # FastAPI backend
│   ├── main.py            # API entry point
│   ├── routes/            # API endpoints
│   └── models.py          # Pydantic models
├── frontend/              # Streamlit application
│   ├── app.py            # Main entry
│   └── pages/            # UI pages
├── services/             # Business logic
│   ├── storage/          # Supabase client
│   ├── extraction/       # Document parsers
│   ├── chunking/         # Text segmentation
│   └── embeddings/       # Vector generation
├── core/                 # RAG agent components
│   ├── state.py          # Graph state definitions
│   ├── nodes/            # LangGraph nodes
│   └── retrievers/       # Vector/Graph retrievers
├── .specs/               # Specifications & planning
│   └── features/         # Feature specifications
└── README.md
```

## Key Concepts

### Vector RAG

Documents are chunked, embedded, and stored in a vector database. Queries are embedded and matched against document chunks using semantic similarity.

### Graph RAG (Planned)

Building on Microsoft's GraphRAG approach, the system will extract entities (parties, clauses, obligations, deadlines) and relationships from documents, creating a knowledge graph that enables:

- Multi-hop reasoning across documents
- Global synthesis questions
- Entity-centric navigation

### Legal-first Chunking

Optimized for legal document structure:

- Preserves sections, clauses, and articles
- Maintains hierarchy (`section_path`)
- Detects references (`anchors`) to other clauses
- Configurable overlap for context preservation

## Development

### Running Tests

```bash
uv run pytest
```

### Code Standards

- Type hints required for all public functions
- Pydantic schemas for structured LLM outputs
- Registry pattern for LLM/Retriever access
- Async operations for parallel processing

## References

- [Microsoft GraphRAG Documentation](https://microsoft.github.io/graphrag/)
- [GraphRAG: From Local to Global (Paper)](https://arxiv.org/abs/2404.16130)
- [LangChain Graph RAG](https://docs.langchain.com/oss/python/integrations/retrievers/graph_rag)

## Roadmap

- Phase 1: Supabase Schema & Setup
- Phase 2: Document Ingestion (Current)
- Phase 3: Agent Retrieval & Chat Interface
- Phase 4: Router & XLSX Tool
- Phase 5: Graph RAG Implementation

