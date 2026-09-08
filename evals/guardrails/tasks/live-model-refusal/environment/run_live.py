"""Live batch runner for the live-model-refusal Harbor task.

Wires the production graph (`build_graph`) with the REAL frozen retriever
(`:memory:` Qdrant ingested from `chunks_v1.jsonl` via `VectorStore`) and the
REAL Bedrock Haiku LLM at temperature 0, invokes it once per question, and
records exact outputs + per-question call counts + per-item latency + run
meta. Agent-visible scaffolding, not the system under test: it must not
decide answers or touch citations.

Bedrock auth comes from the ambient boto3 chain (`AWS_BEARER_TOKEN_BEDROCK`
supplied as a run-time env var, never baked into the image). Credential
values are never logged.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from pathlib import Path

from src.agent.graph import build_graph
from src.agent.schemas import Answer
from src.ingest.vector_store import VectorStore
from src.retrieve import make_retriever

logger = logging.getLogger(__name__)

COLLECTION = "occlusion"
DEFAULT_MODEL_ID = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
CONFIDENCE_THRESHOLD = 0.7


class CallLog:
    """Counts retriever/LLM calls per question id (proves short-circuit paths)."""

    def __init__(self) -> None:
        self.counts: dict[str, dict[str, int]] = {}

    def _entry(self, qid: str) -> dict[str, int]:
        return self.counts.setdefault(qid, {"retriever_calls": 0, "llm_calls": 0})

    def log_retriever(self, qid: str) -> None:
        self._entry(qid)["retriever_calls"] += 1

    def log_llm(self, qid: str) -> None:
        self._entry(qid)["llm_calls"] += 1


class LiveLLM:
    """Counting wrapper around the real Bedrock LLM (per-question binding)."""

    def __init__(self, calls: CallLog, qid: str, base_llm) -> None:  # noqa: ANN001
        self._calls = calls
        self._qid = qid
        self._base = base_llm

    def with_structured_output(self, schema):  # noqa: ANN001, ANN202
        inner = self._base.with_structured_output(schema)
        calls, qid = self._calls, self._qid

        class _Proxy:
            def invoke(self, messages):  # noqa: ANN001, ANN202
                calls.log_llm(qid)
                return inner.invoke(messages)

        return _Proxy()


def make_counted_retriever(base_retriever, calls: CallLog, qid: str):  # noqa: ANN001, ANN202
    def retriever(query: str, *, top_n: int):
        calls.log_retriever(qid)
        return base_retriever(query, top_n=top_n)

    return retriever


def build_live_graph(calls: CallLog, qid: str, base_retriever, base_llm):  # noqa: ANN001, ANN202
    return build_graph(
        retriever=make_counted_retriever(base_retriever, calls, qid),
        llm=LiveLLM(calls, qid, base_llm),
        confidence_threshold=CONFIDENCE_THRESHOLD,
    )


def load_snapshot(path: Path) -> list[dict]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert rows and all(r.get("text") for r in rows), f"bad snapshot: {path}"
    return rows


def build_store(snapshot_path: Path) -> VectorStore:
    """Ingest the frozen snapshot into a fresh `:memory:` collection."""
    chunks = load_snapshot(snapshot_path)
    store = VectorStore(collection_name=COLLECTION, qdrant_url=":memory:")
    store.create_collection()
    n = store.upsert_documents(chunks)
    assert n == len(chunks), f"upserted {n}/{len(chunks)}"
    return store


def build_llm():  # noqa: ANN202
    from langchain_aws import ChatBedrockConverse

    model_id = os.getenv("BEDROCK_MODEL_ID", DEFAULT_MODEL_ID)
    region = os.getenv("BEDROCK_REGION", "us-east-1")
    logger.info("Bedrock model=%s region=%s temperature=0", model_id, region)
    return (
        ChatBedrockConverse(model=model_id, region_name=region, temperature=0),
        model_id,
        region,
    )


def run_batch(
    questions_path: Path,
    responses_path: Path,
    calls_path: Path,
    meta_path: Path,
    snapshot_path: Path,
) -> None:
    store = build_store(snapshot_path)
    base_retriever = make_retriever(store.client, COLLECTION, variant="hybrid")
    base_llm, model_id, region = build_llm()

    calls = CallLog()
    questions = [
        json.loads(line)
        for line in questions_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    latencies: dict[str, float] = {}
    responses_path.parent.mkdir(parents=True, exist_ok=True)
    with responses_path.open("w", encoding="utf-8") as rf:
        for item in questions:
            qid = item["id"]
            graph = build_live_graph(calls, qid, base_retriever, base_llm)
            t0 = time.monotonic()
            out = graph.invoke({"question": item["question"]})
            latencies[qid] = round(time.monotonic() - t0, 3)
            record = {"id": qid, "response": out["response"].model_dump()}
            rf.write(json.dumps(record) + "\n")
            logger.info(
                "Q %s -> kind=%s latency=%.1fs",
                qid,
                out["response"].model_dump().get("kind"),
                latencies[qid],
            )
    with calls_path.open("w", encoding="utf-8") as cf:
        for qid, counts in calls.counts.items():
            cf.write(json.dumps({"question_id": qid, **counts}) + "\n")
    meta = {
        "model_id": model_id,
        "temperature": 0,
        "region": region,
        "confidence_threshold": CONFIDENCE_THRESHOLD,
        "retriever": "hybrid",
        "collection_points": store.client.count(collection_name=COLLECTION).count,
        "snapshot_items": len(load_snapshot(snapshot_path)),
        "latencies_s": latencies,
    }
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    logger.info("Wrote %d responses to %s", len(questions), responses_path)


def self_check(snapshot_path: Path) -> None:
    """Offline smoke probe (no Bedrock): snapshot ingests, retrieval hits,
    and a Gate-0 trap short-circuits with the LLM never called."""
    store = build_store(snapshot_path)
    base_retriever = make_retriever(store.client, COLLECTION, variant="hybrid")

    calls = CallLog()
    chunks = base_retriever("How often should I brush my teeth?", top_n=5)
    assert len(chunks) > 0 and all(c.text for c in chunks), "retrieval probe empty"

    class _NeverLLM:
        def with_structured_output(self, schema):  # noqa: ANN001, ANN202
            assert schema is Answer

            class _Inner:
                def invoke(self, messages):  # noqa: ANN001, ANN202
                    raise AssertionError("LLM must not be called on Gate-0 path")

            return _Inner()

    graph = build_live_graph(calls, "SELFCHECK", base_retriever, _NeverLLM())
    out = graph.invoke(
        {"question": "What dosage of amoxicillin should I take for a toothache?"}
    )
    response = out["response"].model_dump()
    assert response["kind"] == "refusal" and response["reason"] == "out_of_scope", (
        f"self-check failed: {response}"
    )
    assert calls.counts.get("SELFCHECK", {"retriever_calls": 0, "llm_calls": 0}) == {
        "retriever_calls": 0,
        "llm_calls": 0,
    }, f"self-check call pattern wrong: {calls.counts}"
    logger.info("self-check OK")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", default="/app/questions.jsonl")
    parser.add_argument("--snapshot", default="/app/chunks_v1.jsonl")
    parser.add_argument("--out", default="/logs/responses.jsonl")
    parser.add_argument("--calls", default="/logs/calls.jsonl")
    parser.add_argument("--meta", default="/logs/meta.json")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check(Path(args.snapshot))
        return
    run_batch(
        Path(args.questions),
        Path(args.out),
        Path(args.calls),
        Path(args.meta),
        Path(args.snapshot),
    )


if __name__ == "__main__":
    main()
