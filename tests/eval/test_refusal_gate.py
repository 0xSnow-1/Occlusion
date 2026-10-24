"""Deterministic refusal and provenance contracts for the eval corpus.

These tests never call a model. They pin the two guarantees that can be
checked offline:

1. Every diagnostic/prescriptive golden item is blocked by the
   deterministic guardrail before retrieval.
2. The frozen eval snapshot is grounded in the approved corpus and contains
   none of the rejected ``data/raw/_archive/`` sources.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.agent.guardrail import screen_question
from src.eval.golden import load_golden_set, validate_against_chunks

REPO_ROOT = Path(__file__).resolve().parents[2]
GOLDEN = REPO_ROOT / "data/golden_set_v1.jsonl"
FROZEN_CHUNKS = (
    REPO_ROOT
    / "evals/guardrails/tasks/live-model-refusal/environment/chunks_v1.jsonl"
)

ARCHIVE_DOC_IDS = frozenset(
    {
        "AAPD_Pediatric_Local_Anesthesia",
        "AHA_ADA_Antibiotic_Prophylaxis_Guidelines",
        "IADT_Traumatic_Dental_Injuries_Guidelines",
        "Uniform-Glossary-01-2020",
    }
)


def test_every_diagnostic_refusal_is_blocked_by_guardrail():
    items = load_golden_set(GOLDEN)
    diagnostic = [
        item for item in items if item.expected_behavior == "refuse_diagnostic"
    ]

    assert diagnostic, "golden set must keep its diagnostic trap items"

    for item in diagnostic:
        decision = screen_question(item.question)
        assert not decision.allowed, f"{item.id} was allowed: {item.question}"
        assert decision.rule, f"{item.id} was flagged without a rule"


def test_golden_answer_items_ground_in_frozen_snapshot():
    items = load_golden_set(GOLDEN)

    summary = validate_against_chunks(items, FROZEN_CHUNKS)

    assert summary["items"] == len(items)
    assert summary["chunk_doc_ids"] > 0


def test_frozen_snapshot_excludes_archive_sources():
    doc_ids = {
        json.loads(line)["doc_id"]
        for line in FROZEN_CHUNKS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }

    assert not (ARCHIVE_DOC_IDS & doc_ids)
