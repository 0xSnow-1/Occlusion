# AGENTS.md — Occlusion (Chairside dental RAG MVP)

## Commands
- Setup: `uv sync && cp sample.env .env` (fill keys; `.env` is gitignored — never commit it).
- Test (fast, offline): `uv run pytest tests/ingest/ tests/retrieve/ tests/agent/ -q`
- Single test: `uv run pytest tests/<path>::<Class>::<test_name> -q`
- Ingest pipeline: `uv run python -m src.ingest.ingestion_pipeline` (default corpus from `data/raw` plus the 11 `DEFAULT_HTML_URLS`, into on-disk Qdrant at `./data/qdrant_storage`)
- `pyproject.toml` sets `pythonpath = ["."]` — import as `src.*`. Requires Python 3.12+, `uv`.
- CI (`.github/workflows/ci.yml`) mirrors the offline suite on every push and PR. If you add/remove a test path or change the test command, update the `pytest` line to match. Never change triggers, runners, or action versions without human approval.

## Stack / dependencies (source: `ai-stack/STACK.md`, inlined — that dir is gitignored)
- Preferred: Python 3.12+ / uv; LangGraph; Qdrant + fastembed / sentence-transformers; Ragas + LangSmith; Pydantic v2 / FastAPI; PyMuPDF. `pyproject.toml` as committed is approved as-is.
- Never reach for `copilotkit`, `ag-ui-langgraph`, `ddgs` / `duckduckgo-search` (user does not know them) without explicit approval.
- Prefer the simplest solution using an already-listed lib over adding a new dep. New dep needs explicit user approval first: research 1-2 candidates, explain why in layman's terms, go through the learning process, then record the winner in STACK.md.
- This is a portfolio/resume project. The user is the decision-maker — the LLM implements, the user decides. When asked to build something, present options and let the user choose. Do not make architectural or design decisions on the user's behalf.

## Layout (what's real vs stub)
- `src/ingest/` — implemented: `document_parser.py` (PyMuPDFLoader + WebBaseLoader; `doc_id` = PDF stem / URL path segment), `chunking_and_embedding.py` (RecursiveCharacterTextSplitter 1000/200 chars; embedding at upsert time via fastembed `models.Document`), `vector_store.py` (Qdrant dense cosine + sparse `Splade_PP_en_v1`, payload indexes on `doc_id`/`source_url`/`title`, int point ids `0..n`).
- `src/retrieve/` — implemented: `base.py` (Qdrant points → `RetrievedChunk`), `dense.py` (cosine top_k 20), `sparse.py` (BM25 top_k 20), `hybrid.py` (prefetch 20+20, server RRF, client-side fallback), `__init__.py` (exports `dense_search`, `sparse_search`, `hybrid_search`, `make_retriever`).
- `src/agent/schemas.py` — implemented (Phase 5.1): `RetrievedChunk`, `Answer` (`kind`, non-empty `answer`, `citations: list[str]`, `confidence` 0–1), `Refusal` (`RefusalReason` str enum `insufficient_context`/`out_of_scope`, default patient-safe message), `CitationCheck` (fail-closed defaults), `AgentOutput` (discriminated union on `kind`).
  V2 adds `EventType`, `Slot`, `BookingIntent`, `BookingReceipt` (`ok=False` is the only failure channel), `Contact` — see SPEC_V2.md §4.
- `src/agent/state.py` — implemented: `AgentState` TypedDict (`question`, `guardrail`, `fused_chunks`, `candidate`, `citation_check`, `response`, `confidence_threshold`), default overwrite semantics (deliberately no reducers).
  V2 adds `booking_intent`, `slots`, `booking_receipt`, `contact` (same overwrite rule) — see SPEC_V2.md §5.
- `src/agent/graph.py` — implemented (Phase 5.3): LangGraph wiring (guardrail, retrieve, generate, verify, decide nodes; conditional edges for flagged/empty paths).
  V2 adds a `booking` node: booking intent → booking → END; never calls the LLM or retrieval — see SPEC_V2.md §6.
- `src/agent/tools.py` — implemented (V2, SPEC_V2.md §3): stdlib `urllib` wrappers over cal.com API v2 (`list_event_types`, `get_slots`, `create_booking`); `CAL_API_KEY` from env at call time, per-endpoint `cal-api-version`, browser `User-Agent`; never raises into the graph (empty list / `BookingReceipt(ok=False)` on failure).
- `src/agent/booking_intent.py` — implemented (V2, SPEC_V2.md §2): deterministic regex booking-intent parse; advice/timing frames and `reschedule` never route to booking.
- `src/agent/callbacks.py` — implemented (V2, SPEC_V2.md §8): callback capture to `data/callbacks.jsonl` (gitignored); name/phone + question hash (never raw text) + reason + UTC timestamp.
- `src/agent/verify.py` — implemented: `verify_citations` checks inline `[SRC:doc_id]` tokens against retrieved chunk IDs; fail-closed on zero citations or fabricated IDs.
- `src/agent/prompts/` (package) — implemented (Phase 5.2): `format_dental_qa_prompt` with `[SRC:doc_id]`-anchored context blocks; versioned templates (`.md`) loaded via `load_prompt_template`.
- `src/agent/guardrail.py` — implemented (Phase 7.2): `screen_question` deterministic regex-based scope gate returning `GuardrailDecision(allowed, rule)`.
- `src/agent/agents.py` — **empty stub**. Reserved for future multi-agent orchestration.
- `src/eval/` — `golden.py` + `ragas/` (eval harness) and, since V2, `deflection.py` (scoreboard math, SPEC_V2.md §8).

## Contracts the tests pin (don't reinvent)
- `rrf_fuse(dense, sparse, k=60, top_n=...)`: rank-based RRF; doc in both lists outranks rank-1-only (`tests/agent/test_fusion.py`).
- Citations: inline `[SRC:doc_id]` tokens; `verify_citations` checks IDs ∈ retrieved set; zero citations or any fabricated ID → `verified=False`, fail closed (`tests/agent/test_verify.py`).
- `build_graph(retriever=..., llm=..., confidence_threshold=...)`: injectable retriever + `llm.with_structured_output(Answer)` fake; empty retrieval / low confidence / fabricated citation → `Refusal` (`tests/agent/test_graph.py`).
  V2 adds optional `list_event_types_fn`/`get_slots_fn`/`create_booking_fn` injections (default to the real cal.com wrappers).
- Booking (SPEC_V2.md §2/§4): a booking word must carry a concrete signal (strong phrase / ISO time / day hint / first-person visit); advice- and timing-shaped sentences and `reschedule` never route to booking — pinned by `tests/agent/test_booking_graph.py`.
  Tools never raise into the graph; a slot the API did not return is never confirmed (`BookingReceipt(ok=False)` + callback offer is the only failure channel) — pinned by `tests/agent/test_tools.py`.
- Schemas: `Answer` (`answer` non-empty, `citations: list[str]`, `confidence` 0–1) vs `Refusal` (`reason` enum, default message mentions consulting a dentist); discriminated union on `kind` (`tests/agent/test_schemas.py`).

## Gotchas
- `tests/agent/test_guardrail.py` (29), `test_graph.py` (4), `test_verify.py` (7), `test_schemas.py` (11), `test_fusion.py` (4), `test_prompts.py` (6) plus V2 files `test_tools.py` (10), `test_booking_graph.py` (18), `test_callbacks.py` (5), `test_deflection.py` (3) — 97 agent tests, all green. Total offline suite is 136 tests. Chunking tests run fast (no model downloads, embedding at upsert time).
- Qdrant `:memory:` ignores payload indexes (warning is benign); Cloud free tier suspends after ~1wk idle. Sparse vectors must be declared at collection creation — never add later (see `DECISIONS/hybrid-qdrant-vector-store.md`). Don't hardcode dim 384; use `client.get_embedding_size()`.
- Logging: `logging.getLogger(__name__)` per module, `basicConfig` only at entry points; no `print()` in library code (`LOGGING.md`).
- Ignored artifacts: `data/parsed/`, `data/embeddings_cache/`, `data/qdrant_storage/`, `data/callbacks.jsonl`, `eval/results/`, `data/raw/_archive/`. Keep versioned snapshots (`chunks_v1.jsonl`, `golden_set_v1.jsonl`) when created.
- No lint, typecheck, or `opencode.json` in repo (CI exists: `.github/workflows/ci.yml`). Streamlit UI at `src/ui/app.py` (Dockerfile for HF Spaces at port 7860).

## Scope guards (from SCOPE.md / PROVENANCE.md)
- Refusal correctness on trap questions is the hard ship gate (100%, zero slack) — never answer diagnostic/prescriptive or out-of-corpus questions confidently.
- Corpus is patient-education only (HRSA/NIDCR/CDC public domain + NHS OGL v3.0). NHS-derived output needs OGL attribution. Do NOT re-add: MedlinePlus/ency, ADA/Colgate/WebMD, NADP glossary, per-Trust leaflets, archived clinical guidelines, CMS glossary — all explicitly rejected.
- Follow `TODO.md` phase order (0–2 gate everything; verify gate per task) and check `SCOPE.md` before adding features.
