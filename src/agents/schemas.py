"""Pydantic schemas for agents domain.

Request/response models for agent queries and responses.
All schemas inherit from CustomModel for consistent datetime serialization.
"""

from typing import Literal

from pydantic import Field

from src.common.models import CustomModel


class QueryRequest(CustomModel):
    """Request schema for agent query.

    Attributes:
        query: User question to be answered.
        datasource: Optional override for data source selection.
    """

    query: str = Field(..., min_length=1, description="User question to be answered")
    datasource: Literal["vectorstore", "web_search", "auto"] = Field(
        default="auto",
        description="Data source: auto (router decides), vectorstore, or web_search",
    )


class QueryResponse(CustomModel):
    """Response schema for agent query.

    Attributes:
        answer: Generated answer with citations.
        sources: List of document sources used for generation.
        confidence: Confidence score for the answer.
    """

    answer: str = Field(..., description="Generated answer with citations")
    sources: list[str] = Field(default_factory=list, description="Document sources used")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Answer confidence score")


class AgentStatusResponse(CustomModel):
    """Response schema for agent status check.

    Attributes:
        status: Current status of the agent.
        llm_configured: Whether LLM is ready for use.
        retriever_configured: Whether retriever is ready for use.
        reranker_configured: Whether reranker is ready for use.
    """

    status: Literal["ready", "not_ready"] = Field(..., description="Agent status")
    llm_configured: bool = Field(default=False, description="LLM configuration status")
    retriever_configured: bool = Field(default=False, description="Retriever configuration status")
    reranker_configured: bool = Field(default=False, description="Reranker configuration status")
