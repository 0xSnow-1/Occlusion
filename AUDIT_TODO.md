# AUDIT_TODO.md - Remediation plan from the independent audit

> `TODO.md` is the original build plan.
> This file is the audit remediation queue.
> Work top to bottom.
> Do not check a box until its Verify step passes.

## How to use this file

- Pick exactly one task.
- Read the whole task before editing.
- Run the Verify step and paste the evidence into the PR body.
- Handoff notes go in `.agents/handoffs/<branch>.md`.

## Baseline re-checked in this repo

- Offline suite: 132 passed in about 3 seconds.
- Vendored Qdrant index: 179 points.
- Archive contamination: 45 points (25%) from `data/raw/_archive/`.
- Archive breakdown: `Uniform-Glossary-01-2020` 26, `AHA_ADA_Antibiotic_Prophylaxis_Guidelines` 8, `IADT_Traumatic_Dental_Injuries_Guidelines` 6, `AAPD_Pediatric_Local_Anesthesia` 5.
- `tests/eval/` does not exist.
- CI runs only `tests/ingest/ tests/retrieve/ tests/agent/`.
- `ragas` harness logs PASS/FAIL but never exits nonzero.
- No `langsmith` imports anywhere.
- `LOGGING.md` and `SHIP_CRITERIA.md` do not exist.
- README badge says 129 tests, actual is 132.

---

## P0 - Safety and credibility blockers

### P0.1 Remove rejected archive sources from the index (Blocker) - START HERE

> **Status:** done in `fix/audit-p0-safety`.
> Parser allowlist, `.dockerignore` exclusion, regression tests, and a rebuilt 133-point index with zero archive points.

**What is wrong, in plain English**

- The ingester scans every PDF anywhere under `data/raw`.
- That includes the `data/raw/_archive/` folder.
- The repo's own `SCOPE.md` and provenance rules say the files in that folder are rejected sources.
- The deployed demo index therefore contains 45 chunks that the project says it does not use.
- The Docker image can also ship those files, because `.dockerignore` does not exclude them.
- The eval snapshot is clean, but the demo index is not, so the headline claims and the live demo do not share one corpus.

**Where the bug is**

- `src/ingest/document_parser.py:15` uses `Path(PDF_path).glob("**/*.pdf")`, which matches `_archive`.
- `.dockerignore` has no `data/raw/_archive/` entry.
- `src/ingest/ingestion_pipeline.py:29` points the default corpus at `data/raw`.

**What to fix**

1. In `src/ingest/document_parser.py`, stop ingesting anything inside `_archive`.
   - Smallest correct patch: skip paths where `"_archive"` is one of `pdf_file.parts`.
   - Stronger patch, preferred: replace the free-for-all glob with an explicit allowlist of approved PDF paths, so a newly dropped rejected file can never sneak in.
2. Add `data/raw/_archive/` to `.dockerignore`.
3. Add a regression test that asserts no archive `doc_id` is returned by `load_all_PDFS`.
4. Rebuild the vendored index with `uv run python scripts/run_ingest.py`.
5. Re-vendor the index with `git add -f data/qdrant_storage`.
6. Add an eval/demo parity check so the snapshot and demo index cannot silently diverge again.

**How to verify**

- Run `uv run pytest tests/ingest/ tests/retrieve/ tests/agent/ -q` and get 132+ passing.
- Query the rebuilt store and confirm the four archive doc IDs above return zero points.
- Confirm the point count drops by 45 (179 -> 134, before any other corpus changes).
- Run `docker build` or inspect the build context and confirm `_archive` is absent.

**Definition of done**

- No archive source can reach the parser, the image, or the index.
- A test fails if archive content is reintroduced.
- README and Dockerfile point counts match the rebuilt index.

---

### P0.2 Make eval a CI gate (High)

> **Status:** partial in `fix/audit-p0-safety`.
> Offline diagnostic-refusal gate, frozen-snapshot integrity check, and nonzero exit on threshold or baseline regression are in place.
> The live Ragas baseline run still needs the owner's Bedrock credentials.

**What is wrong, in plain English**

- Evals are manual.
- `run_ragas.py` prints PASS/FAIL and exits 0 either way.
- CI only runs unit tests, so a quality regression can merge green.
- Refusal correctness is the hard ship gate, but it is not automated against the frozen snapshot.

**Where**

- `src/eval/ragas/run_ragas.py` ends after logging, with no `sys.exit(1)` on failure.
- `.github/workflows/ci.yml` runs only pytest.
- `evals/guardrails/tasks/live-model-refusal/environment/chunks_v1.jsonl` is the frozen 120-chunk snapshot.
- `data/golden_set_v1.jsonl` is the 78-item golden set.
- `tests/eval/` does not exist.

**What to fix**

1. Make `run_ragas.py` exit nonzero when any threshold in `THRESHOLDS` fails.
2. Add `tests/eval/` with a deterministic refusal test over `chunks_v1.jsonl`.
   - No live model calls.
   - Assert every trap question refuses and every answerable question does not fail closed.
3. Add a Ragas baseline comparison that fails when a metric drops below the committed baseline or threshold.
   - Keep the live judge run opt-in or scheduled, not on every PR, to control cost.
4. Add `tests/eval/` to the CI pytest command.
5. Keep CI offline and deterministic for PRs.

**How to verify**

- Temporarily break a threshold in the harness and confirm CI fails.
- Restore it and confirm CI passes.
- Run the refusal test against the frozen snapshot and get 100% refusal on traps.

**Definition of done**

- A regression in refusal behavior or Ragas metrics turns CI red.
- The CI command in `AGENTS.md` and `ci.yml` matches the new test paths.

---

### P0.3 Add the FastAPI service boundary (High)

**What is wrong, in plain English**

- `fastapi` and `uvicorn` are declared dependencies, but no app exists.
- Every caller currently imports internals directly.
- There is no request validation, length limit, timeout, request ID, health check, or metrics endpoint.

**Where**

- New code under `src/service/`.
- Entry point in `scripts/run_api.py` or `src/service/main.py`.
- `src/ui/app.py` becomes an HTTP client instead of importing the graph directly.

**What to fix**

1. Add `GET /health` for liveness and `GET /ready` for index readiness.
2. Add `POST /ask` with a typed Pydantic request and response.
3. Add a maximum question length and reject empty or whitespace-only input with 422.
4. Add a per-request timeout and a request ID.
5. Add `GET /metrics` in Prometheus text format.
6. Return `503` when retrieval or generation is unavailable.
7. Keep the graph injectable so tests run without Bedrock.

**How to verify**

- Start the service locally.
- `curl` `/health`, `/ready`, `/ask`, and `/metrics`.
- Send an empty string and confirm 422.
- Send an over-length question and confirm 422.
- Run the service tests offline with a fake retriever and fake LLM.

**Definition of done**

- The Streamlit UI talks to the service, not to internals.
- All endpoints work locally and have tests.

---

### P0.4 Fix the empty-question hole (High)

> **Status:** done in `fix/audit-p0-safety`.
> Blank input routes straight to refusal, and the graph test proves retrieval and generation never run.

**What is wrong, in plain English**

- `screen_question("")` returns `allowed=True`.
- The graph then runs retrieval on an empty query.
- Qdrant returns nearest neighbors anyway, so the pipeline retrieves 5 chunks and may answer.
- The guardrail docstring claims empty retrieval fails closed, but empty input does not produce empty retrieval.

**Where**

- `src/agent/guardrail.py:101` explicitly allows empty input.
- `src/agent/graph.py:50` calls the retriever with whatever string it got.

**What to fix**

- Decide where the boundary guard belongs.
- Preferred: reject empty or whitespace-only input at the API boundary (422) and add a defense-in-depth graph check before retrieval.
- Add a graph test that an empty question never calls the retriever and returns a refusal.

**How to verify**

- Unit test: `screen_question("   ")` is rejected or the graph refuses before retrieval.
- API test: `POST /ask` with `""` returns 422.
- Test proves the retriever is not called.

**Definition of done**

- Empty input cannot reach retrieval through any supported entry point.

---

### P0.5 Add a retrieval relevance gate (High)

**What is wrong, in plain English**

- A question like "What is the capital of France?" retrieves 5 plausible-looking dental chunks.
- There is no score threshold, so the model is the only thing standing between an off-topic question and a confident answer.
- Out-of-corpus refusal is currently model behavior, not enforced code behavior.

**Where**

- `src/retrieve/hybrid.py` and `src/retrieve/base.py`.
- `src/agent/graph.py` after retrieval.

**What to fix**

1. Inspect the score scale returned by dense, sparse, and RRF fusion.
2. Add an explicit, documented relevance threshold.
3. Fail closed when the best fused score is below the threshold.
4. Measure the threshold on the golden set plus a negative set so it does not over-refuse.
5. Record the chosen threshold in `DECISIONS/`.

**How to verify**

- Off-corpus questions return `Refusal(insufficient_context)` deterministically.
- Golden answerable questions still answer at the current rate.
- A test covers both sides of the threshold.

**Definition of done**

- Off-topic refusal no longer depends on the LLM.

---

## P1 - Production readiness

### P1.1 Tracing, metrics, cost, and latency (High)

- Add LangSmith tracing only if it is actually configured and tested, or remove the README claim.
- Add per-node latency, token counts, cost, and request IDs.
- Add `/metrics` counters and histograms.
- Add structured logs with a request ID.
- Verify with one local request and one dashboard or log trace.

### P1.2 Fix the CLI Bedrock token path (High)

- `scripts/run_agent.py:56` builds `ChatBedrockConverse` without `bedrock_api_key`.
- `src/ui/app.py:175` passes `bedrock_api_key=os.getenv("AWS_BEARER_TOKEN_BEDROCK")`.
- Make the CLI use the same explicit token path.
- Or centralize model construction in one helper used by CLI, UI, eval, and service.
- Verify by running the CLI against Bedrock with the bearer token set.

### P1.3 Timeouts, retries, and circuit breaker (Medium)

- Add explicit timeouts to every network call.
- Add bounded retries with backoff for transient failures.
- Add a circuit breaker for provider outages.
- Map failures to `503 service_unavailable`.
- Verify with a forced timeout and a forced 5xx from a fake client.

### P1.4 Auth, rate limits, and abuse controls (High once an API exists)

- Add API key or bearer auth.
- Add per-client rate limiting.
- Add request size limits.
- Add basic abuse logging with redaction.
- Verify with a missing key, a valid key, and an over-limit client.

### P1.5 Reproducible deploy (High)

- Pin `requirements.txt` fully, or install from `uv.lock`.
- Add a non-root `USER` to the Dockerfile.
- Add a `HEALTHCHECK`.
- Add a container publish workflow.
- Verify a clean build, a non-root process, and a passing health check.

### P1.6 Index versioning and atomic swap (Medium)

- Replace bare `0..n` point IDs with stable IDs.
- Add an index manifest with corpus hash, source list, point count, and build time.
- Build into a new collection and swap atomically.
- Add backup and restore steps.
- Verify a rollback to the previous collection.

### P1.7 Log redaction and retention (Medium)

- Stop logging raw questions at INFO.
- Define a retention policy.
- Redact identifiers and free text where required.
- Verify logs contain no raw patient-style question text.

### P1.8 Provenance enforcement in code (Blocker companion to P0.1)

- Add a source allowlist with license metadata.
- Enforce the allowlist at ingest time.
- Ensure NHS-derived output carries OGL attribution.
- Verify a rejected source fails ingest and a missing attribution fails a test.

---

## P2 - Engineering hygiene

### P2.1 Eval breadth

- Add dense vs sparse vs hybrid attribution on the golden set.
- Add retrieval recall and MRR by retriever.
- Keep the Harness task evidence fresh.

### P2.2 CI quality gates

- Add `ruff` lint.
- Add `mypy` or `pyright` type checking.
- Add coverage with a floor.
- Add dependency audit, secret scanning, Dependabot, and image scanning.
- Keep triggers, runners, and action versions unchanged without human approval.

### P2.3 Remove dead code and unused dependencies

- Delete or repair `src/ui/gradio_app.py`.
- Remove unused dependencies from `pyproject.toml` and `requirements.txt`.
- Verify the app still runs and tests still pass.

### P2.4 Docs drift

- Fix the README test badge (129 -> 132).
- Reconcile chunk and point counts across README, Dockerfile, and the rebuilt index.
- Add the missing `LOGGING.md` and `SHIP_CRITERIA.md`, or remove the references.
- Remove or implement the LangSmith tracing claim.
- Verify every number in the README against a command that produces it.

### P2.5 Load testing and SLOs

- Add a load test for `/ask`.
- Define p95 latency and error-rate SLOs.
- Add alerts that map to those SLOs.
- Verify the load test result against the stated SLO.

---

## Suggested order

1. P0.1 - remove archive sources and rebuild.
2. P0.4 - empty input guard.
3. P0.5 - relevance gate.
4. P0.2 - eval CI gate.
5. P0.3 - FastAPI service.
6. P1.1 and P1.2 - observability and CLI token.
7. P1.3 to P1.8 - reliability, auth, deploy, index, logging, provenance.
8. P2 - cleanup, breadth, and SLOs.

## Why this order

- P0.1 makes the corpus match the repo's own stated scope.
- P0.4 and P0.5 close the two refusal holes that the safety claims depend on.
- P0.2 makes those safety claims enforceable in CI.
- P0.3 gives every later production feature a boundary to attach to.
- P1 and P2 only make sense once the safety and service foundation is true.
