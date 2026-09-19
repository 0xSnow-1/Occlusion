# Occlusion: Chairside Dental Patient FAQ Assistant

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/LangGraph-agent_graph-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![Qdrant](https://img.shields.io/badge/Qdrant-hybrid_dense_sparse-blue.svg)](https://qdrant.tech/)
[![Offline tests](https://img.shields.io/badge/tests-129_passed-brightgreen.svg)](https://github.com/0xSnow-1/Occlusion/actions)
[![Ragas](https://img.shields.io/badge/Ragas-faithfulness_0.93-purple.svg)](src/eval/ragas/results/ragas_baseline_v1.json)

> **Status:** MVP in active development. **Domain:** Dental patient education. **Core claim:** cited answers or safe refusal, never a confident guess.
> **Measured:** Ragas faithfulness 0.9304 / relevancy 0.8938 / precision 0.7952 / recall 0.9191 · Harbor safety trilogy 204/204 oracle criteria · live-model pass 192/202 (10 boundary over-refusals under analysis).

## Executive summary

**Occlusion** is a citation-grounded Retrieval-Augmented Generation system over a small, openly licensed dental patient-education corpus (HRSA/NIDCR/CDC public domain + NHS UK OGL v3.0).
It answers routine questions with inline `[SRC:doc_id]` citations verified against retrieved chunks, and refuses diagnostic, prescriptive, or out-of-corpus questions through a deterministic pre-LLM guardrail plus fail-closed validation gates.
Every change is measured against a versioned golden set and a Ragas harness with a judge model distinct from the generator.

Built as a portfolio project, it demonstrates hybrid retrieval, LangGraph orchestration with Pydantic-structured outputs, healthcare-grade safety wiring, and eval-driven development with honest baselines, including open backlogs.

## Try it in 60 seconds

The demo answers ONLY from the documents listed below — never from general knowledge. Paste these three questions in order:

1. `How am I supposed to brush my teeth properly?` → answered with clickable source links.
2. `What dosage of amoxicillin should I take for a toothache?` → refused in ~0.1s without the AI ever being asked (medication decisions are out of scope).
3. `What is the capital of France?` → refused (outside the corpus; answered honestly instead of guessed).

Refusals outside the corpus are deliberate, not broken. The same three questions are clickable buttons in the demo sidebar.

What it covers, in plain words: brushing and flossing, cavities and tooth decay, gum disease, dry mouth, dentures, children's teeth basics, plus emergency and post-procedure guidance from NHS UK sources (knocked-out tooth, abscess, toothache, wisdom-tooth removal, root canals). Anything else — medication doses, personal diagnosis, insurance, off-topic — is refused on purpose.

## Problem

Dental front desks drown in routine-question call volume (SCOPE.md §2, industry data):

- Staff spend an estimated 50-60% of work hours on phone calls (40-60 calls/day at 4-6 min each).
- Practices miss roughly 20-35% of incoming calls during business hours.
- ~45% of calls arrive outside 9-5, when no one answers.
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
> The code and tests on `main` pin the simpler pipeline above (`spec.md` §2, §5). Router, NC-agent, and the bounded-retry loop are explicitly future work. See Roadmap.

## Core engineering

### Hybrid retrieval with RRF

- **Dense** `sentence-transformers/all-MiniLM-L6-v2` (cosine) for paraphrase; **sparse** `prithivida/Splade_PP_en_v1` (SPLADE/BM25-style) for exact terminology. Dimension read via `client.get_embedding_size()`, never hardcoded.
- Collection declared hybrid-ready from day one (dense + sparse at creation; sparse cannot be added later, see `DECISIONS/hybrid-qdrant-vector-store.md`). Payload indexes on `doc_id` / `source_url` / `title`.
- `hybrid_search(..., top_k=20, top_n=5, fusion_k=60)`: two prefetches fused server-side with `FusionQuery(fusion=RRF)`; client-side `rrf_fuse(dense, sparse, k=60)` fallback. Rank-based fusion because cosine (bounded) and BM25 (unbounded) scores are incomparable.
- `rrf_fuse` contract pinned by `tests/agent/test_fusion.py`: a doc in both lists outranks a rank-1-only doc.
- `make_retriever(client, collection, variant="hybrid"|"dense"|"sparse")` is the seam the graph and harness share.

### Safety wiring (the hard gate)

- Guardrail rules are decision-shaped (dosage/medication frames, `do I have` diagnosis, `should I get <treatment>`), not keyword blocklists, so informational mentions of pain/antibiotics/root canal still pass. Pinned by 29 tests in `tests/agent/test_guardrail.py` (12 flagged + 17 allowed incl. boundary cases).
- Graph gates pinned by `tests/agent/test_graph.py` with stub retriever + FakeLLM: empty retrieval, low confidence, and fabricated citation each produce `Refusal`.
- Refusal reasons are wire contracts: guardrail-flagged → `out_of_scope`; failed validation / empty retrieval → `insufficient_context`. Every refusal message mentions consulting a dentist.
- Real pre-guardrail escape is on record (`SHARED_CONTEXT.md`): an amoxicillin-dosage ask once returned as `kind=answer` at confidence 0.95, which is why the guardrail sits pre-LLM.

### Ingestion

- Parse: `PyMuPDFLoader` per PDF page (`doc_id` = file stem) + `WebBaseLoader` per HTML page (`doc_id` = URL slug). Failures logged and skipped.
- Chunk: `RecursiveCharacterTextSplitter` 1000/200, each chunk inherits source metadata plus `chunk_index`/`chunk_total`. Embedding at upsert via fastembed `models.Document` (no separate embedding stage).
- Index: `VectorStore` recreates the collection each run (`recreate_collection=True`), integer point ids `0..n`, payloads self-contained (text + metadata) so retrieval feeds the LLM directly. Default store `./data/qdrant_storage` (gitignored); `:memory:` for tests; `https://` URL for Cloud.
- First end-to-end run: 28 pages → 118 chunks → 118 points.

## Evaluation (measured, not claimed)

### Ragas baseline: `src/eval/ragas/results/ragas_baseline_v1.json`

Generator `global.anthropic.claude-haiku-4-5-20251001-v1:0` (temp 0), judge `global.anthropic.claude-sonnet-4-5-20250929-v1:0` (distinct, no self-judging), hybrid retriever, top_n 5, confidence threshold 0.7.
Golden set `data/golden_set_v1.jsonl`: 78 items (70 `answer` + 6 `refuse_diagnostic` + 2 `refuse_no_coverage`), schema-validated by `src/eval/golden.py`.

| Metric | Target (SCOPE.md §6) | Measured mean | Verdict |
|---|---|---|---|
| Faithfulness | ≥ 0.85 | **0.9304** (68 scored) | PASS |
| Response relevancy | ≥ 0.80 | **0.8938** | PASS |
| Context precision | ≥ 0.75 | **0.7952** | PASS |
| Context recall | measured | **0.9191** | recorded |

Notes: 68 items scored, 2 refused unscored (`G07`, `G37`); 1 item NaN on precision excluded from mean; ~20 items score < 0.75 on precision, which is the open retrieval-ranking backlog (see `SHARED_CONTEXT.md` pointer). Refusals are never Ragas-scored by design.
Reproduce (needs Bedrock + ingested `occlusion` collection): `uv run python -m src.eval.ragas.run_ragas --limit 3` smoke, then full run.

### Harbor safety trilogy: 204/204 oracle criteria (frozen doubles, $0)

| Task | What it proves | Scale | Result |
|---|---|---|---|
| `trap-refusal` | Obvious traps refuse with correct reason; controls answer; LLM never called on Gate-0/empty paths | 25 Q (20 traps + 5 controls), 73 criteria | **73/73** (`evals/jobs/2026-09-08__03-02-25`) |
| `boundary-precision` | Informational symptom/medication/treatment phrasings still answer (no over-refusal) | 25 B-items, 53 criteria | **53/53** (`evals/jobs/2026-09-08__03-02-55`) |
| `nearmiss-refusal` | Minimal-pair traps (one word flips answer→refuse) still refuse | 25 N-items, 78 criteria | **78/78** (`evals/jobs/2026-09-08__03-03-25`) |

Specs: `evals/guardrails/tasks/{trap-refusal,boundary-precision,nearmiss-refusal}/Task.md`. Exact-match verifiers on `kind`/`reason`/call pattern; `no-edit-rules` hash-checks forbid editing guardrail sources to pass.

### Live-model pass: 192/202 (honest backlog)

`live-model-refusal` (approved 2026-09-08): same 75 trilogy questions through real `:memory:` Qdrant hybrid retrieval + live Bedrock Haiku 4.5 @ temp 0.
All 44 refusal-side items pass; 10 boundary items over-refuse (5x Gate-2 no-citation, 5x Gate-3 low-confidence). That is the current calibration backlog, recorded in `SHARED_CONTEXT.md`.
Latency/cost are recorded, never gated; SCOPE §6 target was P95 < 3 s, recalibrated by owner decision 2026-09-19 to ~5 s accepted (Bedrock round-trip is the driver). Documented cost @ ~500 queries/day.

**Ship gate:** any trap question answered confidently instead of refused = do not ship, regardless of every other number.

### Latency and cost (measured 2026-09-10, local hardware)

| Metric | Value | Notes |
|---|---|---|
| Latency P50 | 3.5 s | 12 timed `graph.invoke` calls, repo-local Qdrant, hybrid retriever, Bedrock Haiku 4.5 at temp 0, threshold 0.7 |
| Latency P95 | 4.9 s | Over the original P95 < 3 s target; owner recalibrated to ~5 s accepted on 2026-09-19 |
| Cost per query | ~$0.01 est. | ~$1 per 75-call live pass → ~$5/day @ 500 queries |

The driver is the Bedrock round-trip, not retrieval. Staging must re-measure before any ship claim, since deploy adds cold start and never subtracts.

Index parity note: eval numbers were measured on the frozen 120-chunk snapshot. The Docker image bakes a 136-point superset index (the CDC `about` page served its full content at build time instead of the 1-chunk stub). Demo-safe, but eval-demo parity is not exact.

## Corpus and provenance

~15 openly licensed patient-education documents (`data/PROVENANCE.md`, `data/HTML_SOURCES.md`):

- **4 PDFs** (`data/raw/`): HRSA (HHS) brushing/flossing, dry mouth, routine-care guides; NIDCR/NIH older-adults guide.
- **11 HTML pages** (ingested via `DEFAULT_HTML_URLS`): NIDCR gum disease, CDC cavities, 9× NHS UK (wisdom-tooth, root canal, decay, gum disease, grinding, abscess, knocked-out tooth, toothache, treatments).

Licenses: US HRSA/NIDCR/CDC is public domain; NHS UK is OGL v3.0. Outputs derived from NHS material carry *"Contains public sector information licensed under the Open Government Licence v3.0."*
Known limits (documented, not hidden): triage navigation is NHS-based (111/999/A&E, not silently localized); insurance terminology descoped to v1 (`refuse_no_coverage` golden items); fillings/scale-and-polish aftercare covered at overview level only.
Deliberately excluded and archived (`data/raw/_archive/`, gitignored): 9 clinical-guideline files (v2 clinician-mode candidate), CMS glossary, plus rejected MedlinePlus/ency, ADA/Colgate/WebMD, NADP glossary, per-Trust leaflets. See `RESEARCHER_OUTPUT.md`.

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
| Demo | Streamlit UI at `src/ui/app.py` (+ scripts `run_ingest.py` / `run_agent.py` `--chat`) | Chat face over the production graph; Dockerfile → HF Spaces (port 7860) |

## Run it locally

Prerequisites: Python 3.12+, `uv`, and Bedrock keys in `.env`.
Bedrock is the only wired generation path, and Qdrant runs repo-local at `./data/qdrant_storage`, so no Qdrant Cloud keys are needed.

```bash
git clone https://github.com/0xSnow-1/Occlusion.git
cd Occlusion
uv sync
cp sample.env .env   # fill keys; .env is gitignored, never commit it
uv run python scripts/run_ingest.py --pdf-only  # try path: local PDFs only, no HTML fetch, no keys needed
uv run python scripts/run_agent.py --chat  # interactive (quit with quit/q; Qdrant local lock is single-process)
uv run streamlit run src/ui/app.py         # demo UI (requires ingested collection + Bedrock .env keys)
uv run pytest tests/ingest/ tests/retrieve/ tests/agent/ -q
```

Two ingest paths. Start with `--pdf-only`: it ingests local PDFs from `data/raw` only and skips the 11 HTML sources, so it needs no HTML fetch and no API keys. Run the full ingest (`uv run python scripts/run_ingest.py` with no flag) when you want the whole corpus: 4 PDFs plus 11 HTML pages into `./data/qdrant_storage`. Qdrant path mode holds a single-process lock, so close the chat session (type `quit` or `q`) before starting Streamlit or a second run.

Single test: `uv run pytest tests/agent/test_guardrail.py -q`.
Ragas smoke (needs Bedrock + ingested collection): `uv run python -m src.eval.ragas.run_ragas --limit 3`.
CI (`.github/workflows/ci.yml`) runs the offline pytest suite on push/PR to `main`. Full Ragas/Harbor evals run on demand (cost discipline: judge calls scale with items × metrics).

## Testing

111 offline tests, green: 61 agent (`test_guardrail` 29, `test_graph` 4, `test_verify` 7, `test_schemas` 11, `test_fusion` 4, `test_prompts` 6) + 39 ingest/retrieve + 11 source-link and OGL (`test_source_url` 5, `test_ogl_disclaimer` 6).
Qdrant `:memory:` ignores payload indexes (benign warning); Cloud free tier suspends after ~1 wk idle; sparse vectors must exist at collection creation.
Logging: `logging.getLogger(__name__)` per module, `basicConfig` only at entry points, no `print()` in library code.

## Demo

Live demo: Streamlit Community Cloud (free tier, no card) — URL will be posted here once live: `https://<your-app>.streamlit.app`.

Deploy (owner only, 5 minutes): sign in at share.streamlit.io with GitHub → Create app → repo `0xSnow-1/Occlusion`, branch `main`, main file `src/ui/app.py`, Python 3.12 → Advanced settings → Secrets (TOML): `AWS_BEARER_TOKEN_BEDROCK`, `BEDROCK_MODEL_ID`, `BEDROCK_REGION` → Deploy. Dependencies install from `requirements.txt` at repo root; the Qdrant index is vendored at `data/qdrant_storage/` (force-added, 179 points, 1.4 MB — re-vendor after any corpus change with `uv run python scripts/run_ingest.py` then `git add -f data/qdrant_storage`).

Hibernation note: Community Cloud sleeps apps after 12h without traffic; anyone visiting wakes it by clicking. First wake is slow (dependency load plus embedding-model download), then faster follow-ups in the same session. The vendored index is a superset of the 120-chunk eval snapshot (see latency notes above).

To try it locally, run in order: `uv run python scripts/run_ingest.py --pdf-only`, then `uv run python scripts/run_agent.py --chat` and ask one routine question, then `uv run streamlit run src/ui/app.py`. The chat prints each node as it runs (guardrail, retrieve, generate, verify, decide) followed by the structured Answer or Refusal as JSON. The Streamlit page shows the same answer with confidence, clickable source links, and retrieved evidence.

Sources in the UI are clickable `[doc_id](url)` links with a backticked chip fallback for legacy chunks that predate `source_url`. The disclaimer at the top of the page and the footer under every answer both carry the exact sentence `Contains public sector information licensed under the Open Government Licence v3.0.` (see `OGL_ATTRIBUTION`, `citation_link`, and `format_answer_footer` in `src/ui/app.py`).

## Docs

- `spec.md`: as-built technical reference (code + tests win over older docs)
- `SCOPE.md`: scope, refusal taxonomy, ship/kill criteria, v2 parking lot
- `TODO.md`: phased roadmap with per-task verify gates
- `AGENTS.md`: module contracts, test pins, gotchas
- `SHARED_CONTEXT.md`: current pointer, learnings, eval roadmap
- `Architecture Design desc.md` + `Architecture_diagram_v3.png`: target-vision companion (see as-built note above)
- `data/PROVENANCE.md`, `data/HTML_SOURCES.md`: corpus manifests
- `DECISIONS/hybrid-qdrant-vector-store.md`, `LOGGING.md`

## Roadmap (v2 parking lot, deliberately not v1)

Cross-encoder rerank (only if evals earn its latency) · original dental-benefit glossary · US triage source · clinician-mode corpus · MCP tool exposure · front-desk dashboard · multi-turn memory · multilingual. `TODO.md` phase order gates everything; check `SCOPE.md` before adding features.

## License

Code: MIT, see [LICENSE](LICENSE).
Corpus content: US public domain (HRSA/NIDCR/CDC) + OGL v3.0 (NHS UK).
NHS-derived output requires: *"Contains public sector information licensed under the Open Government Licence v3.0."*

## Contact

Portfolio project. Implementation by the repo owner, decisions by the owner. Issues and doc-fix PRs welcome; new dependencies need explicit owner approval first.

- GitHub: <https://github.com/0xSnow-1/Occlusion>

---

*Occlusion: cited answers or safe refusal, measured, not claimed.*
