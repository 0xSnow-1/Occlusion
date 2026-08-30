"""TODO Phase 5.3 — compiled-graph behavior with a fake LLM (no API calls).

The fake LLM stands in for `llm.with_structured_output(Answer).invoke(...)` so
the whole pipeline runs offline — this is the "mock LLM hook" from TODO 5.2.
"""

from src.agent.graph import build_graph
from src.agent.schemas import Answer, Refusal, RefusalReason, RetrievedChunk

STUB_CHUNK = RetrievedChunk(
    doc_id="ada-guide-001",
    text="Silver diamine fluoride (SDF) can arrest early caries lesions.",
)


def stub_retriever(query: str, *, top_n: int):
    return [STUB_CHUNK]


class FakeLLM:
    """Minimal stand-in: `.with_structured_output(Answer)` returns self,
    `.invoke(messages)` returns a canned output."""

    def __init__(self, output):
        self._output = output

    def with_structured_output(self, schema):
        assert schema is Answer
        return self

    def invoke(self, messages):
        return self._output


def test_happy_path_returns_cited_answer():
    graph = build_graph(
        retriever=stub_retriever,
        llm=FakeLLM(
            Answer(
                answer="SDF arrests early caries [SRC:ada-guide-001].",
                citations=["ada-guide-001"],
                confidence=0.9,
            )
        ),
    )
    out = graph.invoke({"question": "Does silver diamine fluoride work?"})
    assert isinstance(out["response"], Answer)
    assert out["citation_check"].verified
    assert out["fused_chunks"] == [STUB_CHUNK]


def test_low_confidence_fails_closed():
    graph = build_graph(
        retriever=stub_retriever,
        llm=FakeLLM(
            Answer(
                answer="Not sure. [SRC:ada-guide-001]",
                citations=["ada-guide-001"],
                confidence=0.2,
            )
        ),
        confidence_threshold=0.5,
    )
    out = graph.invoke({"question": "Am I fine?"})
    assert isinstance(out["response"], Refusal)
    assert out["response"].reason == RefusalReason.INSUFFICIENT_CONTEXT


def test_fabricated_citation_fails_closed():
    graph = build_graph(
        retriever=stub_retriever,
        llm=FakeLLM(
            Answer(
                answer="Claim [SRC:fake-999].",
                citations=["fake-999"],
                confidence=0.95,
            )
        ),
    )
    out = graph.invoke({"question": "Tell me about it."})
    assert isinstance(out["response"], Refusal)


def test_empty_retrieval_fails_closed():
    graph = build_graph(
        retriever=lambda query, *, top_n: [],
        llm=FakeLLM(
            Answer(
                answer="x [SRC:ada-guide-001]",
                citations=["ada-guide-001"],
                confidence=0.9,
            )
        ),
    )
    out = graph.invoke({"question": "Anything?"})
    assert isinstance(out["response"], Refusal)

    # The gate short-circuits before generation on empty retrieval, so the
    # LLM was never even called in spirit: fused_chunks stays empty.
    assert out["fused_chunks"] == []