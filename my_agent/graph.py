from langgraph.graph import StateGraph, END, START
from typing import Literal

from my_agent.state import GraphState
from my_agent.nodes.router import router_node
from my_agent.nodes.retrieval import retrieval_node
from my_agent.nodes.query_generation import multi_query_generation_node
from my_agent.nodes.grading import documents_grader_node
from my_agent.nodes.generation import generate_answer_node
from my_agent.nodes.web_search import web_search_node



def should_continue(state: GraphState) -> Literal["generate", "web_search"]:
    documents = state.get("documents", [])
    if not documents:
        return "web_search"
    return "generate"


def create_graph():
    graph = StateGraph(GraphState)
    
    graph.add_node("generate_queries", multi_query_generation_node)
    graph.add_node("retrieve", retrieval_node)
    graph.add_node("grade_docs", documents_grader_node)
    graph.add_node("generate", generate_answer_node)
    graph.add_node("web_search", web_search_node)

    graph.add_conditional_edges(
        START,
        router_node,
        {
            "vectorstore": "generate_queries",
            "web_search": "web_search"
        }
    )
    
    graph.add_edge("generate_queries", "retrieve")
    graph.add_edge("retrieve", "grade_docs")
    
    graph.add_conditional_edges(
        "grade_docs",
        should_continue,
        {
            "generate": "generate",
            "web_search": "web_search"
        }
    )
    
    graph.add_edge("web_search", "generate")
    graph.add_edge("generate", END)
    
    return graph.compile()
