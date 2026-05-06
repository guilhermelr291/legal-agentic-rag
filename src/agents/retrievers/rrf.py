"""Reciprocal Rank Fusion for merging multiple ranked document lists."""

from __future__ import annotations

import hashlib
import json

from langchain_core.documents import Document


def _document_key(doc: Document) -> str:
    """Generate unique key for a document.

    Uses document ID from metadata if available, otherwise
    generates SHA256 hash from content and metadata.

    Args:
        doc: Document to generate key for.

    Returns:
        Unique string key for the document.
    """
    doc_id = (doc.metadata or {}).get("id")
    if doc_id is not None:
        return str(doc_id)
    payload = json.dumps(
        {"content": doc.page_content, "meta": doc.metadata or {}},
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def reciprocal_rank_fusion(
    rankings: list[list[str]],
    *,
    c: float = 60.0,
) -> list[tuple[str, float]]:
    """Merge ranked identifier lists using RRF: score(d) += 1 / (c + rank).

    *c* is the smoothing constant (same role as LangChain EnsembleRetriever's ``c``;
    many papers call this *k*, often set to 60).

    Args:
        rankings: List of ranked document ID lists.
        c: RRF smoothing constant.

    Returns:
        List of (document_id, score) tuples sorted by score descending.
    """
    scores: dict[str, float] = {}
    for system_ranking in rankings:
        seen: set[str] = set()
        rank = 0
        for doc_id in system_ranking:
            if doc_id in seen:
                continue
            seen.add(doc_id)
            rank += 1
            scores[doc_id] = scores.get(doc_id, 0.0) + 1.0 / (c + rank)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def reciprocal_rank_fusion_documents(
    rankings: list[list[Document]],
    *,
    c: float = 60.0,
    top_k: int = 50,
) -> list[Document]:
    """RRF over several ranked Document lists, then return the top *top_k* docs.

    Each inner list should be ordered best-first (e.g. one list per multi-query).

    Args:
        rankings: List of ranked Document lists.
        c: RRF smoothing constant.
        top_k: Maximum number of documents to return.

    Returns:
        Fused and ranked list of documents.
    """
    if not rankings:
        return []

    id_rankings: list[list[str]] = []
    doc_store: dict[str, Document] = {}

    for system_ranking in rankings:
        row: list[str] = []
        seen: set[str] = set()
        for doc in system_ranking:
            key = _document_key(doc)
            if key in seen:
                continue
            seen.add(key)
            row.append(key)
            if key not in doc_store:
                doc_store[key] = doc
        id_rankings.append(row)

    fused = reciprocal_rank_fusion(id_rankings, c=c)
    return [doc_store[i] for i, _ in fused[:top_k] if i in doc_store]
