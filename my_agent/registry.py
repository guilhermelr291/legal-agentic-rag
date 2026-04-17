from contextvars import ContextVar
from typing import Any

from langchain_openai import ChatOpenAI
from my_agent.retrievers.base import Retriever

_llm_var: ContextVar[ChatOpenAI | None] = ContextVar("llm", default=None)
_retriever_var: ContextVar[Retriever | None] = ContextVar("retriever", default=None)


def set_llm(llm: ChatOpenAI) -> None:
    _llm_var.set(llm)


def get_llm() -> ChatOpenAI:
    llm = _llm_var.get()
    if llm is None:
        raise RuntimeError("LLM not configured. Call set_llm() first.")
    return llm


def set_retriever(retriever: Retriever) -> None:
    _retriever_var.set(retriever)


def get_retriever() -> Retriever:
    retriever = _retriever_var.get()
    if retriever is None:
        raise RuntimeError("Retriever not configured. Call set_retriever() first.")
    return retriever


def clear_registry() -> None:
    _llm_var.set(None)
    _retriever_var.set(None)
