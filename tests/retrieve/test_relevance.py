"""AUDIT P0.5 - deterministic off-corpus gate.

The gate has two contracts:

1. Pure score logic: raw dense OR sparse evidence passes; both below floor
   refuses. RRF scores are never used because they are rank-based.
2. Retriever wiring: an off-topic or descoped question returns no chunks,
   so the existing graph path refuses without calling the LLM.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.eval.negative import load_negative_set
from src.retrieve import make_retriever
from src.retrieve.relevance import (
    assess_relevance,
    is_descoped_question,
    screen_retrieval,
)


def _point(pid: int, doc_id: str, text: str, score: float):
    return SimpleNamespace(
        id=pid,
        score=score,
        payload={
            "doc_id": doc_id,
            "text": text,
            "source_url": "https://example.com",
        },
    )


class _ScoreClient:
    """Fake Qdrant client with separate dense, sparse, and fused scores."""

    def __init__(
        self,
        dense_score: float,
        sparse_score: float,
        fused: list | None = None,
    ):
        self.dense_score = dense_score
        self.sparse_score = sparse_score
        self.fused = fused or [_point(0, "doc-1", "fused text", 0.9)]
        self.calls: list[dict] = []

    def query_points(self, **kwargs):
        self.calls.append(kwargs)
        if "prefetch" in kwargs:
            return SimpleNamespace(points=self.fused)
        using = kwargs.get("using")
        score = self.dense_score if using == "dense" else self.sparse_score
        return SimpleNamespace(
            points=[_point(9, f"{using}-doc", f"{using} text", score)]
        )


class TestScoreGate:
    def test_dense_alone_can_pass(self):
        assert assess_relevance(0.50, 0.0).relevant

    def test_sparse_alone_can_pass(self):
        assert assess_relevance(0.10, 12.0).relevant

    def test_both_below_floor_refuses(self):
        decision = assess_relevance(0.30, 8.0)
        assert not decision.relevant
        assert decision.reason == "low_similarity"

    def test_missing_scores_fail_closed(self):
        decision = assess_relevance(None, None)
        assert not decision.relevant
        assert decision.reason == "no_scores"

    def test_thresholds_are_injectable(self):
        assert assess_relevance(0.20, 6.0, dense_floor=0.15).relevant
        assert assess_relevance(0.20, 6.0, sparse_floor=5.0).relevant


class TestDescopedTopics:
    @pytest.mark.parametrize(
        "question",
        [
            "What's my dental insurance deductible?",
            "Does my dental plan cover a root canal?",
            "How much is my copay for a filling?",
            "What is my annual dental premium?",
            "How do I file a dental insurance claim?",
            "Does my policy pay for a crown?",
        ],
    )
    def test_insurance_phrasings_are_descoped(self, question: str):
        assert is_descoped_question(question)

    @pytest.mark.parametrize(
        "question",
        [
            "What is gum disease?",
            "What are the benefits of flossing?",
            "What should I bring to my dental visit?",
            "How do braces straighten teeth and who gets them on the NHS?",
            "What is a treatment plan for a root canal?",
        ],
    )
    def test_answerable_phrasings_are_not_descoped(self, question: str):
        assert not is_descoped_question(question)

    def test_insurance_refused_even_with_high_scores(self):
        decision = screen_retrieval(
            "What's my dental insurance deductible?", 0.9, 20.0
        )
        assert not decision.relevant
        assert decision.reason == "descoped_topic"

    def test_blank_refused(self):
        decision = screen_retrieval("   ", 0.9, 20.0)
        assert not decision.relevant
        assert decision.reason == "blank"


class TestRetrieverGate:
    def test_hybrid_refuses_low_scores_before_fusion(self):
        client = _ScoreClient(dense_score=0.10, sparse_score=5.0)
        retriever = make_retriever(client, "col", variant="hybrid")

        assert retriever("What is the capital of France?", top_n=5) == []
        assert len(client.calls) == 2
        assert all("prefetch" not in call for call in client.calls)

    def test_hybrid_passes_answerable_scores(self):
        client = _ScoreClient(dense_score=0.50, sparse_score=15.0)
        retriever = make_retriever(client, "col", variant="hybrid")

        out = retriever("How do I brush my teeth?", top_n=5)

        assert [chunk.doc_id for chunk in out] == ["doc-1"]
        assert len(client.calls) == 3

    def test_hybrid_refuses_descoped_without_any_query(self):
        client = _ScoreClient(dense_score=0.90, sparse_score=30.0)
        retriever = make_retriever(client, "col", variant="hybrid")

        assert retriever("What's my dental insurance deductible?", top_n=5) == []
        assert client.calls == []

    def test_dense_refuses_low_score_without_extra_query(self):
        client = _ScoreClient(dense_score=0.10, sparse_score=99.0)
        retriever = make_retriever(client, "col", variant="dense")

        assert retriever("What is the capital of France?", top_n=5) == []
        assert len(client.calls) == 1

    def test_gate_can_be_disabled_for_raw_baselines(self):
        client = _ScoreClient(dense_score=0.10, sparse_score=5.0)
        retriever = make_retriever(
            client, "col", variant="dense", relevance_gate=False
        )

        out = retriever("What is the capital of France?", top_n=5)

        assert [chunk.doc_id for chunk in out] == ["dense-doc"]


class TestNegativeSet:
    def test_negative_set_parses_and_covers_both_categories(self):
        items = load_negative_set("data/negative_set_v1.jsonl")
        assert len(items) == 12
        assert {item.category for item in items} == {"off_topic", "insurance"}
