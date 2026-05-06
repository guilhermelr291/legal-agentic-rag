"""Router node for determining data source."""

from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.agents.registry import get_llm
from src.agents.state import GraphState


class RouteQuery(BaseModel):
    """Output schema for query routing decision."""

    datasource: Literal["vectorstore", "web_search"] = Field(
        description="Route to vectorstore for Python topics or web_search for general knowledge"
    )


def router_node(state: GraphState) -> Literal["vectorstore", "web_search"]:
    """Router that determines the data source and returns the route directly.

    Used by add_conditional_edges to decide the next node.

    Args:
        state: Current graph state containing messages.

    Returns:
        Either "vectorstore" or "web_search" based on query analysis.
    """
    llm = get_llm()

    structured_llm = llm.with_structured_output(RouteQuery)
    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are an expert at routing questions. Use vectorstore for Python topics, web_search otherwise.",
            ),
            ("human", "{question}"),
        ]
    )
    router_chain = prompt | structured_llm

    question = state["messages"][-1].content
    result = router_chain.invoke({"question": question})
    return result.datasource
