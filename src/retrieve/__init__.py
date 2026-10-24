"""Runtime read path: question text -> ranked chunks (TODO Phases 3.3-4.4).

The write path (`src/ingest/`) fills Qdrant; this package only searches it.
Every search function returns `list[RetrievedChunk]`, best first, so the
future LangGraph retrieval node (Phase 5.3) and the eval harness (Phase 6)
can swap variants without rewriting anything.
"""

from __future__ import annotations

import logging
from typing import Any, Callable

from src.agent.schemas import RetrievedChunk
from src.retrieve.dense import dense_search
from src.retrieve.hybrid import hybrid_search
from src.retrieve.relevance import (
    DENSE_FLOOR,
    SPARSE_FLOOR,
    assess_relevance,
    best_retrieval_scores,
    screen_relevance_question,
)
from src.retrieve.sparse import sparse_search

logger = logging.getLogger(__name__)

__all__ = [
    "dense_search",
    "sparse_search",
    "hybrid_search",
    "make_retriever",
]


def _log_refusal(variant: str, reason: str | None, query: str) -> None:
    logger.info(
        "Retriever gate refused %s query (reason=%s): %.80s",
        variant,
        reason,
        query,
    )


def make_retriever(
    client: Any,
    collection_name: str,
    variant: str = "hybrid",
    relevance_gate: bool = True,
    dense_floor: float = DENSE_FLOOR,
    sparse_floor: float = SPARSE_FLOOR,
    **kwargs: Any,
) -> Callable[..., list[RetrievedChunk]]:
    """Build the `(query, *, top_n)` callable the future graph node will use.

    This is the LLM-callable seam without building the agent: the Phase 5
    graph imports this, and later the same function can be exposed as an
    agent tool — no rewrite needed.

    When ``relevance_gate`` is true (the default), questions that are
    descoped or have no dental retrieval signal return an empty list. The
    graph already treats empty retrieval as a fail-closed refusal, so the
    LLM never sees an off-corpus question. Set ``relevance_gate=False`` for
    raw retrieval baselines.
    """
    if variant == "dense":

        def retrieve(query: str, *, top_n: int = 5) -> list[RetrievedChunk]:
            if relevance_gate:
                precheck = screen_relevance_question(query)
                if not precheck.relevant:
                    _log_refusal(variant, precheck.reason, query)
                    return []
            hits = dense_search(
                client, collection_name, query, top_k=top_n, **kwargs
            )
            if relevance_gate:
                decision = assess_relevance(
                    hits[0].score if hits else None,
                    None,
                    dense_floor=dense_floor,
                    sparse_floor=sparse_floor,
                )
                if not decision.relevant:
                    _log_refusal(variant, decision.reason, query)
                    return []
            return hits

    elif variant == "sparse":

        def retrieve(query: str, *, top_n: int = 5) -> list[RetrievedChunk]:
            if relevance_gate:
                precheck = screen_relevance_question(query)
                if not precheck.relevant:
                    _log_refusal(variant, precheck.reason, query)
                    return []
            hits = sparse_search(
                client, collection_name, query, top_k=top_n, **kwargs
            )
            if relevance_gate:
                decision = assess_relevance(
                    None,
                    hits[0].score if hits else None,
                    dense_floor=dense_floor,
                    sparse_floor=sparse_floor,
                )
                if not decision.relevant:
                    _log_refusal(variant, decision.reason, query)
                    return []
            return hits

    elif variant == "hybrid":

        def retrieve(query: str, *, top_n: int = 5) -> list[RetrievedChunk]:
            if relevance_gate:
                precheck = screen_relevance_question(query)
                if not precheck.relevant:
                    _log_refusal(variant, precheck.reason, query)
                    return []
                dense_score, sparse_score = best_retrieval_scores(
                    client,
                    collection_name,
                    query,
                    dense_model=kwargs.get("dense_model"),
                    sparse_model=kwargs.get("sparse_model"),
                )
                decision = assess_relevance(
                    dense_score,
                    sparse_score,
                    dense_floor=dense_floor,
                    sparse_floor=sparse_floor,
                )
                if not decision.relevant:
                    _log_refusal(variant, decision.reason, query)
                    return []
            return hybrid_search(
                client, collection_name, query, top_n=top_n, **kwargs
            )

    else:
        raise ValueError(
            f"Unknown retrieval variant: {variant!r} "
            "(expected 'dense', 'sparse' or 'hybrid')"
        )

    return retrieve
