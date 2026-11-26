"""Cross-encoder rerank stage — offline wiring tests.

The lazy loader is patched, so no model downloads or network calls happen.
"""

from __future__ import annotations

from types import SimpleNamespace

import src.retrieve.hybrid as hybrid_module
import src.retrieve.rerank as rerank_module

from src.agent.schemas import RetrievedChunk
from src.retrieve import (
    DEFAULT_RERANK_MODEL,
    hybrid_search,
    make_retriever,
    rerank_chunks,
)


def _point(pid, doc_id, text, score):
    return SimpleNamespace(
        id=pid,
        score=score,
        payload={
            "doc_id": doc_id,
            "text": text,
            "source_url": "https://example.com",
        },
    )


class _FakeClient:
    def __init__(self, points):
        self._points = points
        self.calls = []

    def query_points(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(points=self._points)


class _FakeEncoder:
    def __init__(self, scores):
        self._scores = scores
        self.calls = []

    def rerank(self, query, documents):
        self.calls.append((query, list(documents)))
        return iter(self._scores)


def _chunk(doc_id, text, score, title=None):
    return RetrievedChunk(
        doc_id=doc_id,
        text=text,
        score=score,
        source_url=f"https://example.com/{doc_id}",
        title=title,
    )


class TestRerankChunks:
    def test_empty_input_returns_without_loading_model(self, monkeypatch):
        def _explode(_name):
            raise AssertionError("model must not load for empty input")

        monkeypatch.setattr(rerank_module, "_load_reranker", _explode)
        assert rerank_chunks("q", []) == []

    def test_sorts_truncates_sets_score_and_preserves_fields(self, monkeypatch):
        chunks = [
            _chunk("a", "alpha", 0.9, title="A"),
            _chunk("b", "beta", 0.8, title="B"),
            _chunk("c", "gamma", 0.7, title="C"),
        ]
        encoder = _FakeEncoder([0.1, 0.95, 0.5])
        monkeypatch.setattr(rerank_module, "_load_reranker", lambda _name: encoder)

        out = rerank_chunks("query", chunks, top_n=2)

        assert [c.doc_id for c in out] == ["b", "c"]
        assert [c.score for c in out] == [0.95, 0.5]
        best = out[0]
        assert best.text == "beta"
        assert best.source_url == "https://example.com/b"
        assert best.title == "B"
        assert encoder.calls == [("query", ["alpha", "beta", "gamma"])]

    def test_uses_default_model_unless_overridden(self, monkeypatch):
        seen = []

        def _loader(name):
            seen.append(name)
            return _FakeEncoder([0.5])

        monkeypatch.setattr(rerank_module, "_load_reranker", _loader)

        rerank_chunks("q", [_chunk("a", "alpha", 0.1)])
        rerank_chunks("q", [_chunk("a", "alpha", 0.1)], model_name="custom/model")

        assert seen == [DEFAULT_RERANK_MODEL, "custom/model"]


class TestHybridRerankToggle:
    def test_default_off_uses_top_n_and_never_reranks(self, monkeypatch):
        def _explode(*_args, **_kwargs):
            raise AssertionError("rerank path must not run when rerank=False")

        monkeypatch.setattr(hybrid_module, "rerank_chunks", _explode)
        client = _FakeClient(
            [
                _point(0, "doc-1", "one", 0.9),
                _point(1, "doc-2", "two", 0.8),
            ]
        )

        out = hybrid_search(client, "col", "q", top_k=20, top_n=2)

        assert client.calls[0]["limit"] == 2
        assert [c.doc_id for c in out] == ["doc-1", "doc-2"]

    def test_rerank_fetches_top_k_then_returns_best_top_n(self, monkeypatch):
        encoder = _FakeEncoder([0.2, 0.9, 0.1, 0.7])
        loaded = []

        def _loader(name):
            loaded.append(name)
            return encoder

        monkeypatch.setattr(rerank_module, "_load_reranker", _loader)
        client = _FakeClient(
            [
                _point(0, "doc-a", "a-text", 0.9),
                _point(1, "doc-b", "b-text", 0.8),
                _point(2, "doc-c", "c-text", 0.7),
                _point(3, "doc-d", "d-text", 0.6),
            ]
        )

        out = hybrid_search(
            client, "col", "what?", top_k=20, top_n=2, rerank=True
        )

        assert client.calls[0]["limit"] == 20
        assert [c.doc_id for c in out] == ["doc-b", "doc-d"]
        assert [c.score for c in out] == [0.9, 0.7]
        assert loaded == [DEFAULT_RERANK_MODEL]
        assert encoder.calls == [("what?", ["a-text", "b-text", "c-text", "d-text"])]

    def test_rerank_candidates_overrides_candidate_limit(self, monkeypatch):
        monkeypatch.setattr(
            rerank_module, "_load_reranker", lambda _name: _FakeEncoder([0.3, 0.1])
        )
        client = _FakeClient(
            [
                _point(0, "doc-1", "one", 0.9),
                _point(1, "doc-2", "two", 0.8),
            ]
        )

        hybrid_search(
            client,
            "col",
            "q",
            top_k=20,
            top_n=1,
            rerank=True,
            rerank_candidates=7,
        )

        assert client.calls[0]["limit"] == 7


class TestMakeRetrieverRerank:
    def test_forwards_rerank_kwargs_to_hybrid_search(self, monkeypatch):
        captured = {}

        def _fake_hybrid(client, collection_name, query, **kwargs):
            captured["client"] = client
            captured["collection_name"] = collection_name
            captured["query"] = query
            captured["kwargs"] = kwargs
            return []

        monkeypatch.setattr("src.retrieve.hybrid_search", _fake_hybrid)
        client = object()

        retriever = make_retriever(
            client,
            "col",
            relevance_gate=False,
            rerank=True,
            rerank_candidates=7,
        )
        out = retriever("some question", top_n=3)

        assert out == []
        assert captured["client"] is client
        assert captured["collection_name"] == "col"
        assert captured["query"] == "some question"
        assert captured["kwargs"] == {
            "top_n": 3,
            "rerank": True,
            "rerank_candidates": 7,
        }
