from contextvars import ContextVar


from langchain_openai import ChatOpenAI
from my_agent.retrievers.base import Retriever
from my_agent.config.settings import get_settings


_llm_var: ContextVar[ChatOpenAI | None] = ContextVar("llm", default=None)
_retriever_var: ContextVar[Retriever | None] = ContextVar("retriever", default=None)
_reranker_var: ContextVar["Reranker" | None] = ContextVar("reranker", default=None)


def set_llm(llm: ChatOpenAI) -> None:
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
    settings = get_settings()
    llm = ChatOpenAI(
        model=settings.openai_lightweight_model,
        api_key=settings.openai_api_key
    )
    set_llm(llm)
    return llm


def set_retriever(retriever: Retriever) -> None:
    _retriever_var.set(retriever)


def get_retriever() -> Retriever:
    retriever = _retriever_var.get()
    if retriever is None:
        raise RuntimeError("Retriever not configured. Call set_retriever() first.")
    return retriever


def set_reranker(reranker: "Reranker") -> None:
    _reranker_var.set(reranker)


def get_reranker() -> "Reranker":
    reranker = _reranker_var.get()
    if reranker is None:
        raise RuntimeError("Reranker not configured. Call set_reranker() first.")
    return reranker


def clear_registry() -> None:
    _llm_var.set(None)
    _retriever_var.set(None)
    _reranker_var.set(None)
