from langchain_core.prompts import ChatPromptTemplate
from langchain_tavily import TavilySearch

from my_agent.state import GraphState
from my_agent.registry import get_llm
from my_agent.config.settings import get_settings


def web_search_node(state: GraphState) -> GraphState:
    llm = get_llm()
    settings = get_settings()
    
    tavily_tool = TavilySearch(max_results=settings.tavily_max_results)
    
    prompt_optimized_web_search = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant and your task is to transform the user question into a search query optimized for tavily search."),
        ("human", "User question: {question}"),
    ])
    optimized_web_search_chain = prompt_optimized_web_search | llm
    
    question = state["messages"][-1].content
    optimized_query = optimized_web_search_chain.invoke({"question": question})
    tavily_results = tavily_tool.run(optimized_query.content)
    
    return {"documents": tavily_results}
