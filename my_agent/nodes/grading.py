from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate

from my_agent.state import GraphState
from my_agent.registry import get_llm


class IsDocumentRelevant(BaseModel):
    binary_score: str = Field(
        description="Document is relevant to the user question, 'yes' or 'no'"
    )


async def documents_grader_node(state: GraphState) -> GraphState:
    llm = get_llm()
    
    documents_grader_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a helpful assistant and your task is to grade the document as relevant or not relevant to the user question. :
    1. The document should be relevant to the user question
    2. The document should be not relevant to the user question
    """),
        ("human", "Document: {document} \n\n User question: {question}"),
    ])
    documents_grader_chain = documents_grader_prompt | llm.with_structured_output(IsDocumentRelevant)
    
    documents = state["documents"]
    question = state["messages"][-1].content
    
    if not documents:
        return {"documents": []}
    
    inputs = [
        {"document": document, "question": question} 
        for document in documents
    ]
    
    results = await documents_grader_chain.abatch(inputs)
    
    relevant_documents = [
        doc for doc, result in zip(documents, results) 
        if result.binary_score.lower() == "yes"
    ]
    
    return {"documents": relevant_documents}
