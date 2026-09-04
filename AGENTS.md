# AGENTS.md — Occlusion (Chairside dental RAG MVP)

## Commands
- Setup: `uv sync && cp sample.env .env` (fill keys; `.env` is gitignored — never commit it).
- Test (fast, offline): `uv run pytest tests/ingest/test_vector_store.py -q`
- Single test: `uv run pytest tests/<path>::<Class>::<test_name> -q`
- Ingest pipeline: `uv run python scripts/run_ingest.py` (PDFs only, `:memory:` Qdrant)
- `pyproject.toml` sets `pythonpath = ["."]` — import as `src.*`. Requires Python 3.12+, `uv`.

## Stack / dependencies (source: `ai-stack/STACK.md`, inlined — that dir is gitignored)
- Preferred: Python 3.12+ / uv; LangGraph; Qdrant + fastembed / sentence-transformers; Ragas + LangSmith; Pydantic v2 / FastAPI; PyMuPDF. `pyproject.toml` as committed is approved as-is.
- Never reach for `copilotkit`, `ag-ui-langgraph`, `ddgs` / `duckduckgo-search` (user does not know them) without explicit approval.
- Prefer the simplest solution using an already-listed lib over adding a new dep. New dep needs explicit user approval first: research 1–2 candidates, explain why in layman's terms, go through the learning process, then record the winner in STACK.md.

## Layout (what's real vs stub)
- `src/ingest/` — implemented: `document_parser.py` (PyMuPDFLoader + WebBaseLoader; `doc_id` = PDF stem / URL path segment), `chunking_and_embedding.py` (RecursiveCharacterTextSplitter 1000/200 chars; lazy `all-MiniLM-L6-v2`, 384-dim, embedding in `metadata["embedding"]`), `vector_store.py` (Qdrant dense cosine + sparse `Splade_PP_en_v1`, payload indexes on `doc_id`/`source_url`/`title`, int point ids `0..n`).
- `src/agent/{schemas,graph,fusion,verify,state,prompts,agents}.py` — **empty stubs**. The tests under `tests/agent/` are the spec: implement to match them (see below). `src/retrieve/`, `src/eval/` — empty, planned per TODO phases.
- `scripts/run_ingest.py` — manual-run pipeline only (parse → chunk → `:memory:` collection → upsert with fastembed-on-the-fly).

## Contracts the tests pin (don't reinvent)
- `rrf_fuse(dense, sparse, k=60, top_n=...)`: rank-based RRF; doc in both lists outranks rank-1-only (`tests/agent/test_fusion.py`).
- Citations: inline `[SRC:doc_id]` tokens; `verify_citations` checks IDs ∈ retrieved set; zero citations or any fabricated ID → `verified=False`, fail closed (`tests/agent/test_verify.py`).
- `build_graph(retriever=..., llm=..., confidence_threshold=...)`: injectable retriever + `llm.with_structured_output(Answer)` fake; empty retrieval / low confidence / fabricated citation → `Refusal` (`tests/agent/test_graph.py`).
- Schemas: `Answer` (`answer` non-empty, `citations: list[str]`, `confidence` 0–1) vs `Refusal` (`reason` enum, default message mentions consulting a dentist); discriminated union on `kind` (`tests/agent/test_schemas.py`).

## Gotchas
- `tests/agent/*` currently FAIL with `ImportError` (stubs unimplemented) — expected. `tests/ingest/test_vector_store.py` passes (19 tests); chunking/embedding tests download the MiniLM model on first run (~27s).
- Qdrant `:memory:` ignores payload indexes (warning is benign); Cloud free tier suspends after ~1wk idle. Sparse vectors must be declared at collection creation — never add later (see `DECISIONS/hybrid-qdrant-vector-store.md`). Don't hardcode dim 384; use `client.get_embedding_size()`.
- Logging: `logging.getLogger(__name__)` per module, `basicConfig` only at entry points; no `print()` in library code (`LOGGING.md`).
- Ignored artifacts: `data/parsed/`, `data/embeddings_cache/`, `data/qdrant_storage/`, `eval/results/*.json`, `data/raw/_archive/`. Keep versioned snapshots (`chunks_v1.jsonl`, `golden_set_v1.jsonl`) when created.
- No CI, lint, typecheck, or `opencode.json` in repo. No FastAPI/UI yet (TODO Phase 9).

## Scope guards (from SCOPE.md / PROVENANCE.md)
- Refusal correctness on trap questions is the hard ship gate (100%, zero slack) — never answer diagnostic/prescriptive or out-of-corpus questions confidently.
- Corpus is patient-education only (HRSA/NIDCR/CDC public domain + NHS OGL v3.0). NHS-derived output needs OGL attribution. Do NOT re-add: MedlinePlus/ency, ADA/Colgate/WebMD, NADP glossary, per-Trust leaflets, archived clinical guidelines, CMS glossary — all explicitly rejected.
- Follow `TODO.md` phase order (0–2 gate everything; verify gate per task) and check `SCOPE.md` before adding features.
