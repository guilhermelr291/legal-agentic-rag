"""Rerankers module for document relevance reranking.

Provides base reranker interface and Cohere implementation
for reordering retrieved documents based on query relevance.
"""

from src.agents.rerankers.base import Reranker
from src.agents.rerankers.cohere import CohereReranker

__all__ = [
    "Reranker",
    "CohereReranker",
]
