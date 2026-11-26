# Cross-Encoder Rerank Model Choice

**Date:** 2026-11-25
**Status:** Proposed (awaiting owner approval, roadmap Phase A.1)
**File:** `src/retrieve/hybrid.py` (future `src/retrieve/rerank.py`)
**Task:** `docs/internal/TODO.md` Task 4.3

## Decision

Use `Xenova/ms-marco-MiniLM-L-6-v2` as the cross-encoder reranker, loaded through `fastembed`'s `TextCrossEncoder`.

The rerank stage stays off by default until Phase A.3 measures it.
No code is written until the owner approves this choice.

## Why

1. **No new Python dependency.**
   `fastembed>=0.8.0` is already pinned in `pyproject.toml`.
   Version 0.8.0 ships `fastembed.rerank.cross_encoder.TextCrossEncoder`.
   That class loads cross-encoder models from a fixed list, including both candidates below.
   The install that already runs embeddings also runs the reranker.
   `sentence-transformers` is not needed for this path.
2. **Small and fast.**
   The chosen model is 0.08 GB in fastembed's ONNX build.
   The v1 latency target is P95 ~5 s, and the demo runs on Streamlit Community Cloud.
   A small model keeps the cold-start cost low.
3. **The null result stays credible.**
   This is the standard MS MARCO reranker baseline.
   If it does not earn its latency, the finding is not an artifact of a weak model.
   If it helps, `jinaai/jina-reranker-v1-turbo-en` is a one-string swap in the same API.

## Candidates

| Candidate | Params | ONNX size | Context | License | Reported ranking | One-line trade-off |
|---|---|---|---|---|---|---|
| `Xenova/ms-marco-MiniLM-L-6-v2` | 22.7M | 0.08 GB | 512 tokens | Apache-2.0 | NDCG@10 74.30 on TREC DL 2019, MRR@10 39.01 on MS MARCO dev | Smallest and fastest, but trained on web passages, not clinical text |
| `jinaai/jina-reranker-v1-turbo-en` | 37.8M | 0.15 GB | 8,192 tokens | Apache-2.0 | NDCG@10 49.60 on 17 BEIR sets, Hit Rate 85.13 on LlamaIndex RAG | Slightly better reported ranking for about 2x disk, but the long context is wasted on short chunks |

The two ranking columns are not comparable.
They come from different benchmarks and different publishers.
Jina's own card compares its model to `ms-marco-MiniLM-L-6-v2` on the same BEIR and LlamaIndex metrics and reports the turbo model slightly ahead.
Treat that as vendor-published evidence, not an independent result.

### Rejected for now

- `BAAI/bge-reranker-base` (1.04 GB, MIT).
  A quality step-up, but 13x the disk of the chosen model.
  Keep it as a fallback only if both small models fail Phase A.3.
- `jinaai/jina-reranker-v2-base-multilingual` (1.11 GB, cc-by-nc-4.0).
  The non-commercial license conflicts with a public portfolio and demo.
  Reject on license first, size second.

## Loader path

TODO Task 4.3 names `sentence-transformers`.
That is one way to load a cross-encoder, not the only way.

| Path | Install cost | Model choice | Verdict |
|---|---|---|---|
| `fastembed` `TextCrossEncoder` | Zero, already pinned | Fixed list of 6 rerankers | Chosen |
| `sentence-transformers` `CrossEncoder` | Adds PyTorch and transformers, plus a larger image | Any HF cross-encoder, plus `rank()` | Rejected for v1 |

The fastembed path wins on install size and cold start.
The cost is a fixed model list.
If a future step needs a model outside that list, revisit this decision.

## Integration notes for Phase A.2

These are facts for the implementer, not code.

- `hybrid_search` currently passes `limit=top_n` (default 5) to the fusion query at `src/retrieve/hybrid.py:51-63`.
  It never materializes the top ~20.
  The rerank stage must first fetch about 20 fused chunks, then rerank down to `top_n`.
- `TextCrossEncoder.rerank(query, documents)` yields one score per document in input order.
  The stage must zip scores to chunks and sort descending.
- Chunks are split at 1000 characters with 200 overlap (`AGENTS.md`).
  That is roughly 250 tokens, so both candidates see the full chunk without truncation.
- The return type must stay `list[RetrievedChunk]`, best first, so `make_retriever` and the graph do not change.

## Consequences

- A new model file (about 80 MB) downloads on first rerank use and is cached.
- The rerank stage adds one cross-encoder pass over about 20 pairs per query.
  Phase A.3 records the p50 and p95 delta.
- If the stage does not improve ordering, it stays off and this decision records why.
  That outcome is an acceptable result, not a failure.

## Sources

- fastembed supported models, including the rerank cross-encoder table: https://qdrant.github.io/fastembed/examples/Supported_Models/
- fastembed 0.8.0 `TextCrossEncoder` (verified in the project venv at `.venv/lib/python3.12/site-packages/fastembed/rerank/cross_encoder/text_cross_encoder.py`).
  `TextCrossEncoder.list_supported_models()` returns both candidates with the sizes above.
- `Xenova/ms-marco-MiniLM-L-6-v2` model card: https://huggingface.co/Xenova/ms-marco-MiniLM-L-6-v2
- `cross-encoder/ms-marco-MiniLM-L6-v2` model card, training data and benchmarks: https://huggingface.co/cross-encoder/ms-marco-MiniLM-L-6-v2
- `jinaai/jina-reranker-v1-turbo-en` model card, parameters and benchmark table: https://huggingface.co/jinaai/jina-reranker-v1-turbo-en
- `sentence-transformers` on PyPI, PyTorch requirement: https://pypi.org/project/sentence-transformers/
- Repo: `pyproject.toml` (fastembed pin), `src/retrieve/hybrid.py:51-63` (fusion limit), `AGENTS.md` (chunk size), `docs/internal/TODO.md` Task 4.3.
