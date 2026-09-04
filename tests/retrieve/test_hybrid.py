"""TODO Phases 3.3/4.2 — retrieval wiring with a mocked Qdrant client.

No API calls, no model downloads: fake clients return canned points so
these tests prove payload mapping, fusion wiring, the fallback path, and
the `(query, *, top_n)` signature the future graph node will use.
"""

from __future__ import annotations

import sys
import types
from types import SimpleNamespace

import pytest

from src.agent.schemas import RetrievedChunk
from src.retrieve import dense_search, hybrid_search, make_retriever
from src.retrieve.base import points_to_chunks


def _ensure_qdrant_models():
    """Use the real qdrant_client when installed, else a structural stub.

    The stub only mimics constructor signatures (`Document`, `Prefetch`,
    `FusionQuery`, `Fusion`) plus the names `vector_store.py` imports at
    module top — enough for offline wiring tests.
    """
    try:
        from qdrant_client import models  # noqa: F401
        return
    except ImportError:
        pass

    models_mod = types.ModuleType("qdrant_client.models")

    class _Query:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    class Document(_Query):
        pass

    class Prefetch(_Query):
        pass

    class FusionQuery(_Query):
        pass

    class Fusion:
        RRF = "RRF"

    for name in (
        "Distance",
        "PointStruct",
        "SparseIndexParams",
        "SparseVectorParams",
        "VectorParams",
    ):
        setattr(models_mod, name, type(name, (), {}))
    models_mod.Document = Document
    models_mod.Prefetch = Prefetch
    models_mod.FusionQuery = FusionQuery
    models_mod.Fusion = Fusion

    client_mod = types.ModuleType("qdrant_client")
    client_mod.QdrantClient = type("QdrantClient", (), {})
    client_mod.models = models_mod
    sys.modules["qdrant_client"] = client_mod
    sys.modules["qdrant_client.models"] = models_mod


_ensure_qdrant_models()


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
    """Returns canned points for any `query_points` call, recording kwargs."""

    def __init__(self, points):
        self._points = points
        self.calls = []

    def query_points(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(points=self._points)


class _NoFusionClient:
    """Simulates a server without fusion support: prefetch calls fail."""

    def query_points(self, **kwargs):
        if "prefetch" in kwargs:
            raise TypeError("fusion not supported")
        if kwargs.get("using") == "sparse":
            return SimpleNamespace(
                points=[
                    _point(11, "c", "c-text", 0.5),
                    _point(12, "d", "d-text", 0.4),
                ]
            )
        return SimpleNamespace(
            points=[
                _point(1, "a", "a-text", 0.9),
                _point(2, "b", "b-text", 0.8),
                _point(3, "c", "c-text", 0.7),
            ]
        )


class TestPointsToChunks:
    def test_maps_payload_to_chunk(self):
        out = points_to_chunks([_point(0, "doc-1", "hello", 0.9)])
        assert out == [
            RetrievedChunk(
                doc_id="doc-1",
                text="hello",
                score=0.9,
                source_url="https://example.com",
            )
        ]

    def test_skips_points_with_empty_text(self):
        pts = [_point(0, "doc-1", "", 0.9), _point(1, "doc-2", "kept", 0.5)]
        out = points_to_chunks(pts)
        assert [c.doc_id for c in out] == ["doc-2"]

    def test_empty_input_yields_empty(self):
        assert points_to_chunks([]) == []


class TestDenseSearch:
    def test_uses_dense_vector_and_limit(self):
        client = _FakeClient([_point(0, "doc-1", "hello", 0.9)])
        out = dense_search(client, "col", "what is this?", top_k=3)
        assert [c.doc_id for c in out] == ["doc-1"]
        call = client.calls[0]
        assert call["using"] == "dense"
        assert call["limit"] == 3
        assert call["with_payload"] is True


class TestHybridSearch:
    def test_prefetches_both_paths_and_limits_top_n(self):
        client = _FakeClient(
            [
                _point(0, "doc-1", "one", 0.9),
                _point(1, "doc-2", "two", 0.8),
            ]
        )
        out = hybrid_search(client, "col", "q", top_k=20, top_n=2)
        assert [c.doc_id for c in out] == ["doc-1", "doc-2"]
        call = client.calls[0]
        assert len(call["prefetch"]) == 2
        # Real Prefetch exposes `.using`; the offline stub keeps `.kwargs`.
        usings = {
            getattr(p, "using", None) or p.kwargs.get("using")
            for p in call["prefetch"]
        }
        assert usings == {"dense", "sparse"}
        assert call["limit"] == 2

    def test_falls_back_to_client_rrf_without_fusion(self):
        out = hybrid_search(_NoFusionClient(), "col", "q", top_k=20, top_n=5)
        ids = [c.doc_id for c in out]
        # "c" is rank 3 dense + rank 1 sparse -> fused first (see test_fusion.py).
        assert ids[0] == "c"
        assert set(ids) == {"a", "b", "c", "d"}


class TestMakeRetriever:
    def test_signature_matches_future_graph_node(self):
        client = _FakeClient([_point(0, "doc-1", "hello", 0.9)])
        retriever = make_retriever(client, "col", variant="dense")
        out = retriever("some question", top_n=2)
        assert isinstance(out[0], RetrievedChunk)
        assert client.calls[0]["limit"] == 2

    def test_unknown_variant_rejected(self):
        with pytest.raises(ValueError):
            make_retriever(_FakeClient([]), "col", variant="nope")
