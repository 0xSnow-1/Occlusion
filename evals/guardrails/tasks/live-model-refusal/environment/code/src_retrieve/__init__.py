"""Runtime read path: question text -> ranked chunks (TODO Phases 3.3-4.4).

The write path (`src/ingest/`) fills Qdrant; this package only searches it.
Every search function returns `list[RetrievedChunk]`, best first, so the
future LangGraph retrieval node (Phase 5.3) and the eval harness (Phase 6)
can swap variants without rewriting anything.
"""

from __future__ import annotations

from typing import Any, Callable

from src.agent.schemas import RetrievedChunk
from src.retrieve.dense import dense_search
from src.retrieve.hybrid import hybrid_search
from src.retrieve.sparse import sparse_search

__all__ = ["dense_search", "sparse_search", "hybrid_search", "make_retriever"]


def make_retriever(
    client: Any,
    collection_name: str,
    variant: str = "hybrid",
    **kwargs: Any,
) -> Callable[..., list[RetrievedChunk]]:
    """Build the `(query, *, top_n)` callable the future graph node will use.

    This is the LLM-callable seam without building the agent: the Phase 5
    graph imports this, and later the same function can be exposed as an
    agent tool — no rewrite needed.
    """
    if variant == "dense":

        def retrieve(query: str, *, top_n: int = 5) -> list[RetrievedChunk]:
            return dense_search(
                client, collection_name, query, top_k=top_n, **kwargs
            )

    elif variant == "sparse":

        def retrieve(query: str, *, top_n: int = 5) -> list[RetrievedChunk]:
            return sparse_search(
                client, collection_name, query, top_k=top_n, **kwargs
            )

    elif variant == "hybrid":

        def retrieve(query: str, *, top_n: int = 5) -> list[RetrievedChunk]:
            return hybrid_search(
                client, collection_name, query, top_n=top_n, **kwargs
            )

    else:
        raise ValueError(
            f"Unknown retrieval variant: {variant!r} "
            "(expected 'dense', 'sparse' or 'hybrid')"
        )

    return retrieve
