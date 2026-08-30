"""Reciprocal Rank Fusion (plan §3, k≈60).

TODO Phase 4.2: this is retrieval logic and belongs in `src/retrieve/` once that
package is built — the graph imports it via the `fusion_fn` parameter, so moving
it later is a one-line change.
"""

from __future__ import annotations

from collections.abc import Iterable

from .schemas import RetrievedChunk


def rrf_fuse(
    dense: Iterable[RetrievedChunk],
    sparse: Iterable[RetrievedChunk],
    *,
    k: int = 60,
    top_n: int = 5,
) -> list[RetrievedChunk]:
    """Fuse two rank lists by Reciprocal Rank Fusion.

    score(d) = sum(1 / (k + rank_i(d))), rank starting at 1.

    Fusion on *rank* rather than raw score sidesteps the different scales of
    cosine (bounded) and BM25 (unbounded) scores — the reason the plan chose
    RRF over fixed weighted blending. When a doc_id appears in both lists the
    first-encountered chunk representation is retained.
    """
    scores: dict[str, tuple[float, RetrievedChunk]] = {}

    for ranked in (dense, sparse):
        for rank, chunk in enumerate(ranked, start=1):
            doc_id = chunk.doc_id
            contribution = 1.0 / (k + rank)
            if doc_id in scores:
                total, first = scores[doc_id]
                scores[doc_id] = (total + contribution, first)
            else:
                scores[doc_id] = (contribution, chunk)

    ordered = sorted(scores.items(), key=lambda kv: kv[1][0], reverse=True)
    return [chunk for _doc_id, (_score, chunk) in ordered[:top_n]]