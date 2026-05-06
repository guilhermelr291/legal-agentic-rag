"""Dependencies for agents domain.

Provides dependency injection helpers for FastAPI routes.
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status

from src.agents.config import AgentsConfig, agents_settings
from src.agents.registry import get_llm, get_reranker, get_retriever


def get_agents_config() -> AgentsConfig:
    """Dependency to get agents configuration."""
    return agents_settings


def check_agent_ready() -> dict:
    """Dependency to verify agent components are configured.

    Raises:
        HTTPException: If required components are not configured.

    Returns:
        Status dict with component configuration states.
    """
    status_result = {
        "llm_configured": False,
        "retriever_configured": False,
        "reranker_configured": False,
    }

    try:
        get_llm()
        status_result["llm_configured"] = True
    except RuntimeError:
        pass

    try:
        get_retriever()
        status_result["retriever_configured"] = True
    except RuntimeError:
        pass

    try:
        get_reranker()
        status_result["reranker_configured"] = True
    except RuntimeError:
        pass

    if not status_result["llm_configured"]:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent not ready: LLM not configured",
        )

    return status_result


# Type aliases for Annotated dependencies
AgentsConfigDep = Annotated[AgentsConfig, Depends(get_agents_config)]
AgentReadyDep = Annotated[dict, Depends(check_agent_ready)]
