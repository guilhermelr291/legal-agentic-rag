"""Batch embedding generator with Supabase upsert for document chunks."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from langchain_openai import OpenAIEmbeddings

from my_agent.config.settings import get_settings
from services.chunking.legal_chunker import LegalChunk
from services.db.repositories import ChunkRecord, ChunkRepository

if TYPE_CHECKING:
    from services.storage.supabase_client import SupabaseClient

logger = logging.getLogger(__name__)


DEFAULT_BATCH_SIZE = 100
DEFAULT_RETRY_DELAY = 2.0


@dataclass
class EmbeddingStats:
    """Statistics from embedding generation process.

    Attributes:
        chunks_processed: Total number of chunks processed
        embeddings_generated: Number of successful embeddings generated
        errors: Number of chunks that failed after retry
        batches_processed: Number of batches completed
    """

    chunks_processed: int = 0
    embeddings_generated: int = 0
    errors: int = 0
    batches_processed: int = 0

    def to_dict(self) -> dict:
        """Convert stats to dictionary for logging/response."""
        return {
            "chunks_processed": self.chunks_processed,
            "embeddings_generated": self.embeddings_generated,
            "errors": self.errors,
            "batches_processed": self.batches_processed,
        }


class EmbeddingGenerator:
    """Batch embedding generator with Supabase upsert.

    Generates OpenAI embeddings for document chunks and upserts them
    to Supabase with idempotent conflict handling. Processes chunks in
    batches with progress logging and automatic retry on API failures.

    Config:
        batch_size: Number of chunks per embedding API call (default: 100)
        retry_delay: Seconds to wait before retry on failure (default: 2.0)

    Example:
        >>> from langchain_openai import OpenAIEmbeddings
        >>> from services.storage.supabase_client import SupabaseClient
        >>>
        >>> embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        >>> client = await SupabaseClient.from_service_role()
        >>> chunk_repo = ChunkRepository(client)
        >>>
        >>> generator = EmbeddingGenerator(embeddings)
        >>> stats = await generator.generate_and_upsert(
        ...     document_id="uuid",
        ...     user_id="user_uuid",
        ...     chunks=legal_chunks,
        ...     chunk_repo=chunk_repo,
        ... )
    """

    def __init__(
        self,
        client: OpenAIEmbeddings | None = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        retry_delay: float = DEFAULT_RETRY_DELAY,
    ):
        """Initialize the embedding generator.

        Args:
            client: OpenAIEmbeddings client. If None, creates from settings.
            batch_size: Number of chunks per batch (default: 100)
            retry_delay: Seconds to wait before retry (default: 2.0)
        """
        if client is None:
            settings = get_settings()
            client = OpenAIEmbeddings(
                model=settings.openai_embedding_model,
                api_key=settings.openai_api_key,
            )

        self._client = client
        self._batch_size = batch_size
        self._retry_delay = retry_delay

    def _batch_chunks(self, chunks: list[LegalChunk]) -> list[list[LegalChunk]]:
        """Split chunks into batches for processing.

        Args:
            chunks: List of LegalChunk objects to batch

        Returns:
            List of batches, each containing up to batch_size chunks
        """
        if not chunks:
            return []

        batches: list[list[LegalChunk]] = []
        for i in range(0, len(chunks), self._batch_size):
            batch = chunks[i : i + self._batch_size]
            batches.append(batch)

        return batches

    async def _generate_with_retry(
        self, texts: list[str]
    ) -> list[list[float]] | None:
        """Generate embeddings with one retry on failure.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors, or None if failed after retry
        """
        try:
            return await self._client.aembed_documents(texts)
        except Exception as e:
            logger.warning(
                "Embedding API failed, retrying in %ss: %s", self._retry_delay, e
            )
            await asyncio.sleep(self._retry_delay)

            try:
                return await self._client.aembed_documents(texts)
            except Exception as e2:
                logger.error("Embedding API failed after retry: %s", e2)
                return None

    def _chunks_to_records(
        self,
        chunks: list[LegalChunk],
        document_id: str,
        user_id: str,
        embeddings: list[list[float]] | None,
    ) -> list[ChunkRecord]:
        """Convert LegalChunks to ChunkRecords with embeddings.

        Args:
            chunks: List of LegalChunk objects
            document_id: Document UUID
            user_id: User UUID for RLS
            embeddings: List of embedding vectors, or None if generation failed

        Returns:
            List of ChunkRecord objects ready for upsert
        """
        records: list[ChunkRecord] = []

        for i, chunk in enumerate(chunks):
            embedding = embeddings[i] if embeddings and i < len(embeddings) else None

            record = ChunkRecord(
                document_id=document_id,
                user_id=user_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                embedding=embedding,
                section_hint=chunk.section_hint,
                section_path=list(chunk.section_path),
                page_start=chunk.page_start,
                page_end=chunk.page_end,
                anchors=list(chunk.anchors),
                char_start=chunk.char_start,
                char_end=chunk.char_end,
            )
            records.append(record)

        return records

    async def generate_and_upsert(
        self,
        document_id: str,
        user_id: str,
        chunks: list[LegalChunk],
        chunk_repo: ChunkRepository,
    ) -> EmbeddingStats:
        """Generate embeddings and upsert chunks to Supabase.

        Processes chunks in batches, generates embeddings via OpenAI API,
        and upserts to Supabase with ON CONFLICT handling. Logs progress
        after each batch.

        Args:
            document_id: UUID of the document being processed
            user_id: User UUID for RLS enforcement
            chunks: List of LegalChunk objects to embed and store
            chunk_repo: ChunkRepository for database operations

        Returns:
            EmbeddingStats with processing results

        Raises:
            ValueError: If chunks list is empty
        """
        if not chunks:
            raise ValueError("Cannot generate embeddings for empty chunk list")

        stats = EmbeddingStats()
        batches = self._batch_chunks(chunks)
        total_batches = len(batches)

        logger.info(
            "Starting embedding generation for document %s: %d chunks in %d batches",
            document_id,
            len(chunks),
            total_batches,
        )

        for batch_num, batch_chunks in enumerate(batches, start=1):
            texts = [chunk.content for chunk in batch_chunks]

            # Generate embeddings with retry
            embeddings = await self._generate_with_retry(texts)

            if embeddings is None:
                # Failed after retry - create records without embeddings
                logger.error(
                    "Batch %d/%d failed after retry, storing without embeddings",
                    batch_num,
                    total_batches,
                )
                embeddings = None
                stats.errors += len(batch_chunks)
            else:
                stats.embeddings_generated += len(batch_chunks)
                logger.debug(
                    "Batch %d/%d: Generated %d embeddings",
                    batch_num,
                    total_batches,
                    len(embeddings),
                )

            # Convert to ChunkRecords
            records = self._chunks_to_records(
                chunks=batch_chunks,
                document_id=document_id,
                user_id=user_id,
                embeddings=embeddings,
            )

            # Upsert to database
            try:
                await chunk_repo.upsert_chunks(records)
                stats.batches_processed += 1
                stats.chunks_processed += len(batch_chunks)

                logger.info(
                    "Batch %d/%d complete (%d chunks)",
                    batch_num,
                    total_batches,
                    len(batch_chunks),
                )
            except Exception as e:
                logger.error(
                    "Failed to upsert batch %d/%d for document %s: %s",
                    batch_num,
                    total_batches,
                    document_id,
                    e,
                )
                stats.errors += len(batch_chunks)

        logger.info(
            "Embedding generation complete for document %s: %s",
            document_id,
            stats.to_dict(),
        )

        return stats
