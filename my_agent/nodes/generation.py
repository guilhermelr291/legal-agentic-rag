from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

from my_agent.state import GraphState
from my_agent.config.settings import get_settings


def generate_answer_node(state: GraphState) -> GraphState:
    settings = get_settings()
    llm = ChatOpenAI(model=settings.openai_model_generation)
    
    generate_answer_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a helpful assistant. Your task is to generate a response to the user question based ONLY on the documents provided.

Rules:
1. Do not make up any information not present in the documents
2. If you don't know the answer, say "I don't know"
3. Use markdown to format your response
4. Include sources in your response
5. Think step by step and critique your answer before generating the final response

Important: Your thought process MUST be between the tags <thinking> and </thinking>. This section will NOT be shown to the user.

Use exactly this format:
<thinking>
Your step-by-step reasoning here
</thinking>

<answer>
Your final response here with markdown formatting and sources
</answer>"""),
        ("human", """Documents:
{documents} \n\n

User question: {question}"""),
    ])
    generate_answer_chain = generate_answer_prompt | llm
    
    documents = state["documents"]
    question = state["messages"][-1].content
    generation = generate_answer_chain.invoke({"documents": documents, "question": question})
    
    return {"generation": generation}
