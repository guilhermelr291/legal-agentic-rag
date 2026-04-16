from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field
from typing import Literal
from langchain_openai import ChatOpenAI
from my_agent.utils.state import MessagesState
from my_agent.utils.state import GraphState
from langchain_tavily import TavilySearch
from typing import List



llm = ChatOpenAI(model="gpt-5-nano")

class RouteQuery(BaseModel):
    datasource: Literal["vectorstore", "web_search"] = Field(
        description="Route to vectorstore for Python topics or web_search for general knowledge"
    )


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

prompt_optimized_web_search = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant and your task is to transform the user question into a search query optimized for tavily search."),
    ("human", "User question: {question}"),
])

optimized_web_search_chain = prompt_optimized_web_search | llm

def web_search_node(state: GraphState) -> GraphState:
    question = state["messages"][-1].content
    optimized_query = optimized_web_search_chain.invoke({"question": question})
    tavily_results = tavily_tool.run(optimized_query.content)
    return {"documents": tavily_results}









generate_answer_llm = ChatOpenAI(model="gpt-5-nano")

generate_answer_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are a helpful assistant. Your task is to generate a response to the user question based ONLY on the documents provided.

Rules:
1. Do not make up any information not present in the documents
2. If you don't know the answer, say "I don't know"
3. Use markdown to format your response
4. Include sources in your response
5. Think step by step and critique your answer before generating the final response

Important: Your thought process MUST be between the tags <think> and </think>. This section will NOT be shown to the user.

Use exactly this format:
<think>
Your step-by-step reasoning here
</think>

<answer>
Your final response here with markdown formatting and sources
</answer>"""),
("human", """Documents:
{documents} \n\n

User question: {question}"""),
])

generate_answer_chain = generate_answer_prompt | generate_answer_llm

def generate_answer_node(state: GraphState) -> GraphState:
    documents = state["documents"]
    question = state["messages"][-1].content
    generation = generate_answer_chain.invoke({"documents": documents, "question": question})
    return {"generation": generation}





class QueryTranslation(BaseModel):
    queries: List[str] = Field(description="5 different search queries for the user question")


query_translation_prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant and your task is to generate 5 different search queries for the user question. The queries should cover different aspects of the question and should be optimized for semantic similarity and bm25 (hybrid search)"),
    ("human", "User question: {question}"),
])

query_translation_chain = query_translation_prompt | llm.with_structured_output(QueryTranslation)


def query_translation_node(state: MessagesState) -> GraphState:
    question = state["messages"][-1].content
    translation = query_translation_chain.invoke({"question": question})
    queries = translation.queries
    return {"queries_for_retrieval": queries}