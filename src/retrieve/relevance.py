"""Deterministic off-corpus gate for retrieval (AUDIT P0.5).

The guardrail blocks diagnostic and prescriptive questions. It deliberately
lets neutral out-of-corpus questions through (for example, "What is the
capital of France?") so this layer can decide from retrieval evidence.

Two checks run before the LLM:

1. Descoped topics are refused before any embedding call. SCOPE.md §5
   descopes insurance terminology for v1, so insurance questions cannot be
   answered from the approved corpus no matter how dental-adjacent they look.
2. A question is relevant only if at least one raw retrieval signal clears
   its floor: dense cosine >= ``DENSE_FLOOR`` or sparse SPLADE >=
   ``SPARSE_FLOOR``. Raw scores are used, never RRF scores: RRF is
   rank-based and has no similarity scale (see
   ``DECISIONS/relevance-gate.md``).

The floors were measured against the 133-point demo index. The lowest
answerable golden item scored 0.447 dense / 12.74 sparse. The highest pure
off-topic item scored 0.316 dense / 7.82 sparse. The OR rule keeps exact
terminology recall while refusing questions with no dental signal.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

from src.retrieve.dense import dense_search
from src.retrieve.sparse import sparse_search

logger = logging.getLogger(__name__)

DENSE_FLOOR = 0.35
SPARSE_FLOOR = 10.0

_INSURANCE_TERMS = re.compile(
    r"\b(?:insurance|insured|deductible|premium|copay|co-?pay|"
    r"co-?payment|reimburs\w*|claim)\b"
    r"|\b(?:dental|health|medical)\s+(?:insurance\s+)?plan\b"
    r"|\b(?:plan|policy)\s+(?:cover|covers|coverage|pay|pays)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RelevanceDecision:
    """Whether a question has enough retrieval evidence to answer."""

    relevant: bool
    reason: str | None = None


def is_descoped_question(question: str) -> bool:
    """Return True for a SCOPE.md §5 topic the corpus deliberately omits."""
    return bool(_INSURANCE_TERMS.search(question))


def assess_relevance(
    dense_score: float | None,
    sparse_score: float | None,
    *,
    dense_floor: float = DENSE_FLOOR,
    sparse_floor: float = SPARSE_FLOOR,
) -> RelevanceDecision:
    """Apply the OR rule to raw dense and sparse top-1 scores."""
    if dense_score is None and sparse_score is None:
        return RelevanceDecision(False, "no_scores")

    dense_ok = dense_score is not None and dense_score >= dense_floor
    sparse_ok = sparse_score is not None and sparse_score >= sparse_floor
    if dense_ok or sparse_ok:
        return RelevanceDecision(True)
    return RelevanceDecision(False, "low_similarity")


def screen_relevance_question(question: str) -> RelevanceDecision:
    """Check question-only rules before any embedding or search call."""
    if not question or not question.strip():
        return RelevanceDecision(False, "blank")
    if is_descoped_question(question):
        return RelevanceDecision(False, "descoped_topic")
    return RelevanceDecision(True)


def screen_retrieval(
    question: str,
    dense_score: float | None,
    sparse_score: float | None,
    *,
    dense_floor: float = DENSE_FLOOR,
    sparse_floor: float = SPARSE_FLOOR,
) -> RelevanceDecision:
    """Decide whether retrieval should proceed for ``question``."""
    question_decision = screen_relevance_question(question)
    if not question_decision.relevant:
        return question_decision
    return assess_relevance(
        dense_score,
        sparse_score,
        dense_floor=dense_floor,
        sparse_floor=sparse_floor,
    )


def best_retrieval_scores(
    client: Any,
    collection_name: str,
    query_text: str,
    *,
    dense_model: str | None = None,
    sparse_model: str | None = None,
) -> tuple[float | None, float | None]:
    """Return the best dense and sparse raw scores for ``query_text``."""
    dense_hits = dense_search(
        client,
        collection_name,
        query_text,
        top_k=1,
        dense_model=dense_model,
    )
    sparse_hits = sparse_search(
        client,
        collection_name,
        query_text,
        top_k=1,
        sparse_model=sparse_model,
    )
    dense_score = dense_hits[0].score if dense_hits else None
    sparse_score = sparse_hits[0].score if sparse_hits else None
    return dense_score, sparse_score


__all__ = [
    "DENSE_FLOOR",
    "SPARSE_FLOOR",
    "RelevanceDecision",
    "assess_relevance",
    "best_retrieval_scores",
    "is_descoped_question",
    "screen_relevance_question",
    "screen_retrieval",
]
