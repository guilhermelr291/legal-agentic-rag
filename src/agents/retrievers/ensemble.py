"""Ensemble retriever combining multiple retrieval strategies."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from langchain_classic.retrievers import EnsembleRetriever as LangChainEnsembleRetriever
from langchain_core.documents import Document

from src.agents.retrievers.base import Retriever

logger = logging.getLogger(__name__)

DEFAULT_HYBRID_WEIGHTS: tuple[float, float] = (0.7, 0.3)


class EnsembleRetriever(Retriever):
    """Hybrid retriever combining multiple retrieval strategies.

    Uses LangChain's EnsembleRetriever with weighted results and
    Reciprocal Rank Fusion for merging results.

    Attributes:
        retrievers: List of underlying retriever instances.
        weights: Weights for combining retriever results.
        c: RRF smoothing constant.
        max_workers: Thread pool size for batch retrieval.
    """

    def __init__(
        self,
        retrievers: list,
        weights: list[float] | None = None,
        c: float = 60,
        max_workers: int = 5,
    ):
        self.retrievers = retrievers
        if weights is None and len(retrievers) == 2:
            self.weights = list(DEFAULT_HYBRID_WEIGHTS)
        else:
            self.weights = weights
        self.c = c
        self.max_workers = max_workers

        langchain_retrievers = []
        for r in retrievers:
            if hasattr(r, "as_retriever"):
                langchain_retrievers.append(r.as_retriever())
            else:
                langchain_retrievers.append(r)

        self._ensemble = LangChainEnsembleRetriever(
            retrievers=langchain_retrievers,
            weights=self.weights,
            c=self.c,
        )

    def retrieve(self, query: str, k: int = 10) -> list[Document]:
        """Retrieve documents using ensemble.

        Args:
            query: Search query string.
            k: Number of documents to retrieve.

        Returns:
            List of documents from ensemble retrieval.
        """
        return self._ensemble.invoke(query, config={"k": k})

    def batch_retrieve(self, queries: list[str], k: int = 10) -> list[list[Document]]:
        """Batch retrieve documents for multiple queries.

        Args:
            queries: List of search query strings.
            k: Number of documents per query.

        Returns:
            List of document lists, one per query.
        """
        if len(queries) == 1:
            return [self.retrieve(queries[0], k)]

        workers = min(self.max_workers, len(queries))
        errors = []

        with ThreadPoolExecutor(max_workers=workers) as executor:
            future_to_query = {executor.submit(self.retrieve, query, k): query for query in queries}

            results = []
            for future in future_to_query:
                query = future_to_query[future]
                try:
                    results.append(future.result())
                except Exception as e:
                    logger.error(f"Retrieval error for query '{query}': {e}", exc_info=True)
                    errors.append({"query": query, "error": str(e)})
                    results.append([])

        if errors:
            logger.warning(f"Failed to retrieve for {len(errors)} out of {len(queries)} queries")

        return results

    async def abatch_retrieve(self, queries: list[str], k: int = 10) -> list[list[Document]]:
        """Async batch retrieve documents.

        Args:
            queries: List of search query strings.
            k: Number of documents per query.

        Returns:
            List of document lists, one per query.
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.batch_retrieve,
            queries,
            k,
        )
