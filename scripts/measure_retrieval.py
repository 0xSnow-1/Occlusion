"""Retrieval metrics for dense, hybrid, and hybrid plus rerank.

Rebuild the frozen 120-chunk snapshot in a fresh ``:memory:`` collection,
run every answerable golden question, and record recall@5, MRR@5, top-1
accuracy, and p50/p95 retrieval latency.

``--compare`` refuses two result files measured on different snapshots or
golden sets. It then writes one side-by-side Markdown report with the
per-question wins and losses.

Usage:
    uv run python scripts/measure_retrieval.py --variant hybrid
    uv run python scripts/measure_retrieval.py --variant hybrid --rerank
    uv run python scripts/measure_retrieval.py --compare OFF.json ON.json \
        --out-md eval/results/rerank_comparison.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import math
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.eval.golden import GoldenItem, load_golden_set, validate_against_chunks
from src.ingest.vector_store import VectorStore
from src.retrieve import make_retriever

logger = logging.getLogger("measure_retrieval")

COLLECTION = "occlusion"
SNAPSHOT_PATH = (
    "evals/guardrails/tasks/live-model-refusal/environment/chunks_v1.jsonl"
)
GOLDEN_PATH = "data/golden_set_v1.jsonl"
RESULTS_DIR = "eval/results"
RERANK_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"
WARMUP_QUESTION = "How often should I brush my teeth?"


def _sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_snapshot(path: str | Path) -> list[dict]:
    rows = [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows and all(row.get("text") for row in rows), f"bad snapshot: {path}"
    return rows


def _build_store(snapshot_path: str | Path) -> VectorStore:
    chunks = _load_snapshot(snapshot_path)
    store = VectorStore(collection_name=COLLECTION, qdrant_url=":memory:")
    store.create_collection()
    count = store.upsert_documents(chunks)
    assert count == len(chunks), f"upserted {count}/{len(chunks)}"
    return store


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * pct / 100.0
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return ordered[low]
    return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)


def _rank_of_first_relevant(
    retrieved_doc_ids: list[str], relevant: set[str]
) -> int | None:
    for position, doc_id in enumerate(retrieved_doc_ids, start=1):
        if doc_id in relevant:
            return position
    return None


def _evaluate(
    retriever, items: list[GoldenItem], top_n: int
) -> list[dict]:
    records: list[dict] = []
    for item in items:
        relevant = set(item.doc_ids)
        started = time.perf_counter()
        chunks = retriever(item.question, top_n=top_n)
        latency_ms = (time.perf_counter() - started) * 1000.0
        retrieved = [chunk.doc_id for chunk in chunks]
        rank = _rank_of_first_relevant(retrieved, relevant)
        recall = len(relevant & set(retrieved)) / len(relevant)
        records.append(
            {
                "id": item.id,
                "question": item.question,
                "relevant_doc_ids": sorted(relevant),
                "retrieved_doc_ids": retrieved,
                "recall_at_k": round(recall, 6),
                "first_relevant_rank": rank,
                "reciprocal_rank": round(1.0 / rank, 6) if rank else 0.0,
                "top1": rank == 1,
                "hit_at_k": rank is not None,
                "latency_ms": round(latency_ms, 3),
            }
        )
    return records


def _summary(records: list[dict], top_n: int) -> dict:
    latencies = [record["latency_ms"] for record in records]
    return {
        f"recall_at_{top_n}": round(
            sum(record["recall_at_k"] for record in records) / len(records), 6
        ),
        f"mrr_at_{top_n}": round(
            sum(record["reciprocal_rank"] for record in records) / len(records),
            6,
        ),
        "top1_accuracy": round(
            sum(record["top1"] for record in records) / len(records), 6
        ),
        f"hit_rate_at_{top_n}": round(
            sum(record["hit_at_k"] for record in records) / len(records), 6
        ),
        "p50_ms": round(_percentile(latencies, 50), 3),
        "p95_ms": round(_percentile(latencies, 95), 3),
        "mean_ms": round(sum(latencies) / len(latencies), 3),
        "min_ms": round(min(latencies), 3),
        "max_ms": round(max(latencies), 3),
    }


def _run(args: argparse.Namespace) -> int:
    if args.rerank and args.variant != "hybrid":
        raise SystemExit("--rerank needs --variant hybrid")

    items = load_golden_set(args.golden)
    validate_against_chunks(items, args.snapshot)
    answerable = [item for item in items if item.expected_behavior == "answer"]

    store = _build_store(args.snapshot)
    kwargs: dict = {}
    if args.rerank:
        kwargs["rerank"] = True
        kwargs["rerank_model"] = args.rerank_model
    retriever = make_retriever(
        store.client,
        COLLECTION,
        variant=args.variant,
        relevance_gate=False,
        **kwargs,
    )

    warmup_started = time.perf_counter()
    retriever(WARMUP_QUESTION, top_n=args.top_n)
    warmup_ms = round((time.perf_counter() - warmup_started) * 1000.0, 3)

    records = _evaluate(retriever, answerable, args.top_n)
    payload = {
        "meta": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "variant": args.variant,
            "rerank": bool(args.rerank),
            "rerank_model": args.rerank_model if args.rerank else None,
            "relevance_gate": False,
            "top_n": args.top_n,
            "snapshot_path": args.snapshot,
            "snapshot_sha256": _sha256(args.snapshot),
            "snapshot_items": len(_load_snapshot(args.snapshot)),
            "golden_path": args.golden,
            "golden_sha256": _sha256(args.golden),
            "golden_items": len(items),
            "answerable_items": len(answerable),
            "warmup_ms": warmup_ms,
            "python": platform.python_version(),
        },
        "summary": _summary(records, args.top_n),
        "per_question": records,
    }

    out = Path(args.out) if args.out else Path(RESULTS_DIR) / (
        f"retrieval_{args.variant}{'_rerank' if args.rerank else ''}_"
        f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    logger.info("Wrote %s", out)

    summary = payload["summary"]
    print(f"{out}")
    print(
        f"{args.variant}{' + rerank' if args.rerank else ''}: "
        f"recall@{args.top_n}={summary[f'recall_at_{args.top_n}']:.4f} "
        f"MRR@{args.top_n}={summary[f'mrr_at_{args.top_n}']:.4f} "
        f"top1={summary['top1_accuracy']:.4f} "
        f"p50={summary['p50_ms']:.1f}ms p95={summary['p95_ms']:.1f}ms"
    )
    return 0


def _rank_label(rank: int | None) -> str:
    return str(rank) if rank else "miss"


def _compare(args: argparse.Namespace) -> int:
    baseline = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
    candidate = json.loads(Path(args.candidate).read_text(encoding="utf-8"))
    for key in ("snapshot_sha256", "golden_sha256", "top_n"):
        left = baseline["meta"][key]
        right = candidate["meta"][key]
        if left != right:
            raise SystemExit(
                f"refusing to compare different {key}: {left!r} vs {right!r}"
            )

    top_n = baseline["meta"]["top_n"]
    off = baseline["summary"]
    on = candidate["summary"]
    off_records = {row["id"]: row for row in baseline["per_question"]}
    on_records = {row["id"]: row for row in candidate["per_question"]}

    rows = [
        (f"recall@{top_n}", off[f"recall_at_{top_n}"], on[f"recall_at_{top_n}"]),
        (f"MRR@{top_n}", off[f"mrr_at_{top_n}"], on[f"mrr_at_{top_n}"]),
        ("top-1 accuracy", off["top1_accuracy"], on["top1_accuracy"]),
        (f"hit rate@{top_n}", off[f"hit_rate_at_{top_n}"], on[f"hit_rate_at_{top_n}"]),
        ("p50 latency (ms)", off["p50_ms"], on["p50_ms"]),
        ("p95 latency (ms)", off["p95_ms"], on["p95_ms"]),
        ("mean latency (ms)", off["mean_ms"], on["mean_ms"]),
    ]

    improved: list[tuple[str, str, int | None, int | None]] = []
    worsened: list[tuple[str, str, int | None, int | None]] = []
    top_n_misses = 0
    for item_id, off_row in off_records.items():
        on_row = on_records[item_id]
        before = off_row["first_relevant_rank"]
        after = on_row["first_relevant_rank"]
        before_rank = before if before else top_n + 1
        after_rank = after if after else top_n + 1
        if after_rank < before_rank:
            improved.append((item_id, off_row["question"], before, after))
        elif after_rank > before_rank:
            worsened.append((item_id, off_row["question"], before, after))
        if before is None and after is None:
            top_n_misses += 1

    def _lines(items: list[tuple[str, str, int | None, int | None]]) -> list[str]:
        if not items:
            return ["_None._", ""]
        lines = [
            "| id | question | off rank | on rank |",
            "|---|---|---|---|",
        ]
        for item_id, question, before, after in items:
            lines.append(
                f"| {item_id} | {question} | {_rank_label(before)} | "
                f"{_rank_label(after)} |"
            )
        return lines + [""]

    label = candidate["meta"]["variant"]
    if candidate["meta"]["rerank"]:
        label += " + rerank"
    off_label = baseline["meta"]["variant"]
    if baseline["meta"]["rerank"]:
        off_label += " + rerank"

    report = [
        "# Rerank comparison",
        "",
        "## Snapshot",
        "",
        f"- Snapshot: `{baseline['meta']['snapshot_path']}` "
        f"({baseline['meta']['snapshot_items']} chunks, "
        f"sha256 `{baseline['meta']['snapshot_sha256'][:16]}`)",
        f"- Golden set: `{baseline['meta']['golden_path']}` "
        f"({baseline['meta']['answerable_items']} answerable items, "
        f"sha256 `{baseline['meta']['golden_sha256'][:16]}`)",
        f"- Top n: {top_n}; relevance gate off; identical snapshot asserted.",
        "",
        "## Side by side",
        "",
        f"| metric | {off_label} | {label} | delta |",
        "|---|---:|---:|---:|",
    ]
    for name, before, after in rows:
        report.append(f"| {name} | {before} | {after} | {after - before:+.4f} |")
    report += [
        "",
        "## Ordering movement",
        "",
        f"- First relevant chunk ranked higher: {len(improved)}",
        f"- Unchanged: {len(off_records) - len(improved) - len(worsened)}",
        f"- Ranked lower: {len(worsened)}",
        f"- Missed in both runs: {top_n_misses}",
        "",
        "### Wins",
        "",
        *_lines(improved),
        "### Losses",
        "",
        *_lines(worsened),
    ]

    out = Path(args.out_md)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(report) + "\n", encoding="utf-8")
    logger.info("Wrote %s", out)
    print(f"{out}")
    return 0


def main() -> int:
    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variant", choices=["dense", "hybrid"], default="hybrid")
    parser.add_argument("--rerank", action="store_true")
    parser.add_argument("--rerank-model", default=RERANK_MODEL)
    parser.add_argument("--snapshot", default=SNAPSHOT_PATH)
    parser.add_argument("--golden", default=GOLDEN_PATH)
    parser.add_argument("--top-n", type=int, default=5)
    parser.add_argument("--out")
    parser.add_argument("--compare", nargs=2, metavar=("BASELINE", "CANDIDATE"))
    parser.add_argument("--out-md", default=f"{RESULTS_DIR}/rerank_comparison.md")
    args = parser.parse_args()

    if args.compare:
        args.baseline, args.candidate = args.compare
        return _compare(args)
    return _run(args)


if __name__ == "__main__":
    raise SystemExit(main())
