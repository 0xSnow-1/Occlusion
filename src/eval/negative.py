"""Negative-set schema and loader for the off-corpus gate (AUDIT P0.5).

The golden set measures answerable and trap questions. This smaller set
measures questions the corpus must refuse for coverage reasons that the
guardrail deliberately allows through: neutral off-topic questions and
SCOPE.md §5 insurance terminology. It is data for threshold measurement,
not part of the frozen eval snapshot.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

NegativeCategory = Literal["off_topic", "insurance"]


class NegativeItem(BaseModel):
    """One negative-set row."""

    id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    category: NegativeCategory


def load_negative_set(path: str | Path) -> list[NegativeItem]:
    """Parse and validate every negative row (duplicate ids fail fast)."""
    items = [
        NegativeItem.model_validate(json.loads(line))
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    ids = [i.id for i in items]
    assert len(ids) == len(set(ids)), "duplicate negative ids"
    return items


__all__ = ["NegativeCategory", "NegativeItem", "load_negative_set"]
