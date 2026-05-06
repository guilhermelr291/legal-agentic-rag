"""Graph state definition for agent execution."""

import operator
from typing import Annotated, TypedDict

from langchain_core.messages import AnyMessage


class GraphState(TypedDict):
    """State for the RAG graph execution.

    Attributes:
        messages: Conversation history with automatic aggregation.
        documents: Retrieved documents relevant to the query.
        generation: Generated answer from the LLM.
        queries_for_retrieval: Generated queries for document retrieval.
    """

    messages: Annotated[list[AnyMessage], operator.add]
    documents: list[str]
    generation: str
    queries_for_retrieval: list[str]
