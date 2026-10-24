Branch: fix/audit-p0-5-relevance-gate
Date: 2026-10-24
Scope: P0.5 off-corpus retrieval gate with a descoped-insurance rule

## What changed

- Added `src/retrieve/relevance.py` with:
  - `screen_relevance_question`: blank and SCOPE.md §5 insurance checks before any query.
  - `assess_relevance`: raw dense >= 0.35 OR sparse >= 10.0, never RRF.
  - `best_retrieval_scores`: top-1 dense and sparse scores for the hybrid gate.
- `make_retriever` now gates by default for dense, sparse, and hybrid.
  - Off-corpus and descoped questions return `[]`, so the existing graph path refuses with `insufficient_context` and never calls the LLM.
  - `relevance_gate=False` preserves raw retrieval baselines.
- Added `data/negative_set_v1.jsonl` with 8 off-topic and 4 insurance items.
- Added `src/eval/negative.py` for schema validation.
- Added `scripts/measure_relevance_gate.py`, the rerunnable threshold lever.
- Added `DECISIONS/relevance-gate.md` with the evidence and tradeoffs.
- Added 24 tests in `tests/retrieve/test_relevance.py` and 2 graph integration tests.

## Verification

- `uv run pytest tests/ingest/ tests/retrieve/ tests/agent/ tests/eval/ -q` -> 170 passed.
- `uv run python scripts/measure_relevance_gate.py` -> 0 false accepts, 0 false refusals across 72 gate-scored golden plus 12 negative items.
- Real local-index check:
  - "What is the capital of France?" -> 0 chunks, graph refusal.
  - "What's my dental insurance deductible?" -> 0 chunks, graph refusal.
  - "How do I brush my teeth?" -> 5 chunks.
- `git diff --check` clean.

## Decisions

- RRF scores are not thresholded because they are rank-based.
- Dense and sparse floors are ORed so exact terminology still passes.
- Insurance is a narrow deterministic coverage rule, not a guardrail diagnostic rule, so the refusal reason stays `insufficient_context`.
- Thresholds were measured on the 133-point demo index. Re-run the script after any corpus, model, or floor change.

## Follow-ups

- P0.2 live Ragas baseline still needs the owner's Bedrock credentials.
- P0.3 FastAPI service is next.
- Booking and scheduling remain model-handled; they are not covered by the insurance rule.
- The hybrid gate adds two top-1 searches per query. Batch them later if latency matters.
