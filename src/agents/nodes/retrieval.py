"""Document retrieval node with RRF fusion and reranking."""

from src.agents.config import agents_settings
from src.agents.registry import get_reranker, get_retriever
from src.agents.retrievers.rrf import reciprocal_rank_fusion_documents
from src.agents.state import GraphState

PER_QUERY_K = 50
RRF_TOP_K = 50


async def retrieval_node(state: GraphState) -> dict:
    """Retrieve documents using multi-query and RRF fusion.

    Performs batched retrieval for each query, fuses results using
    Reciprocal Rank Fusion, then applies optional reranking.

    Args:
        state: Current graph state with queries for retrieval.

    Returns:
        Dict with documents key containing retrieved document contents.
    """
    queries = state["queries_for_retrieval"]
    user_query = state["messages"][-1].content
    retriever = get_retriever()

    ranked_per_query = await retriever.abatch_retrieve(queries, k=PER_QUERY_K)

    fused = reciprocal_rank_fusion_documents(
        ranked_per_query,
        c=60.0,
        top_k=RRF_TOP_K,
    )

    final_k = agents_settings.RERANK_TOP_K

    try:
        reranker = get_reranker()
        fused = await reranker.arerank(user_query, fused, top_k=final_k)
    except RuntimeError:
        fused = fused[:final_k]

    documents = [doc.page_content for doc in fused]
    return {"documents": documents}
