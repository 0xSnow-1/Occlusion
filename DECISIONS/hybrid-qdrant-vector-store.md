# Hybrid Qdrant Vector Store with Dense + Sparse Embeddings

**Date:** 2026-09-03
**Status:** Accepted
**File:** `src/ingest/vector_store.py`

## Decision

Use Qdrant as the vector database with both dense (cosine, 384-dim) and sparse (SPLADE/BM25-style) vectors stored per point from day one, instead of starting dense-only and migrating later.

## Why

- **Hybrid retrieval beats dense-only.** Dense embeddings miss exact terminology (drug names, procedure codes, specific condition names) that dental documents contain. BM25 catches those.
- **Sparse vectors must be declared at collection creation.** Qdrant does not allow adding sparse vector fields after a collection is created without rebuilding it. Starting hybrid-ready avoids a painful migration in Phase 4.
- **RRF fusion requires both vector types.** The architecture uses Reciprocal Rank Fusion which fuses results by rank, not score. This requires both dense and sparse search results to fuse.
- **Dimension should never be hardcoded.** Using `client.get_embedding_size()` instead of hardcoding `384` prevents silent breakage when swapping embedding models.

## Stack

- **Dense model:** `sentence-transformers/all-MiniLM-L6-v2` (384-dim, cosine)
- **Sparse model:** `prithivida/Splade_PP_en_v1` (SPLADE++, IDF-weighted)
- **Libraries:** `qdrant-client[fastembed]` handles both embedding and upsert in one step via `models.Document`

## Tradeoffs

- **First-run latency:** fastembed downloads models on first use (~27s), cached on subsequent runs (~10s).
- **Payload indexes ignored locally:** Qdrant's in-memory mode (`:memory:`) ignores payload indexes. They only work on Qdrant Cloud. Code is ready for both.
- **No search methods yet:** VectorStore only handles collection lifecycle and upsert. Search/retrieval belongs in `src/retrieve/` (Phase 4).
