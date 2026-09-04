"""Shared retrieval schema (minimal slice for TODO Phases 3-4).

This module will grow the full answer/refusal contract in Phase 5.1.
For now it defines only what retrieval returns, so `src/retrieve/`
has a stable return type before any agent code exists.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class RetrievedChunk(BaseModel):
    """One ranked chunk returned by retrieval.

    Example:
        RetrievedChunk(
            doc_id="nhs-gum-disease",
            text="Brush twice a day with fluoride toothpaste ...",
            score=0.83,
            source_url="https://www.nhs.uk/conditions/gum-disease/",
        )
    """

    doc_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    score: float | None = None
    source_url: str | None = None
    title: str | None = None
