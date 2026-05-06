"""Abstract base class for document retrievers."""

from abc import ABC, abstractmethod

from langchain_core.documents import Document


class Retriever(ABC):
    """Abstract base class for retrievers.

    Implementations must provide synchronous and asynchronous
    methods for retrieving documents relevant to a query.
    """

    @abstractmethod
    def retrieve(self, query: str, k: int = 10) -> list[Document]:
        """Retrieve documents relevant to the query.

        Args:
            query: Search query string.
            k: Number of documents to retrieve.

        Returns:
            List of documents ordered by relevance.
        """
        pass

    @abstractmethod
    def batch_retrieve(self, queries: list[str], k: int = 10) -> list[list[Document]]:
        """Retrieve documents for multiple queries.

        Args:
            queries: List of search query strings.
            k: Number of documents to retrieve per query.

        Returns:
            List of document lists, one per query.
        """
        pass

    @abstractmethod
    async def abatch_retrieve(self, queries: list[str], k: int = 10) -> list[list[Document]]:
        """Async retrieve documents for multiple queries.

        Args:
            queries: List of search query strings.
            k: Number of documents to retrieve per query.

        Returns:
            List of document lists, one per query.
        """
        pass
