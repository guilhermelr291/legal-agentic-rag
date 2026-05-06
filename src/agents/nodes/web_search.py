"""Web search node for external information retrieval."""

from langchain_core.prompts import ChatPromptTemplate
from langchain_tavily import TavilySearch

from src.agents.config import agents_settings
from src.agents.registry import get_llm
from src.agents.state import GraphState


async def web_search_node(state: GraphState) -> dict:
    """Perform web search for user query.

    Optimizes the user question for Tavily search and retrieves
    results from the web when vector store doesn't have relevant docs.

    Args:
        state: Current graph state with user messages.

    Returns:
        Dict with documents key containing web search results.
    """
    llm = get_llm()

    tavily_tool = TavilySearch(max_results=agents_settings.TAVILY_MAX_RESULTS)

    prompt_optimized_web_search = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a helpful assistant and your task is to transform the user question into a search query optimized for tavily search.",
            ),
            ("human", "User question: {question}"),
        ]
    )
    optimized_web_search_chain = prompt_optimized_web_search | llm

    question = state["messages"][-1].content
    optimized_query = await optimized_web_search_chain.ainvoke({"question": question})
    tavily_results = await tavily_tool.ainvoke(optimized_query.content)

    return {"documents": tavily_results}
