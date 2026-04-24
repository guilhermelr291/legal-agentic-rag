-- Migration: Document Ingestion Schema
-- Description: Creates tables for document ingestion with vector RAG and graph RAG support
-- Requirements: INGEST-03, INGEST-08

-- Enable pgvector extension for embedding storage
CREATE EXTENSION IF NOT EXISTS vector;

-- Documents table: Stores metadata for uploaded files
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id),
    filename TEXT NOT NULL,
    file_type TEXT NOT NULL CHECK (file_type IN ('pdf', 'docx', 'xlsx')),
    file_size INT NOT NULL,
    storage_path TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('processing', 'ready', 'failed')),
    error_msg TEXT,
    meta JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Row Level Security: Users can only access their own documents
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can only access their own documents"
    ON documents FOR ALL
    USING (user_id = auth.uid());

-- Chunks table: Stores text chunks with vector embeddings for RAG
CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    embedding VECTOR(1536),
    section_hint TEXT,
    section_path TEXT[],
    page_start INT,
    page_end INT,
    anchors TEXT[],
    char_start INT,
    char_end INT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (document_id, chunk_index)
);

-- Row Level Security: Users can only access their own chunks
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can only access their own chunks"
    ON chunks FOR ALL
    USING (user_id = auth.uid());

-- Graph nodes table: Stores entities for Graph RAG
CREATE TABLE graph_nodes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    node_type TEXT NOT NULL,
    label TEXT NOT NULL,
    properties JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Row Level Security: Users can only access their own graph nodes
ALTER TABLE graph_nodes ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can only access their own graph nodes"
    ON graph_nodes FOR ALL
    USING (user_id = auth.uid());

-- Graph edges table: Stores relationships between entities
CREATE TABLE graph_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id UUID NOT NULL,
    source_node_id UUID NOT NULL REFERENCES graph_nodes(id) ON DELETE CASCADE,
    target_node_id UUID NOT NULL REFERENCES graph_nodes(id) ON DELETE CASCADE,
    edge_type TEXT NOT NULL,
    evidence JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Row Level Security: Users can only access their own graph edges
ALTER TABLE graph_edges ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can only access their own graph edges"
    ON graph_edges FOR ALL
    USING (user_id = auth.uid());

-- Indexes for performance optimization

-- Document lookup by user
CREATE INDEX idx_documents_user_id ON documents(user_id);

-- Document status filtering
CREATE INDEX idx_documents_status ON documents(status);

-- Chunk lookup by document
CREATE INDEX idx_chunks_document_id ON chunks(document_id);

-- Vector similarity search index using IVFFlat
CREATE INDEX idx_chunks_embedding ON chunks USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Graph node lookup by document
CREATE INDEX idx_graph_nodes_document_id ON graph_nodes(document_id);

-- Graph node type filtering
CREATE INDEX idx_graph_nodes_type ON graph_nodes(node_type);

-- Graph edge lookup by document
CREATE INDEX idx_graph_edges_document_id ON graph_edges(document_id);

-- Graph edge lookup by source/target nodes
CREATE INDEX idx_graph_edges_source ON graph_edges(source_node_id);
CREATE INDEX idx_graph_edges_target ON graph_edges(target_node_id);

-- Trigger function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at trigger to documents table
CREATE TRIGGER update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Comment on tables for documentation
COMMENT ON TABLE documents IS 'Stores metadata for uploaded legal documents (PDF, DOCX, XLSX)';
COMMENT ON TABLE chunks IS 'Stores text chunks with embeddings for vector RAG retrieval';
COMMENT ON TABLE graph_nodes IS 'Stores extracted entities for Graph RAG';
COMMENT ON TABLE graph_edges IS 'Stores relationships between entities with evidence';
