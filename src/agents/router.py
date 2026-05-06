"""API router for agents domain.

Provides endpoints for querying the RAG agent and checking status.
Uses Annotated[..., Depends(...)] pattern for dependency injection.
"""

from fastapi import APIRouter, HTTPException, status

from src.agents.dependencies import AgentsConfigDep
from src.agents.graph import create_graph
from src.agents.registry import get_llm
from src.agents.schemas import AgentStatusResponse, QueryRequest, QueryResponse
from src.agents.state import GraphState

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get(
    "/status",
    response_model=AgentStatusResponse,
    summary="Check agent status",
    description="Check if all agent components (LLM, retriever, reranker) are configured and ready.",
)
async def get_agent_status() -> AgentStatusResponse:
    """Get current status of agent components."""
    llm_ready = False
    retriever_ready = False
    reranker_ready = False

    try:
        get_llm()
        llm_ready = True
    except RuntimeError:
        pass

    try:
        from src.agents.registry import get_retriever

        get_retriever()
        retriever_ready = True
    except RuntimeError:
        pass

    try:
        from src.agents.registry import get_reranker

        get_reranker()
        reranker_ready = True
    except RuntimeError:
        pass

    all_ready = llm_ready and retriever_ready

    return AgentStatusResponse(
        status="ready" if all_ready else "not_ready",
        llm_configured=llm_ready,
        retriever_configured=retriever_ready,
        reranker_configured=reranker_ready,
    )


@router.post(
    "/query",
    response_model=QueryResponse,
    status_code=status.HTTP_200_OK,
    summary="Query the RAG agent",
    description="Send a question to the RAG agent and receive an answer based on retrieved documents.",
)
async def query_agent(
    request: QueryRequest,
    config: AgentsConfigDep,
) -> QueryResponse:
    """Process a query through the RAG agent.

    Args:
        request: Query request with question and optional datasource override.
        config: Agent configuration.

    Returns:
        Query response with answer and sources.

    Raises:
        HTTPException: If agent components are not configured.
    """
    # Check if LLM is configured
    try:
        get_llm()
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent not ready. LLM not configured. Call init_default_llm() first.",
        ) from None

    # Check if retriever is configured
    try:
        from src.agents.registry import get_retriever

        get_retriever()
    except RuntimeError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent not ready. Retriever not configured. Call set_retriever() first.",
        ) from None

    # Create and run graph
    graph = create_graph()

    # Prepare initial state
    from langchain_core.messages import HumanMessage

    initial_state: GraphState = {
        "messages": [HumanMessage(content=request.query)],
        "documents": [],
        "generation": "",
        "queries_for_retrieval": [],
    }

    try:
        result = await graph.ainvoke(initial_state)

        # Extract answer and sources
        generation = result.get("generation")
        documents = result.get("documents", [])

        if generation is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Agent failed to generate answer",
            )

        # Extract answer content from AIMessage or string
        answer = generation.content if hasattr(generation, "content") else str(generation)

        return QueryResponse(
            answer=answer,
            sources=documents,
            confidence=0.8 if documents else 0.3,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent execution failed: {str(e)}",
        ) from e
