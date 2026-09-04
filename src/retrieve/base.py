"""Shared helpers for the runtime read path (TODO Phases 3.3 / 4.2)."""

from __future__ import annotations

import logging
from typing import Any, Iterable

from src.agent.schemas import RetrievedChunk

logger = logging.getLogger(__name__)


def points_to_chunks(points: Iterable[Any] | None) -> list[RetrievedChunk]:
    """Convert Qdrant scored points to self-contained `RetrievedChunk`s.

    Each point's payload already holds the chunk text and its metadata
    (see `VectorStore.upsert_documents`), so retrieval needs no second
    document store.  Points with empty text are skipped with a warning.
    """
    chunks: list[RetrievedChunk] = []
    for point in points or []:
        if isinstance(point, dict):
            payload = point.get("payload", {}) or {}
            score = point.get("score")
            point_id = point.get("id")
        else:
            payload = getattr(point, "payload", None) or {}
            score = getattr(point, "score", None)
            point_id = getattr(point, "id", None)

        text = payload.get("text", "")
        if not text:
            logger.warning("Skipping point %r: empty text in payload", point_id)
            continue

        doc_id = payload.get("doc_id") or str(point_id)
        chunks.append(
            RetrievedChunk(
                doc_id=str(doc_id),
                text=text,
                score=float(score) if score is not None else None,
                source_url=payload.get("source_url"),
                title=payload.get("title"),
            )
        )
    return chunks
