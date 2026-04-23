from langchain_core.prompts import ChatPromptTemplate
from langchain_tavily import TavilySearch

from my_agent.state import GraphState
from my_agent.registry import get_llm
from my_agent.config.settings import get_settings


async def web_search_node(state: GraphState) -> GraphState:
    llm = get_llm()
    settings = get_settings()

    tavily_tool = TavilySearch(max_results=settings.tavily_max_results)

    prompt_optimized_web_search = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant and your task is to transform the user question into a search query optimized for tavily search."),
        ("human", "User question: {question}"),
    ])
    optimized_web_search_chain = prompt_optimized_web_search | llm

    question = state["messages"][-1].content
    optimized_query = await optimized_web_search_chain.ainvoke({"question": question})
    tavily_results = await tavily_tool.ainvoke(optimized_query.content)

    return {"documents": tavily_results}
