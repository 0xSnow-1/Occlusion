# Pinned sources under test

Vendored verbatim from repo commit `01d6902` (renamed so the Docker build
context stays self-contained; `src/agent/` unchanged since `d87520c`):

- `src_agent/` ← `src/agent/` (`__init__`, `schemas`, `state`, `guardrail`,
  `verify`, `fusion`, `graph`, `prompts/` package — note: the empty
  `prompts.py` stub is NOT vendored; the `prompts/` package wins resolution
  in the repo too)
- `src_retrieve/` ← `src/retrieve/` (`__init__`, `base`, `dense`, `sparse`,
  `hybrid`; added for this task — the live retriever path)
- `src_ingest/vector_store.py` ← `src/ingest/vector_store.py` (added for
  this task — `:memory:` ingest of the frozen snapshot at setup)

The image copies these trees to `/app/src/agent`, `/app/src/retrieve`,
`/app/src/ingest`. When repo sources change, re-vendor, record the new
commit here, and regenerate `tests/fixtures/hashes.json`.
