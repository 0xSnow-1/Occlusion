"""Hybrid dense + sparse search with RRF fusion (TODO Phase 4.2).

Qdrant prefetch pattern: dense top_k + sparse top_k prefetches, fused
server-side with RRF.  Same return shape as `dense_search` so downstream
code and the eval harness can swap retrievers freely.
"""

from __future__ import annotations

import logging
from typing import Any

from src.agent.schemas import RetrievedChunk
from src.retrieve.base import points_to_chunks

logger = logging.getLogger(__name__)


def hybrid_search(
    client: Any,
    collection_name: str,
    query_text: str,
    top_k: int = 20,
    top_n: int = 5,
    fusion_k: int = 60,
    dense_model: str | None = None,
    sparse_model: str | None = None,
) -> list[RetrievedChunk]:
    """Return the top_n fused chunks for `query_text`, best first.

    `fusion_k` applies to the client-side `rrf_fuse` fallback path;
    server-side RRF uses Qdrant's own fusion.  Never reuse the fused
    ordering as a similarity score — RRF is rank-based.
    """
    from qdrant_client import models

    from src.ingest.vector_store import (
        DENSE_VECTOR_NAME,
        SPARSE_VECTOR_NAME,
        _DEFAULT_DENSE_MODEL,
        _DEFAULT_SPARSE_MODEL,
    )

    dense_doc = models.Document(
        text=query_text, model=dense_model or _DEFAULT_DENSE_MODEL
    )
    sparse_doc = models.Document(
        text=query_text, model=sparse_model or _DEFAULT_SPARSE_MODEL
    )
    try:
        response = client.query_points(
            collection_name=collection_name,
            prefetch=[
                models.Prefetch(
                    query=dense_doc, using=DENSE_VECTOR_NAME, limit=top_k
                ),
                models.Prefetch(
                    query=sparse_doc, using=SPARSE_VECTOR_NAME, limit=top_k
                ),
            ],
            query=models.FusionQuery(fusion=models.Fusion.RRF),
            limit=top_n,
            with_payload=True,
        )
    except Exception as exc:
        # Older servers / `:memory:` modes without fusion support fall back
        # to client-side RRF over the two independent searches.  The
        # fallback re-raises genuine errors (bad collection, down server)
        # from the underlying calls.
        logger.warning(
            "Server-side RRF unavailable (%s); falling back to client-side rrf_fuse",
            exc,
        )
        from src.agent.fusion import rrf_fuse
        from src.retrieve.dense import dense_search
        from src.retrieve.sparse import sparse_search

        dense_hits = dense_search(
            client,
            collection_name,
            query_text,
            top_k=top_k,
            dense_model=dense_model or _DEFAULT_DENSE_MODEL,
        )
        sparse_hits = sparse_search(
            client,
            collection_name,
            query_text,
            top_k=top_k,
            sparse_model=sparse_model or _DEFAULT_SPARSE_MODEL,
        )
        return rrf_fuse(dense_hits, sparse_hits, k=fusion_k, top_n=top_n)

    chunks = points_to_chunks(response.points)
    logger.info(
        "hybrid_search: query=%r top_k=%d top_n=%d hits=%d",
        query_text[:80],
        top_k,
        top_n,
        len(chunks),
    )
    return chunks
