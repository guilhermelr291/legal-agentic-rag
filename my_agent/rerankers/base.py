"""Abstract base class for rerankers."""

from abc import ABC, abstractmethod
from typing import List

from langchain_core.documents import Document


class Reranker(ABC):
    """Abstract base class for document rerankers.

    Rerankers take a list of retrieved documents and reorder them
    based on relevance to the query using more computationally
    expensive but accurate scoring methods.
    """

    @abstractmethod
    def rerank(
        self, query: str, documents: List[Document], top_k: int = 10
    ) -> List[Document]:
        """Rerank documents based on relevance to the query.

        Args:
            query: The search query to rank documents against.
            documents: List of documents to rerank.
            top_k: Maximum number of documents to return.

        Returns:
            List of reranked documents, ordered by relevance (best first).
            Documents may include a "rerank_score" in their metadata.
        """
        pass

    @abstractmethod
    async def arerank(
        self, query: str, documents: List[Document], top_k: int = 10
    ) -> List[Document]:
        """Async version of rerank.

        Args:
            query: The search query to rank documents against.
            documents: List of documents to rerank.
            top_k: Maximum number of documents to return.

        Returns:
            List of reranked documents, ordered by relevance (best first).
        """
        pass
