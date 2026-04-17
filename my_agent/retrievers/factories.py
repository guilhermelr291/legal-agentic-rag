from langchain_chroma import Chroma
from langchain_community.retrievers import BM25Retriever

from my_agent.config.settings import get_settings


def create_chroma_retriever(embedding_model=None):
    settings = get_settings()
    
    raise NotImplementedError(
        "Configure Chroma retriever with your embedding model and collection."
    )


def create_bm25_retriever(documents=None):
    if documents is None:
        raise ValueError("BM25 retriever requires documents to be provided")
    
    return BM25Retriever.from_documents(documents)


def create_ensemble_retriever(retrievers, weights=None):
    from my_agent.retrievers.ensemble import EnsembleRetriever
    
    return EnsembleRetriever(
        retrievers=retrievers,
        weights=weights,
    )
