"""Citation verification post-processing (TODO Phase 5.4).

Verifies that every inline [SRC:doc_id] token in the answer exists in the
retrieved set for that query, catching "citation-shaped hallucination" — fluent
but unsupported citations.

Scope note: this checks *that* a cited id was retrieved. Whether the sentence
is actually supported by that chunk is the Ragas faithfulness check (Phase 6).
Log both signals separately.
"""

from __future__ import annotations

import re

from collections.abc import Sequence

from .schemas import Answer, CitationCheck, RetrievedChunk

SRC_TOKEN_PATTERN = re.compile(r"\[SRC:([A-Za-z0-9_./:#-]+)\]")


def extract_citations(text: str) -> list[str]:
    """Return every [SRC:doc_id] token in `text`, in order of appearance."""
    return SRC_TOKEN_PATTERN.findall(text)


def verify_citations(
    answer: Answer,
    retrieved: Sequence[RetrievedChunk],
    *,
    min_citations: int = 1,
) -> CitationCheck:
    """Verify all citations in the answer against the retrieved set.

    Policy (documented, tweak deliberately — TODO 5.4): `verified` is True only
    when every cited id was retrieved AND there is at least one citation. A bare
    answer with no grounding fails closed.
    """
    cited_ids = extract_citations(answer.answer)
    retrieved_ids = [chunk.doc_id for chunk in retrieved]
    retrieved_set = set(retrieved_ids)

    fabricated_ids = [cid for cid in cited_ids if cid not in retrieved_set]
    matches = len(cited_ids) - len(fabricated_ids)
    total = len(cited_ids)
    coverage = matches / total if total else 0.0

    return CitationCheck(
        verified=coverage == 1.0 and total >= min_citations,
        cited_ids=cited_ids,
        retrieved_ids=retrieved_ids,
        fabricated_ids=fabricated_ids,
        matches=matches,
        total=total,
        coverage=coverage,
    )


def strip_fabricated_tokens(text: str, fabricated: Sequence[str]) -> str:
    """Mask fabricated [SRC:...] tokens (one repair-policy option).

    The default gate policy refuses rather than repairs; this helper exists so
    the alternative is one call away (TODO 5.4 "deliberate policy decision").
    """
    if not fabricated:
        return text
    fabricated_set = set(fabricated)

    return re.sub(
        SRC_TOKEN_PATTERN,
        lambda m: "" if m.group(1) in fabricated_set else m.group(0),
        text,
    )