"""Database repository layer for graph data (Graph RAG).

Provides type-safe repository class for graph nodes and edges with
RLS-aware operations via SupabaseClient.
"""

from __future__ import annotations

import logging
from typing import Any

from services.db.repositories import DatabaseError
from services.graph.models import GraphEdge, GraphNode
from services.storage.supabase_client import SupabaseClient

logger = logging.getLogger(__name__)


class GraphRepository:
    """Repository for graph nodes and edges with RLS-aware operations.

    All methods enforce user_id filtering to maintain row-level security.
    Uses SupabaseClient for database operations.

    Graph data is idempotent per document_id - re-uploading a document
    will replace its graph data via cleanup and re-insertion.
    """

    def __init__(self, client: SupabaseClient) -> None:
        """Initialize with a SupabaseClient instance.

        Args:
            client: Configured SupabaseClient for database operations.
        """
        self._client = client

    async def upsert_nodes(self, nodes: list[GraphNode]) -> list[GraphNode]:
        """Batch upsert graph nodes into the database.

        Uses ON CONFLICT (document_id, label, node_type) DO UPDATE for idempotency.
        All nodes must have the same user_id (enforced for RLS).

        Args:
            nodes: List of GraphNode to upsert. Must include user_id and document_id.

        Returns:
            List of upserted GraphNode with generated IDs.

        Raises:
            DatabaseError: If upsert fails or nodes have mixed user_ids.
            ValueError: If nodes list is empty.
        """
        if not nodes:
            raise ValueError("Cannot upsert empty node list")

        for node in nodes:
            if not node.user_id:
                raise DatabaseError(
                    "All nodes must have user_id for RLS compliance"
                )

        user_ids = {node.user_id for node in nodes}
        if len(user_ids) > 1:
            raise DatabaseError(
                f"Batch upsert requires consistent user_id, got: {user_ids}"
            )

        user_id = nodes[0].user_id

        try:
            data = [node.to_db_dict() for node in nodes]

            result = await self._client.upsert(
                table_name="graph_nodes",
                data=data,
                on_conflict="document_id,label,node_type",
                user_id=user_id,
            )

            if not result.data:
                logger.warning("Upsert returned no data, nodes may still be stored")
                return nodes

            records = [GraphNode(**row) for row in result.data]
            logger.info(
                "Upserted %d nodes for document: %s",
                len(records),
                nodes[0].document_id,
            )
            return records

        except DatabaseError:
            raise
        except Exception as e:
            logger.exception("Failed to upsert nodes")
            raise DatabaseError(f"Failed to upsert nodes: {e}", e) from e

    async def upsert_edges(self, edges: list[GraphEdge]) -> list[GraphEdge]:
        """Batch upsert graph edges into the database with evidence validation.

        Edges without evidence are dropped and not persisted.
        Uses ON CONFLICT (document_id, source_node_id, target_node_id, edge_type) DO UPDATE.
        All edges must have the same user_id (enforced for RLS).

        Args:
            edges: List of GraphEdge to upsert. Must include user_id, document_id,
                   source_node_id, target_node_id, and evidence.

        Returns:
            List of upserted GraphEdge with generated IDs.

        Raises:
            DatabaseError: If upsert fails or edges have mixed user_ids.
            ValueError: If edges list is empty.
        """
        if not edges:
            raise ValueError("Cannot upsert empty edge list")

        valid_edges = []
        dropped_count = 0

        for edge in edges:
            if not edge.user_id:
                raise DatabaseError(
                    "All edges must have user_id for RLS compliance"
                )

            if not edge.evidence or not edge.evidence.snippet:
                dropped_count += 1
                continue

            valid_edges.append(edge)

        if dropped_count > 0:
            logger.warning(
                "Dropped %d edges without evidence for document: %s",
                dropped_count,
                edges[0].document_id,
            )

        if not valid_edges:
            logger.info("No valid edges to upsert (all dropped due to missing evidence)")
            return []

        user_ids = {edge.user_id for edge in valid_edges}
        if len(user_ids) > 1:
            raise DatabaseError(
                f"Batch upsert requires consistent user_id, got: {user_ids}"
            )

        user_id = valid_edges[0].user_id

        try:
            data = [edge.to_db_dict() for edge in valid_edges]

            result = await self._client.upsert(
                table_name="graph_edges",
                data=data,
                on_conflict="document_id,source_node_id,target_node_id,edge_type",
                user_id=user_id,
            )

            if not result.data:
                logger.warning("Upsert returned no data, edges may still be stored")
                return valid_edges

            records = [GraphEdge(**row) for row in result.data]
            logger.info(
                "Upserted %d edges for document: %s (dropped %d without evidence)",
                len(records),
                valid_edges[0].document_id,
                dropped_count,
            )
            return records

        except DatabaseError:
            raise
        except Exception as e:
            logger.exception("Failed to upsert edges")
            raise DatabaseError(f"Failed to upsert edges: {e}", e) from e

    async def delete_by_document(self, document_id: str, user_id: str) -> dict[str, int]:
        """Delete all graph nodes and edges for a specific document.

        Used when reprocessing or deleting a document to ensure clean state.
        Deletes edges first (due to FK constraints), then nodes.

        Args:
            document_id: UUID of the document.
            user_id: User ID for RLS filtering.

        Returns:
            Dictionary with counts: {"nodes_deleted": int, "edges_deleted": int}

        Raises:
            DatabaseError: If delete fails.
        """
        try:
            edges_result = await self._client.delete(
                table_name="graph_edges",
                user_id=user_id,
                filters={"document_id": document_id},
            )
            edges_count = len(edges_result.data)

            nodes_result = await self._client.delete(
                table_name="graph_nodes",
                user_id=user_id,
                filters={"document_id": document_id},
            )
            nodes_count = len(nodes_result.data)

            logger.info(
                "Deleted graph data for document: %s (%d nodes, %d edges)",
                document_id,
                nodes_count,
                edges_count,
            )

            return {"nodes_deleted": nodes_count, "edges_deleted": edges_count}

        except DatabaseError:
            raise
        except Exception as e:
            logger.exception(
                "Failed to delete graph data for document: %s", document_id
            )
            raise DatabaseError(
                f"Failed to delete graph data for {document_id}: {e}", e
            ) from e


__all__ = ["GraphRepository"]
