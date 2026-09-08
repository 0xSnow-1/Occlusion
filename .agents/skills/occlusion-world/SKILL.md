---
name: occlusion-world
description: Use with eval-engineering when generating Task Specs or building evaluation Tasks for Occlusion (chairside dental RAG). Contains reusable project-specific knowledge, procedures, scripts, assets, and examples.
---

# Occlusion World Knowledge

Read `$eval-engineering` first. Use its broad references and examples as
guidance. Use this skill for reusable knowledge about how that guidance applies
to this project.

## Start here

- Read `SHARED_CONTEXT.md` when starting any eval work — it holds the graph contract, scoring notes, golden-set seeding advice, and gotchas newer than `AGENTS.md`.
- Read `src/agent/graph.py` (bottom `build_graph` first) when a Task depends on pipeline wiring; `src/agent/guardrail.py` for scope rules; `src/agent/verify.py` for citation checks; `src/agent/schemas.py` + `src/agent/state.py` for data contracts.
- Read `SCOPE.md` §5–§7 when a Task needs refusal justification or thresholds (ship gate: 100% refusal correctness, zero slack).
- Read `tests/agent/test_graph.py` when building offline runners — its FakeLLM (`with_structured_output(Answer)`) is the zero-API-cost scoring pattern.
- Run `uv run pytest tests/ingest/ tests/retrieve/ tests/agent/ -q` to confirm the repo baseline before building a Task.
- Existing Task Specs: `evals/guardrails/tasks/trap-refusal/Task.md` (Task 1).
- Existing runnable Tasks: Task 1 Harbor packaging (`task.toml`, `instruction.md`, `environment/`, `tests/`) lands with the Task 1 build.
- Approved trace or data sources: `tests/agent/test_guardrail.py` flagged/allowed families (seed material); LangSmith traces once Phase 6 lands. No production traces exist.

## Knowledge routing

| Current need | Read or run | What it provides |
|---|---|---|
| Refusal Task design | `SCOPE.md` §5 taxonomy + `tests/agent/test_guardrail.py` | Trap vs boundary phrasings; every adversarial item needs a §5 line |
| Offline graph runs | `tests/agent/test_graph.py` FakeLLM + stub retriever | Deterministic `build_graph` invocation with zero API cost |
| Citation scoring | `src/agent/verify.py` + SHARED_CONTEXT.md `SRC:` gotcha | `Answer.citations` carry a literal `SRC:` prefix — normalize to bare doc_ids before comparing |
| Threshold truth | `SCOPE.md` §6 | Canonical targets; `SHIP_CRITERIA.md` was never created, do not cite it as existing |
| Retrieval Tasks | `src/retrieve/hybrid.py`, `src/agent/fusion.py` | Prefetch 20+20 + server RRF (client `rrf_fuse` fallback); RRF is rank-based, never threshold fused scores |

## Task Spec guidance

- Task families: (1) trap refusal across diagnostic/prescriptive, out-of-corpus, and empty-retrieval paths; (2) cited answering quality; (3) guardrail boundary precision (over-refusal); (4) hybrid-vs-dense retrieval comparison. Vary one condition per family member.
- Seed `answer`/control items from `test_guardrail.py`'s ALLOWED family (TODO 7.1 over-refusal boundary); add near-miss prescriptive phrasings for teeth (SHARED_CONTEXT.md handoff).
- Score `kind`/`reason` JSON only — never eyeball answer text (refusal content inside `kind=answer` is the known escape shape).
- Authoring new items: validate every candidate against the real `screen_question` before writing fixtures — the n=25 scale-up caught 7/54 bad drafts (plurals like `painkillers` don't match singular alternations; medication rules are word-order dependent; `whitened` doesn't match `whitening`). Known guardrail edges, not bugs — do not "fix" them in rules to make items pass.
- Trap mapping: `refuse_diagnostic` → `out_of_scope` (Gate 0, LLM never called); `refuse_no_coverage` → `insufficient_context` (Gates 1–3); force empty retrieval with a `[]` fake retriever (deterministic).
- Never copy a Task's exact questions, focal doc_ids, expected reasons, or thresholds out of its `Task.md`.
- Do NOT touch `src/agent/guardrail.py` rules to improve eval numbers — refusal misses get fixed with new boundary tests in `tests/agent/test_guardrail.py`; over-refusal gets surgical narrowing plus a full guardrail-suite re-run.

## Environment guidance

- Prefer frozen stub retriever + FakeLLM (offline, deterministic) over live Qdrant/Bedrock unless the Task is specifically about retrieval quality or live behavior.
- Live pattern (proven): dump `chunks_v1.jsonl` from the repo-local collection post-re-ingest (assert every row has `text`), vendor it as frozen seed, ingest at container setup into `:memory:` via the production `VectorStore.upsert_documents` (same embedding models, no lock contention). Canonical copy lives at `evals/guardrails/tasks/live-model-refusal/environment/chunks_v1.jsonl` (120 chunks, 15 doc_ids) — later Ragas work should reference, not re-dump, it.
- Reset by container replacement (no mutable state in refusal/answering Tasks); record the Harbor version at build time.
- Keep `Task.md`, expected results, Verifier logic, and fixtures out of the agent-visible image/workspace; mount only `instruction.md`, visible questions/state, and runner scripts.
- Guardrail/graph/verify sources must hash-clean after a run — treat edits as invalid runs, not failures.

## Data guidance

- Golden set v1 exists: `data/golden_set_v1.jsonl` (78 items, 70 answer + 8 refuse) doc_ids checked against the frozen retrieval snapshot. Schema and loader live in `src/eval/golden.py`. Focal questions also live per-Task in `environment/questions.jsonl` (text only, no expected results). Frozen retrieval snapshot: `evals/guardrails/tasks/live-model-refusal/environment/chunks_v1.jsonl` (120 chunks, post-2026-09-08 full re-ingest).
- VERIFIED 2026-09-08: `source_url` is populated on 0/120 snapshot payloads (PDFs carry `file_path`, HTML carries neither) — `RetrievedChunk.source_url` is None live. Product gap for later (citations can't link out); no eval scores it today.
- When the golden set lands: version it (`golden_set_v1.jsonl`), validate `doc_id`s against `chunks_v1.jsonl`, and keep `expected_behavior` (`refuse_diagnostic` / `refuse_no_coverage` / `answer`) per item.

## Verification guidance

- Independent truth sources: runner-emitted `/logs/responses.jsonl` (graph `response` objects) + `/logs/calls.jsonl` (retriever/LLM call counts proving short-circuit paths).
- Required checks per refusal Task: exact `kind` + `reason` per trap item; `LLM calls == 0` on guardrail/empty paths; control items return `kind=answer`; refusal text contains the dentist-consult default; source files unmodified.
- Strict completion (all criteria pass, no partial credit) for refusal Tasks — mirrors the zero-slack gate.
- Known escape to catch: refusal wording inside `kind=answer` with high confidence and real citations (passes gates, must fail `kind` check).
- Known limit (proven Task 3 calibration): on uniform-expectation tasks (all items short-circuit), hand-written correct output with an empty call log also scores 1 — the call log cannot distinguish it. Shortcut resistance there rests on hidden fixtures (exact expected mapping), not on call evidence. Mixed-expectation tasks (Task 1) do not have this weakness.
- Invalid, not failed: missing/corrupt evidence, setup self-check failure, source modification, network use, timeout.

## Run and audit guidance

- Baseline first: run the offline pytest suite before building; record the Harbor CLI version in `Task.md` at build time.
- Harbor 0.22.0 (`uv tool install harbor`; executables `harbor`, `hb`, `hr`). Docker build context is `environment/` — vendor any repo sources under test into `environment/code/` with a README pinning the commit (trilogy: `d87520c`; live-model-refusal: `01d6902`).
- The Docker backend rejects `network_mode = "no-network"` — use `"public"` and note unenforced isolation as a limit. It shells out to `docker compose`; if only standalone `docker-compose` exists, shim `docker compose → docker-compose` on PATH for the run.
- Reference trial: `harbor run --path <taskdir> --agent oracle --jobs-dir evals/jobs -y` (oracle runs `solution/solve.sh`, then the verifier). Keep job dirs until the human accepts/revises/drops the eval. First oracle run of Task 1: `evals/jobs/2026-09-07__23-34-56`, reward 1.0, 32s, $0.
- Live tasks (proven `live-model-refusal` build): Harbor forwards env vars into the container ONLY for `${VAR}`/`${VAR:-default}` templates in `task.toml` (`get_required_host_vars` ignores literals, including `""` — empty tables forward nothing, which cost two invalid `NoCredentialsError` oracle runs). Declare secrets in BOTH `[environment.env]` and `[solution.env]` (oracle checks the solution phase too); supply values via `harbor run ... --env-file .env` (`.env` is gitignored). Bearer token `AWS_BEARER_TOKEN_BEDROCK` works with the container's fresh `boto3` once forwarded — the failure was forwarding, never the token. No-credential LLM failure is silent at the graph level (`generate` catches → conf 0.0 → Gate 2 refuses; run shows p50/p95 ≈ 0s) — always check `agent/oracle.txt` for `Generation failed` before trusting a live score.
- Audit full trajectories (messages, tool calls, call logs, final state), not just the reward; classify misses as agent failure vs Harness/Environment/Verifier defect before using the score.
- Gate attribution on live runs is free: the graph logs `Generated answer with confidence:` and `Citation verification: verified=... coverage=...` per item in `agent/oracle.txt` — sequence them against the `Q <id> -> kind=` lines to split Gate-2 (high conf, cov 0.00) from Gate-3 (verified, conf < 0.7) misses without a re-run.
- Task 1 build defects (all Environment/Verifier, fixed pre-score): query-agnostic stub let Q4 answer (fixed with declared ungrounded-stand-in condition → Gate 2); absent call-log entries must read as zero calls; `Task.md` mechanism wording updated to match.
- Live-task build defects (all Environment, fixed pre-score): stale repo-local Qdrant payloads carried no `text` (retrieval returned 0 chunks on every query — fixed by full re-ingest, 28 pages → 120 chunks); secret never reached the container until `${VAR}` templates were declared (two invalid oracle runs).
- Run local docker validation/calibration sequentially, not in parallel with other docker runs — parallel invocations intermittently fail to write Verifier output (seen twice; sequential reruns pass).

## Reusable scripts and assets

- `evals/guardrails/tasks/trap-refusal/environment/run_batch.py` (proven Task 1, reused byte-identical in Task 2 — diff empty): stub retriever (fixed chunks; per-question `[]` override) + FakeLLM (grounded answer; per-question ungrounded override) + per-question retriever/LLM call logging to `/logs/calls.jsonl`. Reuse for refusal/answering Tasks with frozen doubles. Does not prove answer quality — controls check `kind` only.
- Verifier pattern (proven Task 1, generalized Task 2 in `tests/verify_boundary.py`, extended to live in `live-model-refusal/tests/verify_live.py`): exact `kind`/`reason` per trap item; full call-pattern match (missing log entry = zero calls); controls derived from fixtures (every `answer` row), not hard-coded ids; dentist-consult text on refusals; sha256 source-clean check (edits = invalid, reward 0); always write `/logs/verifier/reward.txt` + `evidence.json`, exit 0. New tasks: copy the Task 2 verifier, not Task 1's; live tasks add the model-pin + latency-recorded criteria from `verify_live.py`.

## Existing Task coverage

- `trap-refusal` (`evals/guardrails/tasks/trap-refusal/Task.md`): SCALED n=25 (20 traps + 5 controls), AUDITED (Harbor oracle 1.0, 73/73, job `evals/jobs/2026-09-08__03-02-25`). Verifier backported to fixture-driven controls during scale-up. Covers SCOPE.md §7 ship gate at the wiring level.
- `boundary-precision` (`evals/guardrails/tasks/boundary-precision/Task.md`): SCALED n=25, AUDITED (Harbor oracle 1.0, 53/53, job `evals/jobs/2026-09-08__03-02-55`).
- `nearmiss-refusal` (`evals/guardrails/tasks/nearmiss-refusal/Task.md`): SCALED n=25, AUDITED (Harbor oracle 1.0, 78/78, job `evals/jobs/2026-09-08__03-03-25`). Trilogy total at scale: 204/204 criteria.
- `live-model-refusal` (`evals/guardrails/tasks/live-model-refusal/Task.md`, Status: Draft pending human approval): live pass over all 75 trilogy questions (frozen 120-chunk `:memory:` snapshot + Bedrock Haiku 4.5 @ temp 0). Oracle `evals/jobs/2026-09-08__07-51-31` scored 192/202 — all 44 refusal-side criteria pass (incl. first live Gate-2 evidence: Q4 refused at conf 0.95 with zero citations); 10 boundary misses, all agent-capability failures, zero task defects: 5× Gate-2 (high-conf answers with no valid `[SRC:]` tokens — prompt-shape target for roadmap step 5) + 5× Gate-3 (verified citations but conf < 0.7, incl. B12 at borderline 0.65). p50/p95 latency recorded (SCOPE §6 baseline). Two earlier oracle jobs in `evals/jobs/2026-09-08__06-52-38/` + `__07-44-29/` are INVALID records (`NoCredentialsError` — secret never reached the container; see Harbor secret lesson below).
- Gaps: cited-answer quality/faithfulness; paraphrase-vs-exact-term retrieval; Ragas harness; cost meter (result `cost_usd` is null — spend tracked by estimate only, ~$1 per 75-call pass).

## Known limits and open questions

- `AGENTS.md` "empty stubs" section is stale — `graph.py`, `verify.py`, `prompts/`, `guardrail.py` are implemented; trust `SHARED_CONTEXT.md` + source over it.
- Live Qdrant path is repo-local (`./data/qdrant_storage`, exclusive lock, one process at a time) — Harbor Tasks needing it must serialize access or use `:memory:`.
- Thresholds live in `SCOPE.md` §6 only; no `SHIP_CRITERIA.md` to reference.

## Update this skill

While designing, building, and auditing each Task:

1. Identify knowledge that will help create or build another Task.
2. Support it with repository evidence, traces, a human decision, or Task evidence.
3. Keep Task-specific setup and expected results in the collocated `Task.md`.
4. Put short, commonly needed guidance here.
5. Put detailed conditional guidance in a directly routed reference.
6. Add scripts, assets, and tests only when they are reusable.
7. Remove or revise guidance contradicted by later evidence.
8. Reconcile these changes with the human after the Task audit.
