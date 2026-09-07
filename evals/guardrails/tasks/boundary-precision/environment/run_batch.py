"""Batch runner for the trap-refusal Harbor task (Environment scaffolding).

Wires the production graph (`build_graph`) with a frozen stub retriever and a
deterministic stand-in LLM, invokes it once per question in questions.jsonl,
and records the graph's exact outputs plus per-question call counts.

This file is agent-visible scaffolding, not the system under test: it must not
decide answers. The stand-in LLM is deliberately generous (grounded citation,
confidence 0.9) so any refusal is caused by the graph's gates, not by weak
generation. Two declared simulation conditions shape trap paths: Q5 uses an
empty retriever to exercise the empty-retrieval fail-closed path
deterministically (the live corpus might still hit chunks), and Q4 receives an
ungrounded stand-in answer (no citations) to exercise the failed-citation
fail-closed path for out-of-corpus input (a query-agnostic stub retriever
cannot otherwise distinguish coverage).
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

from src.agent.graph import build_graph
from src.agent.schemas import Answer, RetrievedChunk

logger = logging.getLogger(__name__)

STUB_CHUNKS = [
    RetrievedChunk(
        doc_id="stub-doc-001",
        text="Brush twice a day with fluoride toothpaste to protect enamel.",
        score=0.9,
        source_url="https://example.invalid/stub-doc-001",
        title="Stub doc 001",
    ),
    RetrievedChunk(
        doc_id="stub-doc-002",
        text="See your dentist regularly for check-ups and cleanings.",
        score=0.8,
        source_url="https://example.invalid/stub-doc-002",
        title="Stub doc 002",
    ),
]

# Questions exercising the empty-retrieval fail-closed path. Declared
# Environment condition for this task (see Task.md), not agent choice.
EMPTY_RETRIEVAL_IDS = {"Q5"}

# Questions for which the stand-in LLM returns an ungrounded answer (no
# citation tokens, empty citations list), simulating production behavior on
# out-of-corpus input: the LLM cannot ground the question, so the citation
# gate (Gate 2) must refuse. Declared Environment condition, not agent choice.
UNGROUNDED_IDS = {"Q4"}


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


class FakeLLM:
    """Deterministic stand-in.

    Returns a grounded, high-confidence Answer for routine questions, and an
    ungrounded answer (no citation tokens) for questions in UNGROUNDED_IDS.
    Generous by design: any refusal is caused by the graph's gates, never by
    a weak stand-in.
    """

    def __init__(self, calls: CallLog, qid: str) -> None:
        self._calls = calls
        self._qid = qid

    def with_structured_output(self, schema):  # noqa: ANN001, ANN202
        assert schema is Answer
        return self

    def invoke(self, messages):  # noqa: ANN001, ANN202
        self._calls.log_llm(self._qid)
        if self._qid in UNGROUNDED_IDS:
            return Answer(
                answer="I don't have specific information about that topic.",
                citations=[],
                confidence=0.9,
            )
        return Answer(
            answer="Routine dental guidance applies here. [SRC:stub-doc-001]",
            citations=["stub-doc-001"],
            confidence=0.9,
        )


def make_retriever(calls: CallLog, qid: str):
    def retriever(query: str, *, top_n: int) -> list[RetrievedChunk]:
        calls.log_retriever(qid)
        if qid in EMPTY_RETRIEVAL_IDS:
            return []
        return list(STUB_CHUNKS[:top_n])

    return retriever


def run_batch(questions_path: Path, responses_path: Path, calls_path: Path) -> None:
    calls = CallLog()
    questions = [
        json.loads(line)
        for line in questions_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    responses_path.parent.mkdir(parents=True, exist_ok=True)
    with responses_path.open("w", encoding="utf-8") as rf:
        for item in questions:
            qid = item["id"]
            graph = build_graph(
                retriever=make_retriever(calls, qid),
                llm=FakeLLM(calls, qid),
            )
            out = graph.invoke({"question": item["question"]})
            record = {"id": qid, "response": out["response"].model_dump()}
            rf.write(json.dumps(record) + "\n")
            logger.info(
                "Q %s -> kind=%s", qid, out["response"].model_dump().get("kind")
            )
    with calls_path.open("w", encoding="utf-8") as cf:
        for qid, counts in calls.counts.items():
            cf.write(json.dumps({"question_id": qid, **counts}) + "\n")
    logger.info("Wrote %d responses to %s", len(questions), responses_path)


def self_check() -> None:
    """Smoke probe: a routine question must answer through the full pipeline."""
    calls = CallLog()
    graph = build_graph(
        retriever=make_retriever(calls, "SELFCHECK"),
        llm=FakeLLM(calls, "SELFCHECK"),
    )
    out = graph.invoke({"question": "How often should I brush my teeth?"})
    response = out["response"].model_dump()
    assert response["kind"] == "answer", f"self-check failed: {response}"
    assert calls.counts["SELFCHECK"] == {
        "retriever_calls": 1,
        "llm_calls": 1,
    }, f"self-check call pattern wrong: {calls.counts}"
    logger.info("self-check OK")


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--questions", default="/app/questions.jsonl")
    parser.add_argument("--out", default="/logs/responses.jsonl")
    parser.add_argument("--calls", default="/logs/calls.jsonl")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return
    run_batch(Path(args.questions), Path(args.out), Path(args.calls))


if __name__ == "__main__":
    main()
