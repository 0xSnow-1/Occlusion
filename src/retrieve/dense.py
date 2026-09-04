"""Dense-only search: the TODO 3.3 baseline (no LLM involved)."""

from __future__ import annotations

import logging
from typing import Any

from src.agent.schemas import RetrievedChunk
from src.retrieve.base import points_to_chunks

logger = logging.getLogger(__name__)


def dense_search(
    client: Any,
    collection_name: str,
    query_text: str,
    top_k: int = 20,
    dense_model: str | None = None,
) -> list[RetrievedChunk]:
    """Embed `query_text` and return the top_k cosine matches.

    The embedding model default lives in `src.ingest.vector_store`
    (single source of truth — never hardcode the dimension here).
    Returns `(chunk, score)` pairs as `RetrievedChunk`s, best first.
    """
    from qdrant_client import models

    from src.ingest.vector_store import DENSE_VECTOR_NAME, _DEFAULT_DENSE_MODEL

    response = client.query_points(
        collection_name=collection_name,
        query=models.Document(
            text=query_text, model=dense_model or _DEFAULT_DENSE_MODEL
        ),
        using=DENSE_VECTOR_NAME,
        limit=top_k,
        with_payload=True,
    )
    chunks = points_to_chunks(response.points)
    logger.info(
        "dense_search: query=%r top_k=%d hits=%d",
        query_text[:80],
        top_k,
        len(chunks),
    )
    return chunks
