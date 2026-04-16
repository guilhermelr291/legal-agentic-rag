from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import Literal
from langchain_openai import ChatOpenAI
from my_agent.utils.state import MessagesState

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




