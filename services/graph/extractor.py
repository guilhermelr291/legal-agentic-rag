"""Graph extraction service for Legal Graph RAG.

Extracts entities and relations from document chunks using a hybrid approach:
1. Heuristic extraction: Cheap regex-based reference detection (Clause X, Article Y)
2. LLM extraction: Structured output for parties, obligations, deadlines, etc.

Every edge MUST have evidence or it is dropped. Graph extraction is feature-flagged
to allow graceful degradation when disabled.
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from my_agent.registry import get_llm
from services.chunking.legal_chunker import LegalChunk
from services.graph.models import Evidence, GraphEdge, GraphExtractionResult, GraphNode

logger = logging.getLogger(__name__)

# Constants for heuristic extraction
REFERENCE_PATTERNS = [
    (r"Clause\s+(\d+)(?:\s*\.\s*(\d+))?", "Clause", "REFERENCES"),
    (r"Article\s+(\d+)|Art\.?\s*(\d+)", "Article", "REFERENCES"),
    (r"Annex\s+(\w+)", "Annex", "REFERENCES"),
    (r"Section\s+(\d+)", "Section", "REFERENCES"),
    (r"as\s+per\s+(?:Clause|Article|Annex|Section)\s+(\w+)", "Reference", "REFERENCES"),
    (r"according\s+to\s+(?:Clause|Article|Annex|Section)\s+(\w+)", "Reference", "REFERENCES"),
]

VALID_EDGE_TYPES = {
    "OBLIGATES",
    "HAS_DEADLINE",
    "HAS_AMOUNT",
    "HAS_PENALTY",
    "DEFINES",
    "REFERENCES",
    "EXCEPTION_OF",
}


class ExtractedRelation(BaseModel):
    """Structured output for LLM relation extraction.

    Used as the schema for structured LLM output in _llm_extraction().
    """

    source_type: str = Field(
        ...,
        description="Type of source node: Party, Section, Obligation, Deadline, Amount, Penalty, Definition",
    )
    source_label: str = Field(
        ..., min_length=1, description="Display name of the source node"
    )
    edge_type: str = Field(
        ...,
        description="Relation type: OBLIGATES, HAS_DEADLINE, HAS_AMOUNT, HAS_PENALTY, DEFINES, REFERENCES, EXCEPTION_OF",
    )
    target_type: str = Field(
        ...,
        description="Type of target node: Party, Section, Obligation, Deadline, Amount, Penalty, Definition",
    )
    target_label: str = Field(
        ..., min_length=1, description="Display name of the target node"
    )
    snippet: str = Field(
        ...,
        min_length=10,
        description="Text snippet from the chunk supporting this relation (quote)",
    )


class ChunkExtractionResult(BaseModel):
    """Structured output for LLM extraction from a single chunk."""

    relations: list[ExtractedRelation] = Field(
        default_factory=list, description="Relations extracted from this chunk"
    )


class GraphExtractor:
    """Extract entities and relations from legal document chunks for Graph RAG.

    Uses a hybrid two-phase approach:
    1. Heuristic extraction: Fast regex-based reference detection
    2. LLM extraction: Structured output for complex entity/relation extraction

    All edges require evidence (snippet + chunk location). Edges without
    evidence are dropped. Graph extraction is feature-flagged via the
    `enabled` parameter.

    Usage:
        >>> from services.graph.extractor import GraphExtractor
        >>> from services.chunking.legal_chunker import LegalChunker
        >>>
        >>> extractor = GraphExtractor(enabled=True)  # Uses get_llm() from registry
        >>> chunks = LegalChunker().chunk(text, pages)
        >>> result = await extractor.extract("doc-uuid", "user-uuid", chunks)
        >>> print(f"Extracted {len(result.nodes)} nodes, {len(result.edges)} edges")
    """

    def __init__(self, llm: Any | None = None, enabled: bool = False) -> None:
        """Initialize the graph extractor.

        Args:
            llm: Optional LLM instance. If None, uses get_llm() from registry.
            enabled: Feature flag to enable/disable graph extraction.
                    When disabled, extract() returns empty result quickly.
        """
        self._llm = llm
        self._enabled = enabled
        self._structured_llm: Any | None = None

        if enabled:
            try:
                llm_instance = llm or get_llm()
                self._structured_llm = llm_instance.with_structured_output(
                    ChunkExtractionResult
                )
                logger.info("GraphExtractor initialized with LLM")
            except Exception as e:
                logger.warning("Failed to initialize structured LLM: %s", e)
                self._enabled = False

    async def extract(
        self, document_id: str, user_id: str, chunks: list[LegalChunk]
    ) -> GraphExtractionResult:
        """Extract graph nodes and edges from document chunks.

        Two-phase extraction:
        1. Heuristic: Find references/anchors → create REFERENCE edges
        2. LLM-based: Extract parties, obligations, deadlines with evidence

        Args:
            document_id: UUID of the document being processed
            user_id: User ID for RLS enforcement
            chunks: List of LegalChunk from the document

        Returns:
            GraphExtractionResult containing all nodes and edges with evidence
        """
        start_time = time.monotonic()

        if not self._enabled or not chunks:
            return self._empty_result(document_id, user_id, len(chunks))

        logger.info(
            "Starting graph extraction for %s (%d chunks)", document_id, len(chunks)
        )

        # Run extraction phases
        all_nodes, all_edges, heuristic_count, llm_count = await self._run_extraction_phases(
            document_id, user_id, chunks
        )

        # Process and deduplicate
        unique_nodes = self._deduplicate_nodes(all_nodes)
        doc_node = self._ensure_document_node(unique_nodes, document_id, user_id)
        node_lookup = self._build_node_lookup(unique_nodes)

        # Resolve edges
        resolved_edges = self._resolve_and_deduplicate_edges(
            all_edges, node_lookup, doc_node, document_id, user_id
        )
        valid_edges = self._filter_valid_edges(resolved_edges)

        # Calculate duration and build result
        duration_ms = int((time.monotonic() - start_time) * 1000)

        logger.info(
            "Graph extraction complete: %d nodes, %d edges (took %dms)",
            len(unique_nodes),
            len(valid_edges),
            duration_ms,
        )

        return self._build_result(
            document_id=document_id,
            user_id=user_id,
            nodes=unique_nodes,
            edges=valid_edges,
            chunk_count=len(chunks),
            duration_ms=duration_ms,
            heuristic_edges=heuristic_count,
            llm_edges=llm_count,
        )

    def _empty_result(
        self, document_id: str, user_id: str, chunk_count: int
    ) -> GraphExtractionResult:
        """Return empty result when extraction is disabled or no chunks.

        Args:
            document_id: Document UUID
            user_id: User ID
            chunk_count: Number of chunks (for statistics)

        Returns:
            Empty GraphExtractionResult with enabled flag set
        """
        return GraphExtractionResult(
            document_id=document_id,
            user_id=user_id,
            statistics={
                "enabled": self._enabled,
                "chunk_count": chunk_count,
                "duration_ms": 0,
                "heuristic_edges": 0,
                "llm_edges": 0,
            },
        )

    async def _run_extraction_phases(
        self, document_id: str, user_id: str, chunks: list[LegalChunk]
    ) -> tuple[list[GraphNode], list[GraphEdge], int, int]:
        """Run both extraction phases and combine results.

        Args:
            document_id: Document UUID
            user_id: User ID for RLS
            chunks: Document chunks to analyze

        Returns:
            Tuple of (all_nodes, all_edges, heuristic_edge_count, llm_edge_count)
        """
        # Phase 1: Heuristic extraction (cheap)
        heuristic_nodes, heuristic_edges = self._heuristic_extraction(
            document_id, user_id, chunks
        )

        # Phase 2: LLM extraction (controlled, with evidence)
        llm_nodes, llm_edges = await self._llm_extraction(document_id, user_id, chunks)

        # Combine results
        all_nodes = heuristic_nodes + llm_nodes
        all_edges = heuristic_edges + llm_edges

        return all_nodes, all_edges, len(heuristic_edges), len(llm_edges)

    def _deduplicate_nodes(self, nodes: list[GraphNode]) -> list[GraphNode]:
        """Deduplicate nodes by (document_id, node_type, label).

        Keeps the first occurrence of each unique node.

        Args:
            nodes: List of nodes (potentially with duplicates)

        Returns:
            List of unique nodes
        """
        node_key = lambda n: (n.document_id, n.node_type, n.label)
        seen_nodes: set[tuple[str, str, str]] = set()
        unique_nodes: list[GraphNode] = []

        for node in nodes:
            key = node_key(node)
            if key not in seen_nodes:
                seen_nodes.add(key)
                unique_nodes.append(node)

        return unique_nodes

    def _ensure_document_node(
        self, nodes: list[GraphNode], document_id: str, user_id: str
    ) -> GraphNode:
        """Ensure document node exists and insert at beginning of list.

        Args:
            nodes: List of nodes to modify (mutated in place)
            document_id: Document UUID
            user_id: User ID for RLS

        Returns:
            The document node (created or existing)
        """
        doc_node = GraphNode(
            document_id=document_id,
            user_id=user_id,
            node_type="Document",
            label=f"Document {document_id[:8]}",
            properties={"full_id": document_id},
        )
        nodes.insert(0, doc_node)
        return doc_node

    def _build_node_lookup(
        self, nodes: list[GraphNode]
    ) -> dict[tuple[str, str], str]:
        """Build lookup table from (node_type, label) to node_id.

        Assigns UUIDs to nodes that don't have an ID yet.

        Args:
            nodes: List of nodes (will be mutated to ensure IDs are set)

        Returns:
            Dictionary mapping (node_type, label) to node_id
        """
        node_lookup: dict[tuple[str, str], str] = {}

        for node in nodes:
            key = (node.node_type, node.label)
            if key not in node_lookup:
                node_id = node.id or str(uuid.uuid4())
                node.id = node_id
                node_lookup[key] = node_id

        return node_lookup

    def _resolve_and_deduplicate_edges(
        self,
        edges: list[GraphEdge],
        node_lookup: dict[tuple[str, str], str],
        doc_node: GraphNode,
        document_id: str,
        user_id: str,
    ) -> list[GraphEdge]:
        """Resolve edge references and deduplicate.

        Args:
            edges: Raw edges from extraction phases
            node_lookup: Mapping from (node_type, label) to node_id
            doc_node: Document node to use as fallback for unresolved sources
            document_id: Document UUID
            user_id: User ID for RLS

        Returns:
            List of resolved and deduplicated edges
        """
        resolved_edges: list[GraphEdge] = []
        seen_edges: set[tuple[str, str, str, str]] = set()

        for edge in edges:
            # Skip edges without evidence (safety check)
            if not edge.evidence or not edge.evidence.snippet:
                logger.debug("Dropping edge without evidence: %s", edge.edge_type)
                continue

            # Resolve target node (the reference)
            target_id = self._resolve_target_node(
                edge, node_lookup, document_id, user_id
            )

            # Resolve source node (the section containing the reference)
            source_id = self._resolve_source_node(
                edge, node_lookup, doc_node
            )

            # Create final edge with resolved IDs
            final_edge = GraphEdge(
                document_id=document_id,
                user_id=user_id,
                source_node_id=source_id,
                target_node_id=target_id,
                edge_type=edge.edge_type,
                evidence=edge.evidence,
            )

            # Deduplicate edges
            edge_key = self._compute_edge_key(final_edge)
            if edge_key not in seen_edges:
                seen_edges.add(edge_key)
                resolved_edges.append(final_edge)

        return resolved_edges

    def _resolve_target_node(
        self,
        edge: GraphEdge,
        node_lookup: dict[tuple[str, str], str],
        document_id: str,
        user_id: str,
    ) -> str:
        """Resolve target node ID for an edge.

        Creates a new Reference node if not found in lookup.

        Args:
            edge: Edge to resolve
            node_lookup: Node lookup table
            document_id: Document UUID
            user_id: User ID

        Returns:
            Resolved target node ID
        """
        # Try to find target in lookup (temporary storage in target_node_id field)
        target_key = ("Reference", edge.target_node_id)
        target_id = node_lookup.get(target_key)

        if not target_id:
            # Create new reference node
            ref_node = GraphNode(
                document_id=document_id,
                user_id=user_id,
                node_type="Reference",
                label=edge.target_node_id,
                properties={"detected_from": edge.source_node_id},
            )
            ref_node.id = str(uuid.uuid4())
            node_lookup[target_key] = ref_node.id
            target_id = ref_node.id

        return target_id

    def _resolve_source_node(
        self,
        edge: GraphEdge,
        node_lookup: dict[tuple[str, str], str],
        doc_node: GraphNode,
    ) -> str:
        """Resolve source node ID for an edge.

        Uses document node as fallback if section not found.

        Args:
            edge: Edge to resolve
            node_lookup: Node lookup table
            doc_node: Document node (fallback)

        Returns:
            Resolved source node ID
        """
        # Try to find section by snippet prefix
        section_hint = edge.evidence.snippet[:50] if edge.evidence.snippet else ""
        source_section_key = ("Section", section_hint)
        source_id = node_lookup.get(source_section_key)

        if not source_id:
            # Use document node as fallback
            source_id = doc_node.id

        return source_id

    def _compute_edge_key(self, edge: GraphEdge) -> tuple[str, str, str, str]:
        """Compute deduplication key for an edge.

        Args:
            edge: Edge to compute key for

        Returns:
            Tuple of (source_id, target_id, edge_type, snippet_prefix)
        """
        snippet_prefix = edge.evidence.snippet[:50] if edge.evidence.snippet else ""
        return (edge.source_node_id, edge.target_node_id, edge.edge_type, snippet_prefix)

    def _filter_valid_edges(self, edges: list[GraphEdge]) -> list[GraphEdge]:
        """Filter edges to only include valid edge types.

        Args:
            edges: List of edges to filter

        Returns:
            Filtered list with only VALID_EDGE_TYPES
        """
        return [e for e in edges if e.edge_type in VALID_EDGE_TYPES]

    def _build_result(
        self,
        document_id: str,
        user_id: str,
        nodes: list[GraphNode],
        edges: list[GraphEdge],
        chunk_count: int,
        duration_ms: int,
        heuristic_edges: int,
        llm_edges: int,
    ) -> GraphExtractionResult:
        """Build final extraction result with statistics.

        Args:
            document_id: Document UUID
            user_id: User ID
            nodes: Final list of nodes
            edges: Final list of edges
            chunk_count: Number of chunks processed
            duration_ms: Total duration in milliseconds
            heuristic_edges: Count of edges from heuristic phase
            llm_edges: Count of edges from LLM phase

        Returns:
            GraphExtractionResult with all data and statistics
        """
        return GraphExtractionResult(
            document_id=document_id,
            user_id=user_id,
            nodes=nodes,
            edges=edges,
            statistics={
                "enabled": True,
                "chunk_count": chunk_count,
                "duration_ms": duration_ms,
                "heuristic_edges": heuristic_edges,
                "llm_edges": llm_edges,
                "final_node_count": len(nodes),
                "final_edge_count": len(edges),
            },
        )

    def _heuristic_extraction(
        self, document_id: str, user_id: str, chunks: list[LegalChunk]
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Fast, cheap extraction of references using regex patterns.

        Detects explicit references like "Clause X", "Article Y", "Annex Z" and
        creates REFERENCE edges between the containing section and the target.

        Args:
            document_id: Document UUID
            user_id: User ID for RLS
            chunks: Document chunks to analyze

        Returns:
            Tuple of (nodes, edges) extracted heuristically
        """
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        for chunk in chunks:
            if not chunk.anchors:
                continue

            # Create section node for this chunk if it has a section hint
            section_node: GraphNode | None = None
            if chunk.section_hint:
                section_node = GraphNode(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    user_id=user_id,
                    node_type="Section",
                    label=chunk.section_hint,
                    properties={
                        "chunk_index": chunk.chunk_index,
                        "page": chunk.page_start,
                    },
                )
                nodes.append(section_node)

            # Process each anchor reference
            for anchor in chunk.anchors:
                ref_match = self._match_reference_pattern(anchor)
                if not ref_match:
                    continue

                ref_type, ref_value = ref_match

                # Create reference node
                ref_node = self._create_reference_node(
                    document_id, user_id, ref_type, ref_value, chunk.chunk_index
                )
                nodes.append(ref_node)

                # Create edge with evidence
                if section_node:
                    edge = self._create_reference_edge(
                        document_id,
                        user_id,
                        section_node.id,
                        ref_node.id,
                        chunk,
                        anchor,
                    )
                    edges.append(edge)

        logger.debug("Heuristic extraction: %d nodes, %d edges", len(nodes), len(edges))
        return nodes, edges

    def _match_reference_pattern(
        self, anchor: str
    ) -> tuple[str, str] | None:
        """Match anchor against reference patterns.

        Args:
            anchor: Anchor text to match

        Returns:
            Tuple of (ref_type, ref_value) or None if no match
        """
        for pattern, ref_type, _ in REFERENCE_PATTERNS:
            match = re.search(pattern, anchor, re.IGNORECASE)
            if match:
                groups = [g for g in match.groups() if g is not None]
                ref_value = groups[0] if groups else anchor
                return (ref_type, ref_value)
        return None

    def _create_reference_node(
        self,
        document_id: str,
        user_id: str,
        ref_type: str,
        ref_value: str,
        chunk_index: int,
    ) -> GraphNode:
        """Create a reference node.

        Args:
            document_id: Document UUID
            user_id: User ID
            ref_type: Type of reference (Clause, Article, etc.)
            ref_value: Value of the reference
            chunk_index: Index where reference was detected

        Returns:
            Created GraphNode for the reference
        """
        return GraphNode(
            id=str(uuid.uuid4()),
            document_id=document_id,
            user_id=user_id,
            node_type="Reference",
            label=f"{ref_type} {ref_value}",
            properties={
                "ref_type": ref_type,
                "ref_value": ref_value,
                "detected_in_chunk": chunk_index,
            },
        )

    def _create_reference_edge(
        self,
        document_id: str,
        user_id: str,
        source_node_id: str | None,
        target_node_id: str | None,
        chunk: LegalChunk,
        anchor: str,
    ) -> GraphEdge:
        """Create a REFERENCE edge with evidence.

        Args:
            document_id: Document UUID
            user_id: User ID
            source_node_id: ID of source node (section)
            target_node_id: ID of target node (reference)
            chunk: Chunk containing the reference
            anchor: Anchor text

        Returns:
            Created GraphEdge
        """
        # Find snippet around the reference
        snippet_start = max(0, chunk.content.find(anchor) - 50)
        snippet_end = min(
            len(chunk.content), chunk.content.find(anchor) + len(anchor) + 50
        )
        snippet = chunk.content[snippet_start:snippet_end].strip()

        return GraphEdge(
            document_id=document_id,
            user_id=user_id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            edge_type="REFERENCES",
            evidence=Evidence(
                document_id=document_id,
                chunk_index=chunk.chunk_index,
                page=chunk.page_start,
                start_char=chunk.char_start + snippet_start,
                end_char=chunk.char_start + snippet_end,
                snippet=snippet,
            ),
        )

    async def _llm_extraction(
        self, document_id: str, user_id: str, chunks: list[LegalChunk]
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        """LLM-based extraction of parties, obligations, and relations.

        Uses structured output to extract entities and relations with evidence.
        Each extracted relation MUST include a text snippet as evidence.

        Args:
            document_id: Document UUID
            user_id: User ID for RLS
            chunks: Document chunks to analyze

        Returns:
            Tuple of (nodes, edges) extracted via LLM
        """
        if not self._structured_llm:
            logger.debug("LLM extraction skipped: no structured LLM available")
            return [], []

        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        batch_size = 5
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            batch_nodes, batch_edges = await self._process_llm_batch(
                document_id, user_id, batch, i
            )
            nodes.extend(batch_nodes)
            edges.extend(batch_edges)

        logger.debug("LLM extraction: %d nodes, %d edges", len(nodes), len(edges))
        return nodes, edges

    async def _process_llm_batch(
        self,
        document_id: str,
        user_id: str,
        batch: list[LegalChunk],
        batch_index: int,
    ) -> tuple[list[GraphNode], list[GraphEdge]]:
        """Process a single batch of chunks with LLM.

        Args:
            document_id: Document UUID
            user_id: User ID
            batch: List of chunks in this batch
            batch_index: Index of batch (for error reporting)

        Returns:
            Tuple of (nodes, edges) from this batch
        """
        nodes: list[GraphNode] = []
        edges: list[GraphEdge] = []

        # Prepare chunk context
        chunk_context = self._build_chunk_context(batch)

        prompt = ChatPromptTemplate.from_messages([
            (
                "system",
                "You are a legal document analyzer. Extract entities and relations from the provided document chunks. "
                "Focus on: Parties (companies, individuals), Obligations (duties, requirements), "
                "Deadlines (dates, timeframes), Amounts (money, quantities), Penalties (fines, consequences). "
                "For each relation, provide the exact text snippet as evidence. "
                "Only extract relations that are clearly stated in the text.",
            ),
            (
                "human",
                "Analyze these document chunks and extract relations:\n\n{chunks}\n\n"
                "Return structured relations with source, target, and evidence snippets.",
            ),
        ])

        try:
            chain = prompt | self._structured_llm
            result: ChunkExtractionResult = await chain.ainvoke(
                {"chunks": "\n\n---\n\n".join(chunk_context)}
            )

            for relation in result.relations:
                source_node, target_node, edge = self._process_relation(
                    relation, document_id, user_id, batch
                )
                if source_node:
                    nodes.append(source_node)
                if target_node:
                    nodes.append(target_node)
                if edge:
                    edges.append(edge)

        except Exception as e:
            logger.warning("LLM extraction failed for batch %d: %s", batch_index, e)
            # Continue with next batch - don't fail the whole extraction

        return nodes, edges

    def _build_chunk_context(self, batch: list[LegalChunk]) -> list[str]:
        """Build text context for LLM from chunks.

        Args:
            batch: List of chunks to build context for

        Returns:
            List of formatted chunk strings
        """
        chunk_context = []
        for chunk in batch:
            chunk_context.append(
                f"CHUNK {chunk.chunk_index}:\n"
                f"Section: {chunk.section_hint or 'N/A'}\n"
                f"Page: {chunk.page_start or 'N/A'}\n"
                f"Content:\n{chunk.content[:2000]}"  # Limit context size
            )
        return chunk_context

    def _process_relation(
        self,
        relation: ExtractedRelation,
        document_id: str,
        user_id: str,
        batch: list[LegalChunk],
    ) -> tuple[GraphNode | None, GraphNode | None, GraphEdge | None]:
        """Process a single extracted relation into nodes and edge.

        Args:
            relation: Extracted relation from LLM
            document_id: Document UUID
            user_id: User ID
            batch: Batch of chunks (for evidence location)

        Returns:
            Tuple of (source_node, target_node, edge) - any may be None
        """
        # Create source node
        source_node = GraphNode(
            id=str(uuid.uuid4()),
            document_id=document_id,
            user_id=user_id,
            node_type=relation.source_type,
            label=relation.source_label,
            properties={"extracted_via": "llm"},
        )

        # Create target node
        target_node = GraphNode(
            id=str(uuid.uuid4()),
            document_id=document_id,
            user_id=user_id,
            node_type=relation.target_type,
            label=relation.target_label,
            properties={"extracted_via": "llm"},
        )

        # Find which chunk contains the evidence
        evidence_chunk = self._find_evidence_chunk(batch, relation.snippet)
        if not evidence_chunk:
            evidence_chunk = batch[0]

        # Calculate position in chunk
        snippet_pos = evidence_chunk.content.find(relation.snippet)
        if snippet_pos < 0:
            snippet_pos = 0

        # Create edge with evidence
        edge = GraphEdge(
            document_id=document_id,
            user_id=user_id,
            source_node_id=source_node.id,
            target_node_id=target_node.id,
            edge_type=relation.edge_type,
            evidence=Evidence(
                document_id=document_id,
                chunk_index=evidence_chunk.chunk_index,
                page=evidence_chunk.page_start,
                start_char=evidence_chunk.char_start + snippet_pos,
                end_char=evidence_chunk.char_start
                + snippet_pos
                + len(relation.snippet),
                snippet=relation.snippet,
            ),
        )

        return source_node, target_node, edge

    def _find_evidence_chunk(
        self, batch: list[LegalChunk], snippet: str
    ) -> LegalChunk | None:
        """Find which chunk in batch contains the given snippet.

        Args:
            batch: List of chunks to search
            snippet: Text snippet to find

        Returns:
            Chunk containing the snippet, or None if not found
        """
        for chunk in batch:
            if snippet in chunk.content:
                return chunk
        return None
