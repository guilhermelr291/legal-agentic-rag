"""LangGraph definition for the RAG agent.

Defines the graph structure with nodes for query routing,
multi-query generation, retrieval, grading, and answer generation.
"""

from typing import Literal

from langgraph.graph import END, START, StateGraph

from src.agents.nodes.generation import generate_answer_node
from src.agents.nodes.grading import documents_grader_node
from src.agents.nodes.query_generation import multi_query_generation_node
from src.agents.nodes.retrieval import retrieval_node
from src.agents.nodes.router import router_node
from src.agents.nodes.web_search import web_search_node
from src.agents.state import GraphState


def should_continue(state: GraphState) -> Literal["generate", "web_search"]:
    """Determine next step after document grading.

    Args:
        state: Current graph state with graded documents.

    Returns:
        "generate" if documents exist, "web_search" otherwise.
    """
    documents = state.get("documents", [])
    if not documents:
        return "web_search"
    return "generate"


def create_graph() -> StateGraph:
    """Create and compile the RAG agent graph.

    Returns:
        Compiled LangGraph state machine for RAG execution.
    """
    graph = StateGraph(GraphState)

    # Add nodes
    graph.add_node("generate_queries", multi_query_generation_node)
    graph.add_node("retrieve", retrieval_node)
    graph.add_node("grade_docs", documents_grader_node)
    graph.add_node("generate", generate_answer_node)
    graph.add_node("web_search", web_search_node)

    # Add conditional edges from START
    graph.add_conditional_edges(
        START,
        router_node,
        {
            "vectorstore": "generate_queries",
            "web_search": "web_search",
        },
    )

    # Add edges between nodes
    graph.add_edge("generate_queries", "retrieve")
    graph.add_edge("retrieve", "grade_docs")

    # Conditional edges based on document relevance
    graph.add_conditional_edges(
        "grade_docs",
        should_continue,
        {
            "generate": "generate",
            "web_search": "web_search",
        },
    )

    graph.add_edge("web_search", "generate")
    graph.add_edge("generate", END)

    return graph.compile()
