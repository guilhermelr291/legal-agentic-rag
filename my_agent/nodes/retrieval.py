from my_agent.config.settings import get_settings
from my_agent.registry import get_retriever, get_reranker
from my_agent.retrievers.rrf import reciprocal_rank_fusion_documents
from my_agent.state import GraphState

PER_QUERY_K = 50
RRF_TOP_K = 50


async def retrieval_node(state: GraphState) -> GraphState:
    queries = state["queries_for_retrieval"]
    user_query = state["messages"][-1].content
    retriever = get_retriever()

    ranked_per_query = await retriever.abatch_retrieve(queries, k=PER_QUERY_K)

    fused = reciprocal_rank_fusion_documents(
        ranked_per_query,
        c=60.0,
        top_k=RRF_TOP_K,
    )

    settings = get_settings()
    final_k = settings.rerank_top_k

    try:
        reranker = get_reranker()
        fused = await reranker.arerank(user_query, fused, top_k=final_k)
    except RuntimeError:
        fused = fused[:final_k]

    documents = [doc.page_content for doc in fused]
    return {"documents": documents}
