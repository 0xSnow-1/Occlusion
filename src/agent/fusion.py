"""Reciprocal Rank Fusion over dense + sparse ranked lists (TODO Phase 4.2).

Fuses on *rank*, not raw score: dense cosine scores and sparse BM25 scores
live on incompatible scales, so a doc's fused score is the sum of
``1 / (k + rank)`` over each list it appears in.  A doc in both lists
therefore outranks a doc that is rank-1 in only one list.
"""

from __future__ import annotations

import logging
from typing import Sequence

from src.agent.schemas import RetrievedChunk

logger = logging.getLogger(__name__)


def rrf_fuse(
    dense: Sequence[RetrievedChunk],
    sparse: Sequence[RetrievedChunk],
    k: int = 60,
    top_n: int = 5,
) -> list[RetrievedChunk]:
    """Fuse two ranked chunk lists with Reciprocal Rank Fusion.

    Parameters
    ----------
    dense, sparse:
        Already-ranked chunks (best first) from each search path.
    k:
        Dampening constant from the RRF paper (default 60).  Larger k
        compresses rank differences; smaller k rewards top ranks more.
    top_n:
        How many fused chunks to keep, best first.
    """
    scores: dict[str, float] = {}
    by_id: dict[str, RetrievedChunk] = {}

    for results in (dense, sparse):
        for rank, chunk in enumerate(results, start=1):
            scores[chunk.doc_id] = scores.get(chunk.doc_id, 0.0) + 1.0 / (k + rank)
            if chunk.doc_id not in by_id:
                by_id[chunk.doc_id] = chunk

    # Stable sort: ties keep first-seen order (dense list first).
    ranked = sorted(scores, key=lambda doc_id: scores[doc_id], reverse=True)
    fused = [by_id[doc_id] for doc_id in ranked[:top_n]]
    logger.debug(
        "rrf_fuse: dense=%d sparse=%d unique=%d returned=%d",
        len(dense),
        len(sparse),
        len(ranked),
        len(fused),
    )
    return fused
