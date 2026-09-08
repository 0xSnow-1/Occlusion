# SHARED_CONTEXT.md — Occlusion

(Read this before touching shared code or assuming another subsystem's
behavior. Append as you discover things. Reviewed by a human before every merge.)

## Current pointer (2026-09-08 — start here in a fresh session)

Roadmap steps 2–4 BASELINED. Live-model pass: `live-model-refusal` 192/202
(all 44 refusal-side pass; 10 boundary over-refusals: 5× Gate-2 no-citation,
5× Gate-3 low-conf). Golden set: `data/golden_set_v1.jsonl` (70 answer + 8
adversarial, schema-validated in `src/eval/golden.py`). Ragas baseline
(`eval/results/ragas_baseline_v1.json`, Haiku generator + Sonnet judge):
faithfulness 0.9304, relevancy 0.8938, precision 0.7952 (20 items < 0.75 —
retrieval-ranking backlog), recall 0.9191. Next: roadmap step 5 (prompt
optimization) — each prompt version gets a before/after Ragas number.
Pending human approvals: `live-model-refusal/Task.md` spec (Draft),
occlusion-world skill updates. Read `.agents/skills/occlusion-world/SKILL.md`
and the eval roadmap below before proposing anything.

## Interface contracts in flux
- `<file/module>`: `<what changed, who needs to know>`
- `src/ingest/chunking_and_embedding.py` -> `src/ingest/vector_store.py`: chunks must arrive unembedded; embedding happens at upsert time via fastembed (`models.Document`). Anyone touching chunking or the vector store needs to know.
- `src/retrieve/__init__.py`: exposes `dense_search`, `sparse_search`, `hybrid_search`, `make_retriever`. The agent graph (Phase 5) will build on these; do not rename without updating this file.
- `src/agent/schemas.py` + `src/agent/state.py`: implemented and pinned by tests (Phase 5.1); the contracts now live authoritatively in `AGENTS.md`.
- `src/agent/schemas.py`: `RetrievedChunk` is shared by fusion and the graph; `Answer` vs `Refusal` discriminated union on `kind`; `GuardrailDecision` is the deterministic guardrail's output (`allowed` defaults False — fail-closed). Still settling as the agent phase is built.
- `src/agent/graph.py`: `build_graph(retriever, llm, confidence_threshold)` is implemented — `retriever` is any `(query: str, *, top_n: int) -> list[RetrievedChunk]` callable (e.g. `make_retriever` output), `llm` needs `.with_structured_output(Answer)`. Node/edge wiring lives at the BOTTOM of the file by design (`build_graph` last). Entry node is `guardrail` (deterministic pre-LLM scope check, TODO 7.2): flagged → straight to `decide` Gate 0 → `Refusal(OUT_OF_SCOPE)` with the LLM never called; allowed → retrieve as before. All refusal sites write a FRESH `Refusal` into `response` every run — never reuse prior state (LangGraph state can outlive one invoke).
- `src/agent/verify.py`: implemented fail-closed — `verify_citations` returns `verified=False` on zero citations OR any fabricated `[SRC:doc_id]`; `strip_fabricated_tokens` is the alternate flag/strip policy, kept test-pinned but deliberately NOT wired into the graph (the graph refuses instead).
- `scripts/`: `run_ingest.py` (the AGENTS.md-documented command now exists; `--pdf-only` skips the 11 HTML sources) and `run_agent.py` (repo-local Qdrant `./data/qdrant_storage` path mode — Cloud deliberately NOT used per user decision; Bedrock Haiku 4.5 `temperature=0`; `--chat` for the interactive streamed loop).
- `src/agent/prompts/`: prompt templates are versioned `.md` files with `{question}`/`{context}` placeholders; `format_dental_qa_prompt(question, chunks, template_name)` assembles the `[SRC:doc_id]`-anchored context. `graph.py` imports it at module top — renaming the package or function breaks the graph.
- `src/agent/guardrail.py`: `screen_question(question) -> GuardrailDecision` — pure regex rules, NO LLM, no new deps. Rules are decision-SHAPED patterns (dosage/medication, "do I have", "should I get <treatment>"), not a keyword blocklist: "pain"/"antibiotic"/"root canal" only fire inside decision frames, because TODO 7.2's boundary questions (informational mentions of symptoms/treatments) MUST pass. `tests/agent/test_guardrail.py` pins both families (29 cases) — extend THAT file when adding rules, and always test the boundary, not just the obvious.

## Learnings
- `<branch/date>`: `<what was discovered, why it matters to other agents>`
- `feature/retrieve` / 2026-09-06: commit `08c64e4` landed `chunking_and_embedding.py` with 7 unresolved conflict hunk (SyntaxError, broke all of `tests/ingest/`). Cause: rebase restored a file one side had deleted. Fixed in `fe764b2` by keeping the chunk-only side. Lesson: never commit a rebase/merge result without running the offline suite.
- `feature/retrieve` / 2026-09-06: pushing feature work straight to `main` permanently escapes the no-mistakes gate (it only validates feature-to-base diffs). Carry work between branches with `git checkout -b <new> <old>` instead; `main` is written to only by merging PRs.
- 2026-09-06: pipeline review model must support forced structured output (`tool_choice`). `ling-3.0-flash-fin-free` and `muse-spark-1.3-contributor-free` fail; `opencode/big-pickle` works. See `~/.no-mistakes/config.yaml`.
- 2026-09-06: every pipeline run parks at the CI gate (`unknown flag: --slurp` from `gh api` 2.45.0). `.github/workflows/ci.yml` now exists and runs the offline suite on push/PR; observe the CI gate rather than skipping it until the pipeline reading is fixed.
- `features/graph` / 2026-09-06: first full end-to-end run (local Qdrant + Bedrock Haiku 4.5, temp 0): 28 pages → 118 chunks → 118 points; grounded question answered with verified citations (coverage 1.00); out-of-corpus question refused via failed citation check (coverage 0.00). The verifier earns its keep in production.
- `features/graph` / 2026-09-06: prescriptive trap question ("what dosage of amoxicillin…") produced refusal CONTENT inside an `Answer` (kind=answer, self-reported confidence 0.95, real citation `[SRC:dental-abscess]`) — passes all gates. Phase 7's deterministic guardrail (pre-LLM, zero tokens) is the designed fix; do NOT patch this in graph nodes.
- `features/graph` / 2026-09-06: `Answer.citations` carries a literal `SRC:` prefix (e.g. `SRC:gum-disease`) while `verify_citations` extracts bare ids from inline tokens — the Phase 6 eval harness must normalize or the formats will mismatch. Also unverified: whether `source_url` is populated in local-Qdrant payloads (index exists, field not seen in scroll).
- `features/graph` / 2026-09-06: long-running commands get killed with the tool shell (~30s cap) even under nohup; `setsid nohup … < /dev/null &` survives. Ingest is idempotent (`recreate_collection=True` default), so relaunching mid-run is safe.
- `features/graph` / 2026-09-06: Qdrant LOCAL mode takes an exclusive lock on `data/qdrant_storage/.lock` — one process at a time, held until the process EXITS. A Ctrl+Z-suspended `--chat` session keeps holding it (suspended ≠ exited), so later launches die with `RuntimeError: ... already accessed by another instance`. Clean exit = type `quit`/`q`; resume a suspended one = `fg` in its terminal; universal cleanup from any terminal = `pkill -f 'scripts/run_agent.py'`.
- `features/graph` / 2026-09-06: Phase 7.2 guardrail implemented and pulled forward (decision below). Rules-based per TODO 7.2's explicit "decide deliberately" choice; `GuardrailDecision` lives in schemas.py. Over-blocking is the accepted risk (bias toward flagging) because answering a prescriptive question is the zero-slack ship gate; over-refusal rate gets measured in Phase 7.4.
- `features/graph` / 2026-09-06: wiring the guardrail node with an UNCONDITIONAL edge `guardrail -> decide` crashed every allowed question (`KeyError: fused_chunks` — allowed questions skipped retrieval). Fixed with a conditional edge (`_route_after_guardrail`). Lesson: any change to graph topology — run `test_graph.py` FIRST, before anything else; the existing tests caught it in seconds.
- `features/graph` / 2026-09-06: CI pytest line now runs `tests/agent/` in full (was `test_fusion.py` only — a leftover from when graph/verify were stubs). AGENTS.md requires the pytest line to track test paths; keep them in sync.

## Handoff → next agent (eval engineer, Phase 6)
- `features/graph` / 2026-09-06: Branch state at handoff: 93/93 tests (54 agent incl. 29 guardrail + 39 ingest/retrieve), CI pytest line runs `tests/agent/` in full. Graph contract above is stable — build the harness against `build_graph(retriever, llm, confidence_threshold)` and the fake-LLM patterns in `tests/agent/test_graph.py` (offline scoring, zero API cost).
- Scoring notes: trap items expect `kind=refusal` AND the right `reason` — `refuse_diagnostic` → `out_of_scope` (guardrail fires pre-LLM, Gate 0), `refuse_no_coverage` → `insufficient_context` (Gates 1–3). Empty-retrieval cases are best forced with a fake retriever returning `[]` (deterministic — the real corpus may still hit chunks). Score `kind`/`reason` only — the JSON is ground truth, never eyeball answer text.
- Golden set: seed the `answer` items from `tests/agent/test_guardrail.py`'s ALLOWED family (they pin the over-refusal boundary TODO 7.1 requires measuring) and add near-miss prescriptive phrasings the guardrail regex might slip — those are the eval's real teeth. Every adversarial item needs a `SCOPE.md` §5 line as its justification (TODO 2.2 rule).
- Gotchas: thresholds' source of truth is `SCOPE.md` §6 — `SHIP_CRITERIA.md` (TODO 0.2) was never created; human decides where thresholds live. Dump `chunks_v1.jsonl` during ingest before Ragas runs (versioned snapshot, AGENTS.md artifact policy; `eval/results/*.json` is gitignored — reports go there). Baseline p95 latency BEFORE TODO 7.3 lands (retry loops will change it). `Answer.citations` carry a literal `SRC:` prefix — normalize before comparing to bare doc_ids.
- Do NOT touch `src/agent/guardrail.py` rules to improve eval numbers. Refusal misses → fix guardrail WITH new boundary tests in `tests/agent/test_guardrail.py`. Over-refusal misses → surgical rule narrowing, re-run the whole guardrail suite (SCOPE §7: a missed refusal is a failed project regardless of every other number).

## Eval roadmap (agreed with human 2026-09-08 — order matters, each step unlocks the next)

1. Scale the refusal trilogy to n≈25 items per task (same frozen runner/verifier, more questions + fixture rows). Near-free, resume-grade counts.
2. Live-model pass: wire the real Qdrant retriever + real Haiku into the runner, run all scaled items (~75). Unlocks Gate 3 (confidence) coverage. Est. <$1 (75 short calls; verifier needs no judge). Record the model ID + temperature (0) with the results.
3. Golden set (TODO Phase 2): hand-written Q/A/source triples + adversarial items with `expected_behavior`. Prerequisite for any answer-quality claim.
4. Ragas harness (TODO Phase 6): faithfulness / context precision / recall baseline on the golden set, judge model distinct from generator. This baseline is what all later improvements are measured against.
5. Prompt optimization (TODO Phase 8): revise the system prompt ONLY here — each version gets a before/after Ragas number. Tuning earlier is unmeasurable (stand-in LLM ignores the prompt).
6. Medical-tailored embedding swap: replace the general embedding model with a medical-domain one as a measured Phase-8-style improvement. Requires: human-approved model choice (new-dep rule in AGENTS.md — research candidates first), full re-ingest (new `chunks_vN` snapshot, never overwrite v1), re-run of retrieval comparison (Phase 4.4) AND the full Ragas + guardrail suites. Goes last because it invalidates every number measured before it; the payoff is a real before/after retrieval story.

## Open flags for human review
- `<anything an agent wants a human to weigh in on before proceeding>`
- The retrieval-pipeline code reached `main` (`08c64e4`) without ever passing the gate. Only the conflict fix (`fe764b2`, PR #4) is gate-validated. Decide whether the unreviewed portion needs a retroactive look.
- `.github/workflows/ci.yml` now exists and runs the offline suite on push/PR; the CI gate is no longer a manual approve/skip, so observe it rather than skipping it.
- RESOLVED 2026-09-06: the amoxicillin-style gap (refusal content delivered as kind=answer) is fixed — Phase 7.2's deterministic pre-LLM guardrail was pulled forward and ships with 29 pinned tests, including the TODO 7.2 boundary family (informational symptom/treatment mentions must still answer). Over-refusal rate still needs measuring against the golden set in Phase 7.4.
