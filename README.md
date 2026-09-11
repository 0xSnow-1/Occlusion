# Occlusion: Chairside Dental Patient FAQ Assistant

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/LangGraph-agent_graph-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![Qdrant](https://img.shields.io/badge/Qdrant-hybrid_dense_sparse-blue.svg)](https://qdrant.tech/)
[![Offline tests](https://img.shields.io/badge/tests-100_passed-brightgreen.svg)](https://github.com/0xSnow-1/Occlusion/actions)
[![Ragas](https://img.shields.io/badge/Ragas-faithfulness_0.93-purple.svg)](src/eval/ragas/results/ragas_baseline_v1.json)

> **Status:** MVP in active development. **Domain:** Dental patient education. **Core claim:** cited answers or safe refusal — never a confident guess.
> **Measured:** Ragas faithfulness 0.9304 / relevancy 0.8938 / precision 0.7952 / recall 0.9191 · Harbor safety trilogy 204/204 oracle criteria · live-model pass 192/202 (10 boundary over-refusals under analysis).

## Executive summary

**Occlusion** is a citation-grounded Retrieval-Augmented Generation system over a small, openly licensed dental patient-education corpus (HRSA/NIDCR/CDC public domain + NHS UK OGL v3.0).
It answers routine questions with inline `[SRC:doc_id]` citations verified against retrieved chunks, and refuses diagnostic, prescriptive, or out-of-corpus questions through a deterministic pre-LLM guardrail plus fail-closed validation gates.
Every change is measured against a versioned golden set and a Ragas harness with a judge model distinct from the generator.

Built as a portfolio project, it demonstrates hybrid retrieval, LangGraph orchestration with Pydantic-structured outputs, healthcare-grade safety wiring, and eval-driven development with honest baselines — including open backlogs.

## Problem

Dental front desks drown in routine-question call volume (SCOPE.md §2, industry data):

- Staff spend an estimated 50–60% of work hours on phone calls (40–60 calls/day at 4–6 min each).
- Practices miss roughly 20–35% of incoming calls during business hours.
- ~45% of calls arrive outside 9–5, when no one answers.
- 67% of patients still prefer phone over FAQ pages for anything beyond simple scheduling.

A static FAQ handles fixed phrasing but breaks on paraphrase and multi-part asks and produces no auditable citation trail.
Occlusion absorbs the routine subset in seconds and reliably refuses anything symptom- or record-specific.

## What is built (as-built, per `spec.md`)

```text
User question
  |
Deterministic guardrail (regex, no LLM) — flagged? --> Refusal(out_of_scope), LLM never called
  | allowed
Hybrid retrieval (Qdrant dense top_k 20 + sparse top_k 20, server RRF, client rrf_fuse fallback, top_n 5)
  |
RAG generation (LLM with_structured_output(Answer) -> { answer, citations, confidence })
  |
Validation gates (deterministic code):
  Gate 1 empty retrieval / Gate 2 citation IDs in retrieved set / Gate 3 confidence >= threshold
  |-- fail --> Refusal (fresh object every run, reason enum, "consult a dentist" message)
  |-- pass --> Answer + source links --> END
```

- Entry node is `guardrail` (`src/agent/guardrail.py`, `screen_question` → `GuardrailDecision`). No tokens spent on refusals.
- `build_graph(retriever, llm, confidence_threshold)` takes any `(query, *, top_n) -> list[RetrievedChunk]` retriever plus an LLM exposing `.with_structured_output(Answer)`.
- `verify_citations` fails closed on zero citations or any fabricated ID; `coverage = matches / total`.
- Cross-cutting: LangSmith tracing, versioned prompts in `src/agent/prompts/`, logging per `LOGGING.md` (no `print()` in library code).

> Note on `Architecture_diagram_v3.png`: that canvas shows the fuller target vision (router, conversational path, evaluator-optimizer retry loop).
> The code and tests on `main` pin the simpler pipeline above (`spec.md` §2, §5). Router / NC-agent / bounded-retry loop are explicitly future work — see Roadmap.

## Core engineering

### Hybrid retrieval with RRF

- **Dense** `sentence-transformers/all-MiniLM-L6-v2` (cosine) for paraphrase; **sparse** `prithivida/Splade_PP_en_v1` (SPLADE/BM25-style) for exact terminology. Dimension read via `client.get_embedding_size()`, never hardcoded.
- Collection declared hybrid-ready from day one (dense + sparse at creation; sparse cannot be added later — see `DECISIONS/hybrid-qdrant-vector-store.md`). Payload indexes on `doc_id` / `source_url` / `title`.
- `hybrid_search(..., top_k=20, top_n=5, fusion_k=60)`: two prefetches fused server-side with `FusionQuery(fusion=RRF)`; client-side `rrf_fuse(dense, sparse, k=60)` fallback. Rank-based fusion because cosine (bounded) and BM25 (unbounded) scores are incomparable.
- `rrf_fuse` contract pinned by `tests/agent/test_fusion.py`: a doc in both lists outranks a rank-1-only doc.
- `make_retriever(client, collection, variant="hybrid"|"dense"|"sparse")` is the seam the graph and harness share.

### Safety wiring (the hard gate)

- Guardrail rules are decision-shaped (dosage/medication frames, `do I have` diagnosis, `should I get <treatment>`), not keyword blocklists — so informational mentions of pain/antibiotics/root canal still pass. Pinned by 29 tests in `tests/agent/test_guardrail.py` (12 flagged + 17 allowed incl. boundary cases).
- Graph gates pinned by `tests/agent/test_graph.py` with stub retriever + FakeLLM: empty retrieval, low confidence, and fabricated citation each produce `Refusal`.
- Refusal reasons are wire contracts: guardrail-flagged → `out_of_scope`; failed validation / empty retrieval → `insufficient_context`. Every refusal message mentions consulting a dentist.
- Real pre-guardrail escape is on record (`SHARED_CONTEXT.md`): an amoxicillin-dosage ask once returned as `kind=answer` at confidence 0.95 — the reason the guardrail sits pre-LLM.

### Ingestion

- Parse: `PyMuPDFLoader` per PDF page (`doc_id` = file stem) + `WebBaseLoader` per HTML page (`doc_id` = URL slug). Failures logged and skipped.
- Chunk: `RecursiveCharacterTextSplitter` 1000/200, each chunk inherits source metadata plus `chunk_index`/`chunk_total`. Embedding at upsert via fastembed `models.Document` (no separate embedding stage).
- Index: `VectorStore` recreates the collection each run (`recreate_collection=True`), integer point ids `0..n`, payloads self-contained (text + metadata) so retrieval feeds the LLM directly. Default store `./data/qdrant_storage` (gitignored); `:memory:` for tests; `https://` URL for Cloud.
- First end-to-end run: 28 pages → 118 chunks → 118 points.

## Evaluation (measured, not claimed)

### Ragas baseline — `src/eval/ragas/results/ragas_baseline_v1.json`

Generator `global.anthropic.claude-haiku-4-5-20251001-v1:0` (temp 0) · judge `global.anthropic.claude-sonnet-4-5-20250929-v1:0` (distinct — no self-judging) · hybrid retriever, top_n 5 · confidence threshold 0.7.
Golden set `data/golden_set_v1.jsonl`: 78 items (70 `answer` + 6 `refuse_diagnostic` + 2 `refuse_no_coverage`), schema-validated by `src/eval/golden.py`.

| Metric | Target (SCOPE.md §6) | Measured mean | Verdict |
|---|---|---|---|
| Faithfulness | ≥ 0.85 | **0.9304** (68 scored) | PASS |
| Response relevancy | ≥ 0.80 | **0.8938** | PASS |
| Context precision | ≥ 0.75 | **0.7952** | PASS |
| Context recall | measured | **0.9191** | recorded |

Notes: 68 items scored, 2 refused unscored (`G07`, `G37`); 1 item NaN on precision excluded from mean; ~20 items score < 0.75 on precision — open retrieval-ranking backlog (see `SHARED_CONTEXT.md` pointer). Refusals are never Ragas-scored by design.
Reproduce (needs Bedrock + ingested `occlusion` collection): `uv run python -m src.eval.ragas.run_ragas --limit 3` smoke, then full run.

### Harbor safety trilogy — 204/204 oracle criteria (frozen doubles, $0)

| Task | What it proves | Scale | Result |
|---|---|---|---|
| `trap-refusal` | Obvious traps refuse with correct reason; controls answer; LLM never called on Gate-0/empty paths | 25 Q (20 traps + 5 controls), 73 criteria | **73/73** (`evals/jobs/2026-09-08__03-02-25`) |
| `boundary-precision` | Informational symptom/medication/treatment phrasings still answer (no over-refusal) | 25 B-items, 53 criteria | **53/53** (`evals/jobs/2026-09-08__03-02-55`) |
| `nearmiss-refusal` | Minimal-pair traps (one word flips answer→refuse) still refuse | 25 N-items, 78 criteria | **78/78** (`evals/jobs/2026-09-08__03-03-25`) |

Specs: `evals/guardrails/tasks/{trap-refusal,boundary-precision,nearmiss-refusal}/Task.md`. Exact-match verifiers on `kind`/`reason`/call pattern; `no-edit-rules` hash-checks forbid editing guardrail sources to pass.

### Live-model pass — 192/202 (honest backlog)

`live-model-refusal` (Draft spec): same 75 trilogy questions through real `:memory:` Qdrant hybrid retrieval + live Bedrock Haiku 4.5 @ temp 0.
All 44 refusal-side items pass; 10 boundary items over-refuse (5× Gate-2 no-citation, 5× Gate-3 low-confidence) — the current calibration backlog, recorded in `SHARED_CONTEXT.md`.
Latency/cost are recorded, never gated; SCOPE §6 target is P95 < 3 s and documented cost @ ~500 queries/day.

**Ship gate:** any trap question answered confidently instead of refused = do not ship, regardless of every other number.

### Latency and cost (measured 2026-09-10)

| Metric | Value | Notes |
|---|---|---|
| Latency P50 | 3.5 s | 12 timed calls, local Qdrant + Bedrock Haiku 4.5 |
| Latency P95 | 4.9 s | Target under review (deploy adds cold start) |
| Cost per query | ~$0.01 est. | ~$1 per 75-call live pass → ~$5/day @ 500 queries |

## Corpus and provenance

~15 openly licensed patient-education documents (`data/PROVENANCE.md`, `data/HTML_SOURCES.md`):

- **4 PDFs** (`data/raw/`): HRSA (HHS) brushing/flossing, dry mouth, routine-care guides; NIDCR/NIH older-adults guide.
- **11 HTML pages** (ingested via `DEFAULT_HTML_URLS`): NIDCR gum disease, CDC cavities, 9× NHS UK (wisdom-tooth, root canal, decay, gum disease, grinding, abscess, knocked-out tooth, toothache, treatments).

Licenses: US HRSA/NIDCR/CDC = public domain; NHS UK = OGL v3.0 — outputs derived from NHS material carry *"Contains public sector information licensed under the Open Government Licence v3.0."*
Known limits (documented, not hidden): triage navigation is NHS-based (111/999/A&E, not silently localized); insurance terminology descoped to v1 (`refuse_no_coverage` golden items); fillings/scale-and-polish aftercare covered at overview level only.
Deliberately excluded and archived (`data/raw/_archive/`, gitignored): 9 clinical-guideline files (v2 clinician-mode candidate), CMS glossary, plus rejected MedlinePlus/ency, ADA/Colgate/WebMD, NADP glossary, per-Trust leaflets — see `RESEARCHER_OUTPUT.md`.

## Tech stack

| Layer | Choice | Why it matters |
|---|---|---|
| Language / pkg | Python 3.12+, `uv`, `pythonpath=["."]` (`src.*` imports) | Reproducible, fast |
| Orchestration | LangGraph (`build_graph`) | Explicit nodes/edges, testable gates |
| Vector DB | Qdrant (dense cosine + sparse SPLADE, RRF) | Hybrid from day one, no migration |
| Embeddings | fastembed at upsert (`models.Document`) | Local, no embedding service |
| Parsing | PyMuPDF + WebBaseLoader | PDF pages + HTML → markdown |
| Structured output | Pydantic v2 (`Answer` vs `Refusal` discriminated on `kind`) | LLM output is a contract |
| Eval | Ragas (distinct judge) + Harbor trilogy + golden set | Quality + safety, separately |
| Observability | LangSmith tracing | Per-node latency/tokens/cost |
| Demo | scripts `run_ingest.py` / `run_agent.py` (`--chat`) | No FastAPI/UI yet (TODO Phase 9) |

## Run it locally

Prerequisites: Python 3.12+, `uv`, Bedrock **or** Groq keys (pick one generation path for the MVP).

```bash
git clone https://github.com/0xSnow-1/Occlusion.git
cd Occlusion
uv sync
cp sample.env .env   # fill keys; .env is gitignored, never commit it
uv run python scripts/run_ingest.py        # default corpus -> ./data/qdrant_storage
uv run python scripts/run_agent.py --chat  # interactive (quit with quit/q; Qdrant local lock is single-process)
uv run pytest tests/ingest/ tests/retrieve/ tests/agent/ -q
```

Single test: `uv run pytest tests/agent/test_guardrail.py -q`.
Ragas smoke (needs Bedrock + ingested collection): `uv run python -m src.eval.ragas.run_ragas --limit 3`.
CI (`.github/workflows/ci.yml`) runs the offline pytest suite on push/PR to `main`. Full Ragas/Harbor evals run on demand (cost discipline: judge calls scale with items × metrics).

## Testing

100 offline tests, green: 61 agent (`test_guardrail` 29, `test_graph` 4, `test_verify` 7, `test_schemas` 11, `test_fusion` 4, `test_prompts` 6) + 39 ingest/retrieve.
Qdrant `:memory:` ignores payload indexes (benign warning); Cloud free tier suspends after ~1 wk idle; sparse vectors must exist at collection creation.
Logging: `logging.getLogger(__name__)` per module, `basicConfig` only at entry points, no `print()` in library code.

## Demo

Deploys to Hugging Face Spaces (Docker SDK — see `Dockerfile`) in TODO.md Phase 9. Create the Space manually, then set:

- SDK: Docker · hardware: CPU basic (free) · port 7860
- Secrets (never in the repo): `AWS_BEARER_TOKEN_BEDROCK`, `BEDROCK_MODEL_ID`, `BEDROCK_REGION`

The image bakes the Qdrant index at build time (`data/qdrant_storage/` is gitignored and cannot be bundled). URL will be posted here once live.

## Docs

- `spec.md` — as-built technical reference (code + tests win over older docs)
- `SCOPE.md` — scope, refusal taxonomy, ship/kill criteria, v2 parking lot
- `TODO.md` — phased roadmap with per-task verify gates
- `AGENTS.md` — module contracts, test pins, gotchas
- `SHARED_CONTEXT.md` — current pointer, learnings, eval roadmap
- `Architecture Design desc.md` + `Architecture_diagram_v3.png` — target-vision companion (see as-built note above)
- `data/PROVENANCE.md`, `data/HTML_SOURCES.md` — corpus manifests
- `DECISIONS/hybrid-qdrant-vector-store.md`, `LOGGING.md`

## Roadmap (v2 parking lot, deliberately not v1)

Cross-encoder rerank (only if evals earn its latency) · original dental-benefit glossary · US triage source · clinician-mode corpus · MCP tool exposure · front-desk dashboard · multi-turn memory · multilingual. `TODO.md` phase order gates everything; check `SCOPE.md` before adding features.

## License

Code: MIT — see [LICENSE](LICENSE).
Corpus content: US public domain (HRSA/NIDCR/CDC) + OGL v3.0 (NHS UK).
NHS-derived output requires: *"Contains public sector information licensed under the Open Government Licence v3.0."*

## Contact

Portfolio project — implementation by the repo owner, decisions by the owner. Issues and doc-fix PRs welcome; new dependencies need explicit owner approval first.

- GitHub: <https://github.com/0xSnow-1/Occlusion>
- LinkedIn / Email: add your profiles here

---

*Occlusion: cited answers or safe refusal — measured, not claimed.*
