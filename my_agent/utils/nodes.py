from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import Literal
from langchain_openai import ChatOpenAI
from my_agent.utils.state import MessagesState
from my_agent.utils.state import GraphState
from langchain_tavily import TavilySearch



class RouteQuery(BaseModel):
    datasource: Literal["vectorstore", "web_search"] = Field(
        description="Route to vectorstore for Python topics or web_search for general knowledge"
    )

llm = ChatOpenAI(model="gpt-5-nano")
structured_llm = llm.with_structured_output(RouteQuery)
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are an expert at routing questions. Use vectorstore for Python topics, web_search otherwise."),
    ("human", "{question}"),
])

router_chain = prompt | structured_llm



def router_node(state: MessagesState) -> Literal["vectorstore", "web_search"]:
    question = state["messages"][-1].content
    result = router_chain.invoke({"question": question})
    return result.datasource




tavily_tool = TavilySearch(max_results=5)


llm_optimized_web_search = ChatOpenAI(model="gpt-5-nano")
prompt_optimized_web_search = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant and your task is to transform the user question into a search query optimized for tavily search."),
    ("human", "User question: {question}"),
])

optimized_web_search_chain = prompt_optimized_web_search | llm_optimized_web_search

def web_search_node(state: GraphState) -> GraphState:
    question = state["messages"][-1].content
    optimized_query = optimized_web_search_chain.invoke({"question": question})
    tavily_results = tavily_tool.run(optimized_query.content)
    return {"documents": tavily_results}


