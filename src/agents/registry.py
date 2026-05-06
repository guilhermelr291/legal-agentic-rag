"""Registry for agent components using context variables.

Provides thread-safe access to LLM, retriever, and reranker instances
using Python's context variables.
"""

from contextvars import ContextVar

from langchain_openai import ChatOpenAI

from src.agents.rerankers.base import Reranker
from src.agents.retrievers.base import Retriever

# Context variables for dependency injection
_llm_var: ContextVar[ChatOpenAI | None] = ContextVar("llm", default=None)
_retriever_var: ContextVar[Retriever | None] = ContextVar("retriever", default=None)
_reranker_var: ContextVar[Reranker | None] = ContextVar("reranker", default=None)


def set_llm(llm: ChatOpenAI) -> None:
    """Set the LLM in the context registry."""
    _llm_var.set(llm)


def get_llm() -> ChatOpenAI:
    """Get the configured LLM.

    Raises:
        RuntimeError: If LLM is not configured. Call set_llm() or init_default_llm() first.
    """
    llm = _llm_var.get()
    if llm is None:
        raise RuntimeError("LLM not configured. Call set_llm() or init_default_llm() first.")
    return llm


def init_default_llm() -> ChatOpenAI:
    """Initialize and set the default LLM based on settings.

    Returns:
        The configured ChatOpenAI instance.
    """
    from src.agents.config import agents_settings

    llm = ChatOpenAI(
        model=agents_settings.OPENAI_LIGHTWEIGHT_MODEL,
        api_key=agents_settings.OPENAI_API_KEY,
    )
    set_llm(llm)
    return llm


def set_retriever(retriever: Retriever) -> None:
    """Set the retriever in the context registry."""
    _retriever_var.set(retriever)


def get_retriever() -> Retriever:
    """Get the configured retriever.

    Raises:
        RuntimeError: If retriever is not configured. Call set_retriever() first.
    """
    retriever = _retriever_var.get()
    if retriever is None:
        raise RuntimeError("Retriever not configured. Call set_retriever() first.")
    return retriever


def set_reranker(reranker: Reranker) -> None:
    """Set the reranker in the context registry."""
    _reranker_var.set(reranker)


def get_reranker() -> Reranker:
    """Get the configured reranker.

    Raises:
        RuntimeError: If reranker is not configured. Call set_reranker() first.
    """
    reranker = _reranker_var.get()
    if reranker is None:
        raise RuntimeError("Reranker not configured. Call set_reranker() first.")
    return reranker


def clear_registry() -> None:
    """Clear all entries from the registry."""
    _llm_var.set(None)
    _retriever_var.set(None)
    _reranker_var.set(None)
