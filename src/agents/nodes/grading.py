"""Document grading node for relevance assessment."""

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from src.agents.registry import get_llm
from src.agents.state import GraphState


class IsDocumentRelevant(BaseModel):
    """Output schema for document relevance grading."""

    binary_score: str = Field(
        description="Document is relevant to the user question, 'yes' or 'no'"
    )


async def documents_grader_node(state: GraphState) -> dict:
    """Grade documents for relevance to user query.

    Uses LLM to determine if each document is relevant to the question,
    filtering out irrelevant documents.

    Args:
        state: Current graph state with documents to grade.

    Returns:
        Dict with filtered documents list.
    """
    llm = get_llm()

    documents_grader_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a helpful assistant and your task is to grade the document as relevant or not relevant to the user question.
        Return 'yes' if the document is relevant to the user question, 'no' otherwise.
    """,
            ),
            ("human", "Document: {document} \n\n User question: {question}"),
        ]
    )
    documents_grader_chain = documents_grader_prompt | llm.with_structured_output(
        IsDocumentRelevant
    )

    documents = state["documents"]
    question = state["messages"][-1].content

    if not documents:
        return {"documents": []}

    inputs = [{"document": document, "question": question} for document in documents]

    results = await documents_grader_chain.abatch(inputs)

    relevant_documents = [
        doc
        for doc, result in zip(documents, results, strict=False)
        if result.binary_score.lower() == "yes"
    ]

    return {"documents": relevant_documents}
