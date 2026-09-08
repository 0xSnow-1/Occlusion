"""Sparse-only (BM25-style) search: the exact-terminology path (TODO Phase 4.1).

Same return shape as `dense_search` so the eval harness can swap them
freely.  Used standalone to prove the Phase 3.3 motivation case (a
specific term dense search ranks poorly) and as one half of hybrid.
"""

from __future__ import annotations

import logging
from typing import Any

from src.agent.schemas import RetrievedChunk
from src.retrieve.base import points_to_chunks

logger = logging.getLogger(__name__)


def sparse_search(
    client: Any,
    collection_name: str,
    query_text: str,
    top_k: int = 20,
    sparse_model: str | None = None,
) -> list[RetrievedChunk]:
    """Return the top_k sparse-vector matches for `query_text`, best first."""
    from qdrant_client import models

    from src.ingest.vector_store import SPARSE_VECTOR_NAME, _DEFAULT_SPARSE_MODEL

    response = client.query_points(
        collection_name=collection_name,
        query=models.Document(
            text=query_text, model=sparse_model or _DEFAULT_SPARSE_MODEL
        ),
        using=SPARSE_VECTOR_NAME,
        limit=top_k,
        with_payload=True,
    )
    chunks = points_to_chunks(response.points)
    logger.info(
        "sparse_search: query=%r top_k=%d hits=%d",
        query_text[:80],
        top_k,
        len(chunks),
    )
    return chunks
