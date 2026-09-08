"""Golden-set schema and validation (TODO Phase 2).

`data/golden_set_v1.jsonl` is the versioned, human-reviewed ground truth:
70 answerable patient-education items (hand-drafted, programmatically
checked) + 8 adversarial items (trilogy-seeded, SCOPE-justified). Never
overwrite it — cut a v2 instead.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, model_validator

ExpectedBehavior = Literal["answer", "refuse_diagnostic", "refuse_no_coverage"]


class GoldenItem(BaseModel):
    """One golden-set row. `reference`/`doc_ids` are empty exactly when the
    item must be refused (adversarial); every answer item needs both."""

    id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    reference: str | None = None
    doc_ids: list[str] = Field(default_factory=list)
    expected_behavior: ExpectedBehavior
    scope_line: str = Field(min_length=1)

    @model_validator(mode="after")
    def _reference_matches_behavior(self) -> GoldenItem:
        if self.expected_behavior == "answer" and not self.reference:
            raise ValueError("answer items need a reference")
        if self.expected_behavior != "answer" and self.reference:
            raise ValueError("refusal items must not carry a reference")
        if self.expected_behavior == "answer" and not self.doc_ids:
            raise ValueError("answer items need grounding doc_ids")
        return self


def load_golden_set(path: str | Path) -> list[GoldenItem]:
    """Parse + schema-validate every row (duplicate ids fail fast)."""
    items = [
        GoldenItem.model_validate(json.loads(line))
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    ids = [i.id for i in items]
    assert len(ids) == len(set(ids)), "duplicate golden ids"
    return items


def validate_against_chunks(
    items: list[GoldenItem], chunks_path: str | Path
) -> dict[str, int]:
    """Every answer item's doc_ids must exist in the chunk snapshot."""
    valid = {
        json.loads(line)["doc_id"]
        for line in Path(chunks_path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    bad = [
        i.id for i in items if not set(i.doc_ids) <= valid
    ]
    assert not bad, f"unknown doc_ids in items: {bad}"
    return {"items": len(items), "chunk_doc_ids": len(valid)}
