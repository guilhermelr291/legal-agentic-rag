from my_agent.state import GraphState
from my_agent.registry import get_retriever
from my_agent.retrievers.rrf import reciprocal_rank_fusion_documents

# Per multi-query: ensemble retrieve this many; RRF then collapses to RRF_TOP_K unique chunks.
PER_QUERY_K = 50
RRF_TOP_K = 50


async def retrieval_node(state: GraphState) -> GraphState:
    queries = state["queries_for_retrieval"]
    retriever = get_retriever()

    ranked_per_query = await retriever.abatch_retrieve(queries, k=PER_QUERY_K)
    fused = reciprocal_rank_fusion_documents(
        ranked_per_query,
        c=60.0,
        top_k=RRF_TOP_K,
    )
    documents = [doc.page_content for doc in fused]

    return {"documents": documents}
