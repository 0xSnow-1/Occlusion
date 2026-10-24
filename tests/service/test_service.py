"""Offline tests for the FastAPI service boundary."""

from __future__ import annotations

import time
from collections.abc import Callable

from fastapi.testclient import TestClient

from src.agent.schemas import (
    Answer,
    CitationCheck,
    GuardrailDecision,
    Refusal,
    RefusalReason,
    RetrievedChunk,
)
from src.service.app import create_app
from src.service.pipeline import AskResult, PipelineUnavailable
from src.service.settings import Settings

CHUNK = RetrievedChunk(
    doc_id="doc-1",
    text="Brush twice a day with fluoride toothpaste.",
    source_url="https://example.com/doc-1",
)
CHECK = CitationCheck(
    verified=True,
    cited_ids=["doc-1"],
    retrieved_ids=["doc-1"],
    matches=1,
    total=1,
    coverage=1.0,
)


def _result(kind: str = "answer") -> AskResult:
    if kind == "answer":
        response = Answer(
            answer="Brush twice a day [SRC:doc-1].",
            citations=["doc-1"],
            confidence=0.9,
        )
    else:
        response = Refusal(reason=RefusalReason.INSUFFICIENT_CONTEXT)
    return AskResult(
        response=response,
        chunks=[CHUNK],
        citation_check=CHECK if kind == "answer" else None,
        guardrail=GuardrailDecision(allowed=True),
        latency_ms=12.5,
        points=133,
    )


class FakePipeline:
    def __init__(
        self,
        *,
        result: AskResult | None = None,
        result_factory: Callable[[str], AskResult] | None = None,
        ready: bool = True,
        points: int = 133,
        error: Exception | None = None,
        delay_s: float = 0.0,
    ) -> None:
        self.result = result or _result()
        self.result_factory = result_factory
        self.ready_value = ready
        self.points_value = points
        self.error = error
        self.delay_s = delay_s
        self.calls: list[object] = []

    def ready(self) -> bool:
        self.calls.append("ready")
        return self.ready_value

    def points(self) -> int:
        self.calls.append("points")
        return self.points_value

    def ask(self, question: str, *, request_id: str) -> AskResult:
        self.calls.append(("ask", question, request_id))
        if self.delay_s:
            time.sleep(self.delay_s)
        if self.error is not None:
            raise self.error
        if self.result_factory is not None:
            return self.result_factory(question)
        return self.result


def _client(pipeline: FakePipeline, **settings) -> TestClient:
    return TestClient(
        create_app(pipeline=pipeline, settings=Settings(**settings))
    )


def test_health_is_live_without_touching_the_pipeline():
    pipeline = FakePipeline()
    response = _client(pipeline).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert pipeline.calls == []


def test_ready_reports_index_metadata():
    pipeline = FakePipeline(points=133)
    response = _client(pipeline).get("/ready")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ready",
        "points": 133,
        "collection": "occlusion",
        "confidence_threshold": 0.7,
        "model_id": "global.anthropic.claude-haiku-4-5-20251001-v1:0",
    }
    assert pipeline.calls == ["ready", "points"]


def test_ready_returns_503_when_index_is_missing():
    pipeline = FakePipeline(ready=False)
    response = _client(pipeline).get("/ready")

    assert response.status_code == 503
    assert response.json()["detail"] == "retrieval index is not ready"
    assert pipeline.calls == ["ready"]


def test_ask_returns_answer_with_request_id_and_evidence():
    pipeline = FakePipeline()
    response = _client(pipeline).post(
        "/ask", json={"question": "How should I brush?"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == response.headers["X-Request-ID"]
    assert body["response"]["kind"] == "answer"
    assert body["chunks"][0]["doc_id"] == "doc-1"
    assert body["citation_check"]["verified"] is True
    assert body["guardrail"]["allowed"] is True
    assert body["latency_ms"] >= 0
    assert body["points"] == 133
    assert pipeline.calls[0][1] == "How should I brush?"


def test_ask_returns_refusal_as_a_normal_response():
    pipeline = FakePipeline(result=_result("refusal"))
    response = _client(pipeline).post(
        "/ask", json={"question": "What is the capital of France?"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["response"]["kind"] == "refusal"
    assert body["response"]["reason"] == "insufficient_context"


def test_ask_rejects_empty_question():
    pipeline = FakePipeline()
    response = _client(pipeline).post("/ask", json={"question": ""})

    assert response.status_code == 422
    assert pipeline.calls == []
    assert response.headers["X-Request-ID"]


def test_ask_rejects_whitespace_only_question():
    pipeline = FakePipeline()
    response = _client(pipeline).post("/ask", json={"question": "   "})

    assert response.status_code == 422
    assert pipeline.calls == []


def test_ask_rejects_over_length_question():
    pipeline = FakePipeline()
    response = _client(pipeline).post(
        "/ask", json={"question": "x" * 1001}
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "question is too long"
    assert pipeline.calls == []


def test_ask_accepts_custom_request_id():
    pipeline = FakePipeline()
    response = _client(pipeline).post(
        "/ask",
        json={"question": "How should I brush?"},
        headers={"X-Request-ID": "req-123"},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "req-123"
    assert response.json()["request_id"] == "req-123"
    assert pipeline.calls[0][2] == "req-123"


def test_ask_generates_request_id_when_header_is_absent():
    pipeline = FakePipeline()
    response = _client(pipeline).post(
        "/ask", json={"question": "How should I brush?"}
    )

    request_id = response.json()["request_id"]
    assert len(request_id) == 32
    int(request_id, 16)
    assert response.headers["X-Request-ID"] == request_id


def test_ask_returns_503_when_pipeline_is_unavailable():
    pipeline = FakePipeline(error=PipelineUnavailable("index down"))
    response = _client(pipeline).post(
        "/ask", json={"question": "How should I brush?"}
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "assistant unavailable"


def test_ask_returns_503_without_leaking_unexpected_errors():
    pipeline = FakePipeline(error=RuntimeError("secret internals"))
    response = _client(pipeline).post(
        "/ask", json={"question": "How should I brush?"}
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "assistant unavailable"
    assert "secret internals" not in response.text


def test_ask_times_out():
    pipeline = FakePipeline(delay_s=0.2)
    response = _client(pipeline, request_timeout_s=0.05).post(
        "/ask", json={"question": "How should I brush?"}
    )

    assert response.status_code == 504
    assert response.json()["detail"] == "request timed out"


def test_metrics_report_requests_outcomes_and_readiness():
    pipeline = FakePipeline(
        result_factory=lambda question: (
            _result("refusal") if "France" in question else _result()
        )
    )
    client = _client(pipeline)
    client.post("/ask", json={"question": "How should I brush?"})
    client.post(
        "/ask",
        json={"question": "What is the capital of France?"},
    )

    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert (
        'occlusion_http_requests_total{endpoint="/ask",status="200"} 2'
        in response.text
    )
    assert "occlusion_answers_total 1" in response.text
    assert (
        'occlusion_refusals_total{reason="insufficient_context"} 1'
        in response.text
    )
    assert "occlusion_pipeline_ready 1" in response.text
    assert "occlusion_index_points 133" in response.text
    assert (
        'occlusion_http_request_duration_seconds_bucket{endpoint="/ask",le="+Inf"} 2'
        in response.text
    )
