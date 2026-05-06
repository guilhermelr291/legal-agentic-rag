"""Answer generation node for final response creation."""

from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from src.agents.config import agents_settings
from src.agents.state import GraphState


async def generate_answer_node(state: GraphState) -> dict:
    """Generate final answer based on retrieved documents.

    Uses the configured generation model to create a response
    based only on the provided documents, with citation support.

    Args:
        state: Current graph state with documents and user question.

    Returns:
        Dict with generation key containing the LLM response.
    """
    llm = ChatOpenAI(model=agents_settings.OPENAI_MODEL_GENERATION)

    generate_answer_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are a helpful assistant. Your task is to generate a response to the user question based ONLY on the documents provided.

Rules:
1. Do not make up any information not present in the documents
2. If you don't know the answer, say "I don't know"
3. Use markdown to format your response
4. Include sources at the end of each sentence of your response using [1], [2], [3], etc.
5. Think step by step and critique your answer before generating the final response

Important: Your thought process MUST be between the tags <thinking> and </thinking>. This section will NOT be shown to the user.

Use exactly this format:
<thinking>
Your step-by-step reasoning here
</thinking>

<answer>
Your final response here with markdown formatting and sources
</answer>""",
            ),
            (
                "human",
                """Documents:
{documents} \n\n

User question: {question}""",
            ),
        ]
    )
    generate_answer_chain = generate_answer_prompt | llm

    documents = state["documents"]
    question = state["messages"][-1].content
    generation = await generate_answer_chain.ainvoke({"documents": documents, "question": question})

    return {"generation": generation}
