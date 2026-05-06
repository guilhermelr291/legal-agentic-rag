"""Embeddings service for OpenAI embedding generation."""

from __future__ import annotations

import asyncio
import logging

from langchain_openai import OpenAIEmbeddings

from src.common.exceptions import ProcessingError
from src.embeddings.config import embeddings_settings

logger = logging.getLogger(__name__)

DEFAULT_RETRY_DELAY = 2.0


class EmbeddingsService:
    """Service for generating OpenAI embeddings.

    Provides batch embedding generation with automatic retry logic
    for handling transient API failures.

    Config:
        batch_size: Number of texts per embedding API call (default: 100)
        retry_delay: Seconds to wait before retry on failure (default: 2.0)

    Example:
        >>> service = EmbeddingsService()
        >>> embeddings = await service.generate_embeddings(["text1", "text2"])
        >>> single = await service.generate_single("single text")
    """

    def __init__(
        self,
        client: OpenAIEmbeddings | None = None,
        batch_size: int | None = None,
        retry_delay: float = DEFAULT_RETRY_DELAY,
    ):
        """Initialize the embeddings service.

        Args:
            client: OpenAIEmbeddings client. If None, creates from settings.
            batch_size: Number of texts per batch. Defaults to settings.BATCH_SIZE.
            retry_delay: Seconds to wait before retry (default: 2.0)
        """
        if client is None:
            client = OpenAIEmbeddings(
                model=embeddings_settings.EMBEDDING_MODEL,
                api_key=embeddings_settings.OPENAI_API_KEY,
            )

        self._client = client
        self._batch_size = batch_size or embeddings_settings.BATCH_SIZE
        self._retry_delay = retry_delay

    def _batch_texts(self, texts: list[str]) -> list[list[str]]:
        """Split texts into batches for processing.

        Args:
            texts: List of text strings to batch

        Returns:
            List of batches, each containing up to batch_size texts
        """
        if not texts:
            return []

        batches: list[list[str]] = []
        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            batches.append(batch)

        return batches

    async def _generate_with_retry(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings with one retry on failure.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors

        Raises:
            ProcessingError: If embedding generation fails after retry
        """
        try:
            return await self._client.aembed_documents(texts)
        except Exception as e:
            logger.warning("Embedding API failed, retrying in %ss: %s", self._retry_delay, e)
            await asyncio.sleep(self._retry_delay)

            try:
                return await self._client.aembed_documents(texts)
            except Exception as e2:
                logger.error("Embedding API failed after retry: %s", e2)
                raise ProcessingError(
                    f"Failed to generate embeddings after retry: {e2}", code="EMBEDDING_FAILED"
                ) from e2

    async def generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts in batches.

        Processes texts in configurable batch sizes with retry logic
        for each batch.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors (one per input text)

        Raises:
            ProcessingError: If embedding generation fails after retry
            ValueError: If texts list is empty
        """
        if not texts:
            raise ValueError("Cannot generate embeddings for empty text list")

        batches = self._batch_texts(texts)
        all_embeddings: list[list[float]] = []

        logger.debug(
            "Generating embeddings for %d texts in %d batches",
            len(texts),
            len(batches),
        )

        for batch_num, batch in enumerate(batches, start=1):
            embeddings = await self._generate_with_retry(batch)
            all_embeddings.extend(embeddings)

            logger.debug(
                "Batch %d/%d complete: generated %d embeddings",
                batch_num,
                len(batches),
                len(embeddings),
            )

        logger.info(
            "Successfully generated %d embeddings for %d texts",
            len(all_embeddings),
            len(texts),
        )

        return all_embeddings

    async def generate_single(self, text: str) -> list[float]:
        """Generate embedding for a single text.

        Args:
            text: Text string to embed

        Returns:
            Embedding vector

        Raises:
            ProcessingError: If embedding generation fails after retry
            ValueError: If text is empty
        """
        if not text or not text.strip():
            raise ValueError("Cannot generate embedding for empty text")

        try:
            embeddings = await self._client.aembed_documents([text])
            return embeddings[0]
        except Exception as e:
            logger.warning(
                "Embedding API failed for single text, retrying in %ss: %s",
                self._retry_delay,
                e,
            )
            await asyncio.sleep(self._retry_delay)

            try:
                embeddings = await self._client.aembed_documents([text])
                return embeddings[0]
            except Exception as e2:
                logger.error("Embedding API failed after retry: %s", e2)
                raise ProcessingError(
                    f"Failed to generate embedding after retry: {e2}", code="EMBEDDING_FAILED"
                ) from e2
