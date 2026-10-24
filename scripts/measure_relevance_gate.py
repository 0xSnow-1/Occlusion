"""Measure the P0.5 relevance gate against the golden and negative sets.

This is the threshold lever: it reruns the real local embedding stack, so
it needs the 133-point index and cached fastembed models. It is not part of
CI. Run it after any corpus, model, or floor change and record the result in
``DECISIONS/relevance-gate.md``.

Usage:
    uv run python scripts/measure_relevance_gate.py
    uv run python scripts/measure_relevance_gate.py --dense-floor 0.35
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.eval.golden import load_golden_set
from src.eval.negative import load_negative_set
from src.ingest.vector_store import VectorStore
from src.retrieve.relevance import (
    DENSE_FLOOR,
    SPARSE_FLOOR,
    best_retrieval_scores,
    screen_retrieval,
)

logger = logging.getLogger("measure_relevance_gate")

GOLDEN_PATH = "data/golden_set_v1.jsonl"
NEGATIVE_PATH = "data/negative_set_v1.jsonl"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qdrant-path", default="./data/qdrant_storage")
    parser.add_argument("--collection", default="occlusion")
    parser.add_argument("--golden", default=GOLDEN_PATH)
    parser.add_argument("--negative", default=NEGATIVE_PATH)
    parser.add_argument("--dense-floor", type=float, default=DENSE_FLOOR)
    parser.add_argument("--sparse-floor", type=float, default=SPARSE_FLOOR)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    store = VectorStore(
        collection_name=args.collection,
        qdrant_url=args.qdrant_path,
    )
    if not store.client.collection_exists(args.collection):
        raise SystemExit(
            f"Collection {args.collection!r} not found at {args.qdrant_path}. "
            "Run `uv run python scripts/run_ingest.py` first."
        )

    rows: list[dict] = []
    for item in load_golden_set(args.golden):
        if item.expected_behavior == "refuse_diagnostic":
            expected = None
            expected_label = "guardrail"
        else:
            expected = item.expected_behavior == "answer"
            expected_label = "answer" if expected else "refuse"
        rows.append(
            {
                "id": item.id,
                "question": item.question,
                "expected": expected,
                "expected_label": expected_label,
            }
        )
    for item in load_negative_set(args.negative):
        rows.append(
            {
                "id": item.id,
                "question": item.question,
                "expected": False,
                "expected_label": "refuse",
            }
        )

    false_accepts = []
    false_refusals = []
    for row in rows:
        dense_score, sparse_score = best_retrieval_scores(
            store.client,
            args.collection,
            row["question"],
        )
        decision = screen_retrieval(
            row["question"],
            dense_score,
            sparse_score,
            dense_floor=args.dense_floor,
            sparse_floor=args.sparse_floor,
        )
        row.update(
            {
                "relevant": decision.relevant,
                "reason": decision.reason,
                "dense": dense_score,
                "sparse": sparse_score,
            }
        )
        if row["expected"] is False and decision.relevant:
            false_accepts.append(row)
        elif row["expected"] is True and not decision.relevant:
            false_refusals.append(row)
        print(
            f"{row['id']:>3}  expected={row['expected_label']:<9}  "
            f"got={'answer' if decision.relevant else 'refuse':<6}  "
            f"reason={decision.reason or '-':<16}  "
            f"dense={dense_score if dense_score is not None else float('nan'):.3f}  "
            f"sparse={sparse_score if sparse_score is not None else float('nan'):.2f}  "
            f"{row['question']}"
        )

    skipped = sum(1 for row in rows if row["expected"] is None)
    print()
    print(
        f"{len(rows)} items: {len(false_accepts)} false accepts, "
        f"{len(false_refusals)} false refusals "
        f"({skipped} diagnostic items handled by the guardrail)"
    )
    if false_accepts:
        print("False accepts:")
        for row in false_accepts:
            print(f"  {row['id']} {row['question']}")
    if false_refusals:
        print("False refusals:")
        for row in false_refusals:
            print(f"  {row['id']} {row['question']}")
    return 1 if false_accepts or false_refusals else 0


if __name__ == "__main__":
    raise SystemExit(main())
