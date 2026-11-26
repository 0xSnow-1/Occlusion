# Tech stack

All versions below are **found** in `pyproject.toml` / README / AGENTS.md unless marked assumed.

## Choices

- Language and runtime: Python ≥3.12, `uv` for dependency management, `pythonpath = ["."]` so imports are `src.*` (**found**)
- Orchestration: LangGraph (`build_graph(retriever, llm, confidence_threshold)`) with explicit nodes/edges for guardrail → retrieve → generate → verify → decide (**found**)
- Vector DB: Qdrant — dense cosine + sparse SPLADE (`Splade_PP_en_v1`), server-side RRF with client-side `rrf_fuse` fallback. Default store is repo-local `./data/qdrant_storage` (Cloud deliberately not used) (**found**)
- Embeddings: fastembed at upsert time via `models.Document`; dense model `sentence-transformers/all-MiniLM-L6-v2`; dimension from `client.get_embedding_size()`, never hardcoded (**found**)
- Parsing: PyMuPDF (`PyMuPDFLoader`) for PDFs, `WebBaseLoader` for HTML (**found**)
- Generation: AWS Bedrock only (`boto3` / `langchain-aws`); generator `claude-haiku-4-5` at temperature 0 in recorded baselines (**found**)
- Structured output: Pydantic v2 `Answer` vs `Refusal` discriminated on `kind` (**found**)
- Eval: Ragas 0.4.2 (judge distinct from generator) + Harbor safety trilogy + hand-written golden set `data/golden_set_v1.jsonl` (**found**)
- Tracing: LangSmith (**found**; Task 6.3 tag conventions still unverified)
- Demo UI: Streamlit at `src/ui/app.py`, live on Streamlit Community Cloud; `Dockerfile` + `spaces/zerogpu/` optional and not deployed (**found**)
- Rerank (planned): local cross-encoder over hybrid top-k before top_n cut; toggleable, off by default until measured (TODO Phase 4.3; owner decision 2026-11-25) (**planned**)

## Constraints

- Never edit `src/agent/guardrail.py` rules to improve eval numbers. Refusal misses need new boundary tests in `tests/agent/test_guardrail.py`. A missed trap refusal is a failed project (SCOPE.md §7).
- No new dependencies without explicit owner approval: research 1–2 candidates, explain in plain language, record the winner (AGENTS.md). Cross-encoder rerank will need this approval when implemented.
- Never commit `.env` or secrets. `.env*`, credential files are gitignored; rotate anything that ever touched a commit.
- Never run workspace-wide `uv` commands from `/home/snowaflic`; run inside this project only.
- `SHARED_CONTEXT.md` is human-reviewed; do not treat agent edits as final without owner review.
- Corpus stays patient-education only: no PHI, no diagnosis, no rejected sources (SCOPE.md §5, `data/PROVENANCE.md`).
- NHS-derived output must carry the OGL v3.0 attribution sentence.
- Qdrant sparse vectors must exist at collection creation; local path mode is single-process (lock file).
- New deps and architectural choices are owner decisions; agents implement, owners decide (AGENTS.md).

## Testing

- Framework: pytest (`dev` group, `pytest>=9.1.0`)
- Location: `tests/ingest/`, `tests/retrieve/`, `tests/agent/`, `tests/eval/`
- Must pass before a commit / merge: `uv run pytest tests/ingest/ tests/retrieve/ tests/agent/ tests/eval/ -q` (144 offline tests green as of README; CI runs the offline suite on push/PR to `main` via `.github/workflows/ci.yml`)
- Single test: `uv run pytest tests/<path>::<Class>::<test_name> -q`
- Full Ragas / Harbor runs are on-demand (cost discipline), not on every push
- Expectations: tests are offline (no model downloads, no API keys); graph tests use stub retriever + FakeLLM; guardrail suite pins both flagged and allowed boundary families
- If the test command or test paths change, update AGENTS.md and the CI pytest line together

## How to run

```bash
uv sync
cp sample.env .env          # fill Bedrock keys; never commit .env

# Ingest (local PDFs only needs no keys)
uv run python scripts/run_ingest.py --pdf-only
# Full corpus: 4 PDFs + 11 HTML pages
uv run python scripts/run_ingest.py

# Interactive agent (repo-local Qdrant; quit with quit/q before starting a second process)
uv run python scripts/run_agent.py --chat

# Demo UI (needs ingested collection + Bedrock keys)
uv run streamlit run src/ui/app.py

# Offline test suite
uv run pytest tests/ingest/ tests/retrieve/ tests/agent/ tests/eval/ -q

# Ragas smoke (needs Bedrock + ingested collection)
uv run python -m src.eval.ragas.run_ragas --limit 3
```

## Project structure

- `src/ingest/` — parse, chunk, embed-at-upsert, Qdrant vector store
- `src/retrieve/` — dense, sparse, hybrid (+ `make_retriever` seam)
- `src/agent/` — schemas, state, graph, guardrail, verify, fusion, versioned prompts
- `src/eval/` — golden-set loader, Ragas harness + committed baseline results
- `src/ui/` — Streamlit app
- `scripts/` — `run_ingest.py`, `run_agent.py`
- `tests/` — offline suite pinned in AGENTS.md
- `data/` — raw corpus, provenance, golden set, gitignored qdrant storage / parsed / embeddings cache
- `docs/internal/TODO.md` — detailed phase plan with verify gates (roadmap index points here)
- `SCOPE.md`, `spec.md`, `AGENTS.md`, `SHARED_CONTEXT.md` — scope, as-built spec, agent contracts, shared state
- `specs/` — this constitution (mission, tech-stack, roadmap)
