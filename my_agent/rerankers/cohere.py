"""Cohere reranker implementation."""


from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional

from langchain_core.documents import Document

from my_agent.rerankers.base import Reranker

import cohere


class CohereReranker(Reranker):
    """Reranker using Cohere's Rerank API.

    Supports both synchronous and asynchronous reranking.
    Default model is 'rerank-v3.5' which is Cohere's most capable model.
    """

    DEFAULT_MODEL = "rerank-v3.5"

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        max_workers: int = 3,
    ):
        """Initialize Cohere reranker.

        Args:
            api_key: Cohere API key.
            model: Model name to use for reranking.
            max_workers: Maximum thread pool workers for async operations.
        """
        self.client = cohere.Client(api_key)
        self.async_client = cohere.AsyncClient(api_key)
        self.model = model
        self.max_workers = max_workers
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    def rerank(
        self, query: str, documents: List[Document], top_k: int = 10
    ) -> List[Document]:
        """Rerank documents using Cohere API (sync).

        Args:
            query: The search query.
            documents: Documents to rerank.
            top_k: Number of top documents to return.

        Returns:
            Reranked list of documents with scores in metadata.
        """
        if not documents:
            return []

        docs_text = [doc.page_content for doc in documents]

        response = self.client.rerank(
            model=self.model,
            query=query,
            documents=docs_text,
            top_n=min(top_k, len(documents)),
        )

        return self._process_results(documents, response.results)

    async def arerank(
        self, query: str, documents: List[Document], top_k: int = 10
    ) -> List[Document]:
        """Rerank documents using Cohere API (async).

        Args:
            query: The search query.
            documents: Documents to rerank.
            top_k: Number of top documents to return.

        Returns:
            Reranked list of documents with scores in metadata.
        """
        if not documents:
            return []

        docs_text = [doc.page_content for doc in documents]

        response = await self.async_client.rerank(
            model=self.model,
            query=query,
            documents=docs_text,
            top_n=min(top_k, len(documents)),
        )

        return self._process_results(documents, response.results)

    def _process_results(
        self,
        original_docs: List[Document],
        results: List,
    ) -> List[Document]:
        """Process Cohere reranking results.

        Args:
            original_docs: Original documents list.
            results: Cohere rerank results.

        Returns:
            Reordered documents with rerank scores in metadata.
        """
        reranked = []

        for result in results:
            doc = original_docs[result.index]
            doc_copy = Document(
                page_content=doc.page_content,
                metadata={
                    **doc.metadata,
                    "rerank_score": result.relevance_score,
                    "original_index": result.index,
                },
            )
            reranked.append(doc_copy)

        return reranked

    def __del__(self):
        """Cleanup thread pool executor."""
        if hasattr(self, "_executor"):
            self._executor.shutdown(wait=False)
