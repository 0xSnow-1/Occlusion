"""Optional cross-encoder rerank stage.

Off by default. `hybrid_search(rerank=True)` opts in. fastembed is
imported inside the loader so importing this module stays offline and
light.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any

from src.agent.schemas import RetrievedChunk

logger = logging.getLogger(__name__)

DEFAULT_RERANK_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"

_RERANKERS: dict[str, Any] = {}


def _load_reranker(model_name: str) -> Any:
    encoder = _RERANKERS.get(model_name)
    if encoder is None:
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        encoder = TextCrossEncoder(model_name)
        _RERANKERS[model_name] = encoder
    return encoder


def rerank_chunks(
    query: str,
    chunks: Sequence[RetrievedChunk],
    top_n: int = 5,
    model_name: str | None = None,
) -> list[RetrievedChunk]:
    """Rescore `chunks` with a cross-encoder and return the best `top_n`.

    Cross-encoder scores replace the incoming scores; every other field is
    preserved. An empty input returns before any model load.
    """
    if not chunks:
        return []
    encoder = _load_reranker(model_name or DEFAULT_RERANK_MODEL)
    scores = encoder.rerank(query, [chunk.text for chunk in chunks])
    ranked = sorted(zip(scores, chunks), key=lambda pair: pair[0], reverse=True)
    return [
        chunk.model_copy(update={"score": float(score)})
        for score, chunk in ranked[:top_n]
    ]
