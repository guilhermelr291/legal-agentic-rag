from typing import List
from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate

from my_agent.state import GraphState
from my_agent.registry import get_llm


class MultiQueryGeneration(BaseModel):
    queries: List[str] = Field(
        description="5 different search queries for the user question"
    )


def multi_query_generation_node(state: GraphState) -> GraphState:
    llm = get_llm()
    
    multi_query_generation_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant and your task is to generate 5 different search queries for the user question. The queries should cover different aspects of the question and should be optimized for semantic similarity and bm25 (hybrid search)"),
        ("human", "User question: {question}"),
    ])
    multi_query_generation_chain = multi_query_generation_prompt | llm.with_structured_output(MultiQueryGeneration)
    
    question = state["messages"][-1].content
    translation = multi_query_generation_chain.invoke({"question": question})
    queries = translation.queries
    
    return {"queries_for_retrieval": queries}
