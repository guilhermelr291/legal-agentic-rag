from my_agent.state import GraphState
from my_agent.registry import get_retriever


async def retrieval_node(state: GraphState) -> GraphState:
    queries = state["queries_for_retrieval"]
    retriever = get_retriever()
    
    results = await retriever.abatch_retrieve(queries, k=10)
    
    documents = [
        doc.page_content 
        for batch in results 
        for doc in batch
    ]
    
    return {"documents": documents}
