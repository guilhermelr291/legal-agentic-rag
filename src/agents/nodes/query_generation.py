"""Query generation node for multi-query retrieval."""

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.agents.registry import get_llm
from src.agents.state import GraphState


class MultiQueryGeneration(BaseModel):
    """Output schema for multi-query generation."""

    queries: list[str] = Field(
        description="5 different search queries to retrieve documents for the user question"
    )


def multi_query_generation_node(state: GraphState) -> dict:
    """Generate multiple search queries from user question.

    Creates 5 different queries covering different aspects of the question,
    optimized for semantic similarity and BM25 hybrid search.

    Args:
        state: Current graph state with user messages.

    Returns:
        Dict with queries_for_retrieval key containing the generated queries.
    """
    llm = get_llm()

    multi_query_generation_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a helpful assistant and your task is to generate 5 different search queries for the user question. The queries should cover different aspects of the question and should be optimized for semantic similarity and bm25 (hybrid search)",
            ),
            ("human", "User question: {question}"),
        ]
    )
    multi_query_generation_chain = multi_query_generation_prompt | llm.with_structured_output(
        MultiQueryGeneration
    )

    question = state["messages"][-1].content
    response = multi_query_generation_chain.invoke({"question": question})
    queries = response.queries

    return {"queries_for_retrieval": queries}
