"""Ragas baseline harness (TODO Phase 6): answer quality on the golden set.

Runs the live graph (repo-local Qdrant + Bedrock Haiku generator) over the
70 answerable golden items, scores the answered ones with Ragas using a
DISTINCT judge model (Bedrock Sonnet — never the generator), and writes a
versioned JSON report. Refused items are NOT Ragas-scored (a refusal has no
answer to ground); they are reported separately — refusal strictness already
has its own Harbor evals.

Cost discipline: Bedrock judge calls scale with items × metrics. Always run
`--limit 3` smoke first (cents), then the full baseline once. No repeats
without human approval.

Usage:
    uv run python -m src.eval.ragas.run_ragas --limit 3        # smoke (plumbing)
    uv run python -m src.eval.ragas.run_ragas                  # full baseline (~70)

Requires: collection `occlusion` ingested (`scripts/run_ingest.py`),
`AWS_BEARER_TOKEN_BEDROCK` in the environment, `data/golden_set_v1.jsonl`.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import src.eval.ragas._ragas_compat  # noqa: F401  (vertexai stub; see module docstring)
from src.agent.graph import build_graph
from src.eval.golden import load_golden_set
from src.ingest.vector_store import VectorStore
from src.retrieve import make_retriever

logger = logging.getLogger(__name__)

COLLECTION = "occlusion"
GENERATOR_MODEL_ID = os.getenv(
    "BEDROCK_MODEL_ID", "global.anthropic.claude-haiku-4-5-20251001-v1:0"
)
JUDGE_MODEL_ID = os.getenv(
    "BEDROCK_JUDGE_MODEL_ID",
    "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
)
REGION = os.getenv("BEDROCK_REGION", "us-east-1")

# SCOPE.md §6 ship thresholds (note: upstream renamed Answer Relevancy to
# Response Relevancy — same metric).
THRESHOLDS = {
    "faithfulness": 0.85,
    "response_relevancy": 0.80,
    "context_precision": 0.75,
}


def collect_samples(limit: int | None) -> tuple[list[dict], list[str]]:
    """Run the live graph over golden answer items; return Ragas-ready
    sample dicts plus the ids refused (unscored)."""
    from langchain_aws import ChatBedrockConverse

    items = [
        i for i in load_golden_set("data/golden_set_v1.jsonl")
        if i.expected_behavior == "answer"
    ]
    if limit:
        items = items[:limit]

    store = VectorStore(collection_name=COLLECTION)
    if not store.client.collection_exists(COLLECTION):
        raise SystemExit(
            "Collection 'occlusion' not found. "
            "Run `uv run python scripts/run_ingest.py` first."
        )
    retriever = make_retriever(store.client, COLLECTION, variant="hybrid")
    llm = ChatBedrockConverse(
        model=GENERATOR_MODEL_ID, region_name=REGION, temperature=0
    )
    graph = build_graph(retriever=retriever, llm=llm, confidence_threshold=0.7)

    samples, refused = [], []
    for item in items:
        chunks = retriever(item.question, top_n=5)
        out = graph.invoke({"question": item.question})
        response = out["response"]
        if response.kind != "answer":
            refused.append(item.id)
            logger.info("%s -> refused (%s)", item.id, response.reason)
            continue
        samples.append(
            {
                "id": item.id,
                "user_input": item.question,
                "retrieved_contexts": [c.text for c in chunks],
                "retrieved_doc_ids": [c.doc_id for c in chunks],
                "response": response.answer,
                "reference": item.reference,
            }
        )
        logger.info("%s -> answered (%d contexts)", item.id, len(chunks))
    return samples, refused


def score_samples(samples: list[dict]) -> list[dict]:
    """Score with Ragas (Sonnet judge, local embeddings for relevancy)."""
    from langchain_aws import ChatBedrockConverse
    from langchain_huggingface import HuggingFaceEmbeddings
    from ragas import EvaluationDataset, SingleTurnSample, evaluate
    from ragas.embeddings import LangchainEmbeddingsWrapper
    from ragas.llms import LangchainLLMWrapper
    from ragas.metrics import (
        Faithfulness,
        LLMContextPrecisionWithReference,
        LLMContextRecall,
        ResponseRelevancy,
    )

    judge = LangchainLLMWrapper(
        ChatBedrockConverse(model=JUDGE_MODEL_ID, region_name=REGION, temperature=0)
    )
    embeddings = LangchainEmbeddingsWrapper(
        HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    )
    metrics = [
        Faithfulness(llm=judge),
        ResponseRelevancy(llm=judge, embeddings=embeddings),
        LLMContextPrecisionWithReference(llm=judge),
        LLMContextRecall(llm=judge),
    ]
    dataset = EvaluationDataset(
        samples=[
            SingleTurnSample(
                user_input=s["user_input"],
                retrieved_contexts=s["retrieved_contexts"],
                response=s["response"],
                reference=s["reference"],
            )
            for s in samples
        ]
    )
    result = evaluate(dataset=dataset, metrics=metrics)
    frame = result.to_pandas()
    # Column names are the metrics' registered names (e.g. ResponseRelevancy
    # scores into `answer_relevancy`); resolve dynamically, never hardcode.
    name_of = {type(m).__name__: m.name for m in metrics}
    cols = {
        "faithfulness": name_of["Faithfulness"],
        "response_relevancy": name_of["ResponseRelevancy"],
        "context_precision": name_of["LLMContextPrecisionWithReference"],
        "context_recall": name_of["LLMContextRecall"],
    }
    scored = []
    for s, (_, row) in zip(samples, frame.iterrows(), strict=True):
        entry = {"id": s["id"], "retrieved_doc_ids": s["retrieved_doc_ids"]}
        for key, col in cols.items():
            value = row.get(col)
            entry[key] = None if value is None else float(value)
        scored.append(entry)
    return scored


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--out", default="src/eval/ragas/results/ragas_baseline_v1.json")
    args = parser.parse_args()

    samples, refused = collect_samples(args.limit)
    logger.info(
        "collected %d answer samples, %d refused: %s",
        len(samples), len(refused), refused,
    )
    scored = score_samples(samples) if samples else []
    def _mean(key: str) -> float | None:
        import math

        vals = [s[key] for s in scored
                if s[key] is not None and not (isinstance(s[key], float) and math.isnan(s[key]))]
        return round(sum(vals) / len(vals), 4) if vals else None

    means = {k: _mean(k) for k in (
        "faithfulness", "response_relevancy", "context_precision", "context_recall")}
    verdict = {
        metric: {"mean": means.get(metric), "threshold": thr,
                 "pass": means.get(metric) is not None and means[metric] >= thr}
        for metric, thr in THRESHOLDS.items()
    }
    report = {
        "generator": GENERATOR_MODEL_ID,
        "judge": JUDGE_MODEL_ID,
        "items_scored": len(scored),
        "items_refused_unscored": refused,
        "means": means,
        "thresholds": verdict,
        "items": scored,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    logger.info("means=%s refused=%d report=%s", means, len(refused), out)
    for metric, v in verdict.items():
        logger.info(
            "%s mean=%.3f vs %.2f -> %s",
            metric, v["mean"] or 0.0, v["threshold"],
            "PASS" if v["pass"] else "FAIL",
        )


if __name__ == "__main__":
    main()
