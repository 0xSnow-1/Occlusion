"""TODO Phase 4.2 — RRF fusion behavior (rank-based, k≈60)."""

from src.agent.fusion import rrf_fuse
from src.agent.schemas import RetrievedChunk


def _chunk(doc_id: str) -> RetrievedChunk:
    return RetrievedChunk(doc_id=doc_id, text=doc_id)


def test_single_list_passthrough_preserves_rank_order():
    dense = [_chunk("a"), _chunk("b"), _chunk("c")]
    out = rrf_fuse(dense, [], k=60, top_n=5)
    assert [c.doc_id for c in out] == ["a", "b", "c"]


def test_doc_in_both_lists_gets_rank_boost():
    dense = [_chunk("a"), _chunk("b"), _chunk("c")]
    sparse = [_chunk("c"), _chunk("d")]
    out = rrf_fuse(dense, sparse, k=60, top_n=5)
    ids = [c.doc_id for c in out]
    # "c" appears at rank 3 (dense) AND rank 1 (sparse), so its fused score
    # beats rank-1-only "a" — that is the whole point of RRF.
    assert ids[0] == "c"
    assert set(ids) == {"a", "b", "c", "d"}


def test_top_n_cap():
    dense = [_chunk(f"doc-{i}") for i in range(10)]
    out = rrf_fuse(dense, [], k=60, top_n=3)
    assert len(out) == 3


def test_empty_lists_yield_empty():
    assert rrf_fuse([], [], k=60, top_n=5) == []