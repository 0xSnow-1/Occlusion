"""Offline tests for the production pipeline adapter."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.agent.schemas import (
    Answer,
    CitationCheck,
    GuardrailDecision,
    Refusal,
    RefusalReason,
    RetrievedChunk,
)
from src.service.pipeline import GraphPipeline, PipelineUnavailable
from src.service.settings import Settings

CHUNK = RetrievedChunk(doc_id="doc-1", text="Brush twice a day.")
CHECK = CitationCheck(
    verified=True,
    cited_ids=["doc-1"],
    retrieved_ids=["doc-1"],
    matches=1,
    total=1,
    coverage=1.0,
)


class FakeStore:
    def __init__(self, *, exists: bool = True, points: int = 133) -> None:
        self.exists = exists
        self.points = points
        self.client = SimpleNamespace(
            collection_exists=lambda collection_name: self.exists,
            count=lambda collection_name: SimpleNamespace(count=self.points),
        )

    def collection_exists(self) -> bool:
        return self.exists


class FakeGraph:
    def __init__(self, state: dict) -> None:
        self.state = state
        self.calls: list[dict] = []

    def invoke(self, payload: dict) -> dict:
        self.calls.append(payload)
        return self.state


def _state(**overrides) -> dict:
    state = {
        "response": Answer(
            answer="Brush twice a day [SRC:doc-1].",
            citations=["doc-1"],
            confidence=0.9,
        ),
        "fused_chunks": [CHUNK],
        "citation_check": CHECK,
        "guardrail": GuardrailDecision(allowed=True),
    }
    state.update(overrides)
    return state


def test_pipeline_returns_agent_result_with_index_metadata():
    graph = FakeGraph(_state())
    pipeline = GraphPipeline(
        Settings(),
        store=FakeStore(points=133),
        graph=graph,
    )

    result = pipeline.ask("How should I brush?", request_id="req-1")

    assert result.response.kind == "answer"
    assert result.chunks == [CHUNK]
    assert result.citation_check == CHECK
    assert result.guardrail.allowed is True
    assert result.points == 133
    assert result.latency_ms >= 0
    assert graph.calls == [{"question": "How should I brush?"}]


def test_pipeline_maps_retrieval_failure_to_unavailable():
    graph = FakeGraph(
        _state(
            response=Refusal(reason=RefusalReason.INSUFFICIENT_CONTEXT),
            fused_chunks=[],
            citation_check=None,
            retrieval_error=True,
        )
    )
    pipeline = GraphPipeline(Settings(), store=FakeStore(), graph=graph)

    with pytest.raises(PipelineUnavailable):
        pipeline.ask("How should I brush?", request_id="req-1")


def test_pipeline_maps_generation_failure_to_unavailable():
    graph = FakeGraph(
        _state(
            response=Refusal(reason=RefusalReason.INSUFFICIENT_CONTEXT),
            citation_check=None,
            generation_error=True,
        )
    )
    pipeline = GraphPipeline(Settings(), store=FakeStore(), graph=graph)

    with pytest.raises(PipelineUnavailable):
        pipeline.ask("How should I brush?", request_id="req-1")


def test_pipeline_rejects_incomplete_graph_state():
    graph = FakeGraph({"guardrail": GuardrailDecision(allowed=True)})
    pipeline = GraphPipeline(Settings(), store=FakeStore(), graph=graph)

    with pytest.raises(PipelineUnavailable):
        pipeline.ask("How should I brush?", request_id="req-1")


def test_ready_reports_missing_collection():
    pipeline = GraphPipeline(Settings(), store=FakeStore(exists=False))

    assert pipeline.ready() is False
    assert pipeline.points() == 0


def test_ready_reports_point_count():
    pipeline = GraphPipeline(Settings(), store=FakeStore(points=133))

    assert pipeline.ready() is True
    assert pipeline.points() == 133


def test_ask_returns_503_when_collection_is_missing():
    pipeline = GraphPipeline(Settings(), store=FakeStore(exists=False))

    with pytest.raises(PipelineUnavailable):
        pipeline.ask("How should I brush?", request_id="req-1")
