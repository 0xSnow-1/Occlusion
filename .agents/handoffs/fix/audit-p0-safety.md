Branch: fix/audit-p0-safety
Date: 2026-10-24
Scope: P0.1 archive provenance, P0.4 blank-question refusal, P0.2 offline eval gate

## What changed

- PDF ingestion now uses an explicit provenance allowlist (`APPROVED_PDF_PATHS`) instead of a free-for-all `**/*.pdf` glob.
- `data/raw/_archive/` is excluded from the Docker build context.
- The graph refuses blank or whitespace-only questions before retrieval, so an empty query can no longer pull nearest-neighbour chunks.
- `src/eval/ragas/run_ragas.py` now exits nonzero when a ship threshold fails or a metric drops beyond tolerance below an optional baseline.
- Added `tests/eval/`: deterministic diagnostic-refusal gate, frozen-snapshot integrity check, and Ragas gate helper tests.
- Rebuilt the vendored Qdrant index from the approved corpus. It now has 133 points and zero archive doc IDs.
- Added `beautifulsoup4` because `WebBaseLoader` requires it and a fresh `uv sync` previously could not run the documented ingest command.

## Verification

- `uv run pytest tests/ingest/ tests/retrieve/ tests/agent/ tests/eval/ -q` -> 144 passed.
- Qdrant probe: 133 points, zero `Uniform-Glossary-01-2020`, `AHA_ADA_Antibiotic_Prophylaxis_Guidelines`, `IADT_Traumatic_Dental_Injuries_Guidelines`, or `AAPD_Pediatric_Local_Anesthesia`.
- `git diff --check` clean.
- `uv sync --frozen --no-dev` succeeds.

## Follow-ups

- P0.5 relevance gate is still required for deterministic refusal of off-corpus questions such as "capital of France".
- Live Ragas baseline run still needs owner Bedrock credentials.
- The demo index (133 points) and eval snapshot (120 chunks) still differ because live HTML content changed; the archive sources are now absent from both.
- `beautifulsoup4` is a new explicit dependency and needs owner approval before merge.
