"""Factory functions for creating retriever instances."""

from langchain_community.retrievers import BM25Retriever

# factories.py: Implementation for retriever factories
# This file is kept for future use when retriever configuration is needed.


def create_chroma_retriever(embedding_model=None):
    """Create a Chroma vector store retriever.

    Args:
        embedding_model: Embedding model for vectorization.

    Raises:
        NotImplementedError: Requires configuration of embedding model and collection.
    """
    raise NotImplementedError(
        "Configure Chroma retriever with your embedding model and collection."
    )


def create_bm25_retriever(documents=None):
    """Create a BM25 keyword retriever.

    Args:
        documents: Documents to index for BM25 retrieval.

    Returns:
        BM25Retriever instance.

    Raises:
        ValueError: If documents are not provided.
    """
    if documents is None:
        raise ValueError("BM25 retriever requires documents to be provided")

    return BM25Retriever.from_documents(documents)


def create_ensemble_retriever(retrievers, weights=None):
    """Build hybrid ensemble retriever.

    For two retrievers, default weights are 0.7 / 0.3 (dense, BM25).

    Args:
        retrievers: List of retriever instances to combine.
        weights: Optional weights for each retriever.

    Returns:
        EnsembleRetriever combining all provided retrievers.
    """
    from src.agents.retrievers.ensemble import EnsembleRetriever

    return EnsembleRetriever(
        retrievers=retrievers,
        weights=weights,
    )
