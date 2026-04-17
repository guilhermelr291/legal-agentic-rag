from typing import Literal
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate

from my_agent.state import MessagesState
from my_agent.registry import get_llm


class RouteQuery(BaseModel):
    datasource: Literal["vectorstore", "web_search"] = Field(
        description="Route to vectorstore for Python topics or web_search for general knowledge"
    )


def router_node(state: MessagesState) -> Literal["vectorstore", "web_search"]:
    llm = get_llm()
    
    structured_llm = llm.with_structured_output(RouteQuery)
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an expert at routing questions. Use vectorstore for Python topics, web_search otherwise."),
        ("human", "{question}"),
    ])
    router_chain = prompt | structured_llm
    
    question = state["messages"][-1].content
    result = router_chain.invoke({"question": question})
    return result.datasource
