# SHARED_CONTEXT.md — Occlusion

(Read this before touching shared code or assuming another subsystem's
behavior. Append as you discover things. Reviewed by a human before every merge.)

## Current pointer (2026-09-08 — start here in a fresh session)

Roadmap steps 2–4 BASELINED. Live-model pass: `live-model-refusal` 192/202
(all 44 refusal-side pass; 10 boundary over-refusals: 5× Gate-2 no-citation,
5× Gate-3 low-conf). Golden set: `data/golden_set_v1.jsonl` (70 answer + 8
adversarial, schema-validated in `src/eval/golden.py`). Ragas baseline
(`src/eval/ragas/results/ragas_baseline_v1.json`, Haiku generator + Sonnet judge):
faithfulness 0.9304, relevancy 0.8938, precision 0.7952 (20 items < 0.75 —
retrieval-ranking backlog), recall 0.9191. Next: roadmap step 5 (prompt
optimization) — each prompt version gets a before/after Ragas number.
Approved by human 2026-09-08: `live-model-refusal/Task.md` spec (Draft →
Approved, oracle baseline 192/202, job `2026-09-08__07-51-31`) and the
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
- `feature/retrieve` / 2026-09-06: commit `08c64e4` landed `chunking_and_embedding.py` with 7 unresolved conflict hunks (SyntaxError, broke all of `tests/ingest/`). Cause: rebase restored a file one side had deleted. Fixed in `fe764b2` by keeping the chunk-only side. Lesson: never commit a rebase/merge result without running the offline suite.
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
- Gotchas: thresholds' source of truth is `SCOPE.md` §6 — `SHIP_CRITERIA.md` (TODO 0.2) was never created; human decides where thresholds live. Ragas code + reports live together in `src/eval/ragas/` (runner, vertexai-shim, `results/` — reports are versioned and committable, NOT gitignored, per human decision 2026-09-08). `Answer.citations` may be bare doc_ids or carry a `SRC:` prefix — always normalize before comparing. Baseline p95 latency BEFORE TODO 7.3 lands (retry loops will change it).
- Do NOT touch `src/agent/guardrail.py` rules to improve eval numbers. Refusal misses → fix guardrail WITH new boundary tests in `tests/agent/test_guardrail.py`. Over-refusal misses → surgical rule narrowing, re-run the whole guardrail suite (SCOPE §7: a missed refusal is a failed project regardless of every other number).

## Eval roadmap (agreed with human 2026-09-08 — order matters, each step unlocks the next)

1. Scale the refusal trilogy to n≈25 items per task (same frozen runner/verifier, more questions + fixture rows). Near-free, resume-grade counts.
2. Live-model pass: wire the real Qdrant retriever + real Haiku into the runner, run all scaled items (~75). Unlocks Gate 3 (confidence) coverage. Est. <$1 (75 short calls; verifier needs no judge). Record the model ID + temperature (0) with the results.
3. Golden set (TODO Phase 2): hand-written Q/A/source triples + adversarial items with `expected_behavior`. Prerequisite for any answer-quality claim.
4. Ragas harness (TODO Phase 6): faithfulness / context precision / recall baseline on the golden set, judge model distinct from generator. This baseline is what all later improvements are measured against.
5. Prompt optimization (TODO Phase 8): revise the system prompt ONLY here — each version gets a before/after Ragas number. Tuning earlier is unmeasurable (stand-in LLM ignores the prompt).
6. Medical-tailored embedding swap: replace the general embedding model with a medical-domain one as a measured Phase-8-style improvement. Requires: human-approved model choice (new-dep rule in AGENTS.md — research candidates first), full re-ingest (new `chunks_vN` snapshot, never overwrite v1), re-run of retrieval comparison (Phase 4.4) AND the full Ragas + guardrail suites. Goes last because it invalidates every number measured before it; the payoff is a real before/after retrieval story.

## Subagent audit 2026-09-09 (3 parallel investigators, read-only)

- Corpus gaps (verified by grep over frozen 120-chunk snapshot): B6 (post-filling diet), B10 (baby-tooth loss timing), B18 (braces + food) have ZERO answer-bearing chunks. B21 same (no "sealant" string anywhere). System refusal on these is CORRECT behavior — fail-closed working as designed. Eval-side fix needed: reclassify as no-coverage or add SCOPE-legal source material. No prompt/graph change can legitimately flip them.
- Verifier/prompt format mismatch (real, code-fixable): `verify.py:41` reads inline `[SRC:]` tokens only, ignores `Answer.citations`; prompt few-shots teach prefixed `citations: ["SRC:..."]` while tests expect bare IDs; no normalization (case/whitespace/`SRC:`-prefix) on either side. Fix: one canonical format + normalize + state which channel counts.
- Few-shot fabrication risk: v2.3 examples flash IDs (`toothache`, `health-info`) absent from most retrievals — model copying an example ID fails as fabricated. Example 3 sits near the amoxicillin-dosage trap family; needs a trap-side test to prove the guardrail still catches it.
- B23 is a rank-cut victim, genuinely fixable via retrieval: both answer halves exist in-corpus but the precise chunk is 2/120 and loses the top_n=5 cut to generic bleed chunks. Candidate for top_n widening or TODO 4.3 rerank.
- Hygiene: 0-byte `src/agent/prompts.py` shadows the `prompts/` package (masked today by `__pycache__` order; breaks under other importers). Delete it.
- Eval contamination (committed then fixed): B5 was briefly both a prompt example and an eval item; swapped to a non-eval boundary question. Rule restated: eval questions NEVER enter the prompt; B12's flip surviving decon is the clean signal.
- Probe variance warning: B16/B25 flipped coverage 1.00 → 0.00 between identical temp-0 runs. Single-probe numbers are untrustworthy on boundary items; use best-of-3 before claiming.
- Repair loop (bounded 1-retry in generate node) was implemented, probed (0 conversions — model answers from head twice), and REVERTED. Graph is back to one-line v2.3 swap. Do not re-add without new evidence.
- `test_low_confidence_fails_closed` pins current Gate-3 semantics (verified + conf 0.2 → Refusal). Coverage-based acceptance CONTRADICTS it — needs human decision + spec-test change, never a silent edit.

## Latency & cost baseline (2026-09-10, pre-deploy)

- Method: 4 corpus-grounded replacement items (RB6/RB10/RB18/RB21, the B6/B10/B18/B21 rebuilds) × 3 trials = 12 timed `graph.invoke` calls over the production path (repo-local Qdrant `./data/qdrant_storage`, 120 points post re-ingest, hybrid retriever, Bedrock Haiku 4.5 @ temp 0, threshold 0.7). Probe script in `/tmp/latency_probe/lat.py` (NOT committed — rerun from scratch for the next measurement). 12/12 `kind=answer`, zero generation failures.
- Sorted seconds: 2.39, 2.39, 2.51, 2.67, 2.82, 3.44, 3.58, 3.97, 4.68, 4.82, 4.82, 4.95. **p50 ≈ 3.5s, p95 ≈ 4.9s.**
- Gate verdict: SCOPE §6 wants P95 < 3s — MISSED on local hardware. Driver is Bedrock round-trip (retrieval is ms; two-citation RB21 answers cluster ~4.8s). Deploy adds cold start, never subtracts — staging MUST re-measure before any ship claim. Recalibrating the 3s target is a human decision (same rule as Gate-3); record the why, never silent-edit.
- Cost: ~$1 per 75-call live pass (prior `live-model-refusal` evidence) → this batch ≈ $0.15 → **~$0.01/query** README estimate. Tokens-per-call were NOT captured (probe logged latency/kind only) — next measurement should record usage metadata for a real cost table.
- Image verification (2026-09-10): `docker build -t occlusion-space .` succeeded (12GB, 4.11GB content); baked index holds **136 points, not 120** — the CDC `about` page served its real content at build time (17 chunks) instead of the "Access Denied" stub frozen in `chunks_v1.jsonl` (1 chunk). All other doc_ids match exactly. Superset, so demo-safe, but the Space index ≠ the eval snapshot — eval numbers were measured on 120. Container boot with `--env-file .env`: `/_stcore/health` 200, zero tracebacks. Lesson: live-HTML sources make build-time indexes non-deterministic; if eval-demo parity ever matters, vendor the HTML snapshot instead of fetching at build.

## Open flags for human review
- `<anything an agent wants a human to weigh in on before proceeding>`
- The retrieval-pipeline code reached `main` (`08c64e4`) without ever passing the gate. Only the conflict fix (`fe764b2`, PR #4) is gate-validated. Decide whether the unreviewed portion needs a retroactive look.
- `.github/workflows/ci.yml` now exists and runs the offline suite on push/PR; the CI gate is no longer a manual approve/skip, so observe it rather than skipping it.
- RESOLVED 2026-09-06: the amoxicillin-style gap (refusal content delivered as kind=answer) is fixed — Phase 7.2's deterministic pre-LLM guardrail was pulled forward and ships with 29 pinned tests, including the TODO 7.2 boundary family (informational symptom/treatment mentions must still answer). Over-refusal rate still needs measuring against the golden set in Phase 7.4.

## V2 pointer (2026-09-11 — receptionist pivot, supersedes Path B draft above)

Spec: `SPEC_V2.md`. Q&A + guardrail + Gates 0-3 frozen; new parallel `booking` node via
`src/agent/tools.py` on real cal.com API v2 (slots + booking, `CAL_API_KEY` in `.env` only).
Owner provides real cal.com account (username + visit types + timezone). Insurance dropped,
no fake slots ever, booking failure degrades to callback list. Next: tools + state + node
test-first per SPEC_V2 §9, then callback list + scoreboard.

## V2 step 1 done (2026-09-11 — booking tools foundation, mocked HTTP only)
- `src/agent/tools.py` (new): stdlib `urllib` only, zero new deps (pyproject untouched).
- Base `https://api.cal.com/v2`, headers `Authorization: Bearer` + `cal-api-version: 2024-08-13`, 10 s timeout.
- Key read from env at call time; missing key returns `[]` / `ok=False` with no network call.
- Never raises into the graph; never logs the key or headers (test-pinned via `caplog`).
- Defensive parsing: event `length`/`lengthInMinutes`/`duration_min` variants; slots dict-of-lists or flat list; booking `uid`/`id`, `startTime`/`start`.
- `schemas.py`: `EventType`/`Slot`/`BookingIntent`/`BookingReceipt`/`Contact` verbatim per SPEC_V2 §4.
- `state.py`: 4 new fields, overwrite only, no reducers.
- Tests: `tests/agent/test_tools.py` 9 tests mocked; suite 109/109 green (was 100).
- Graph untouched: no booking node yet, Q&A path byte-identical. Next: booking node + `test_booking_graph.py`.

## V2 step 2 done (2026-09-11 — booking node + routing, mocked tools only)
- `src/agent/booking_intent.py` (new): deterministic regex, no LLM. Strict AND rule (booking word + day hint or visit word) so Q&A like "available services" or "what is a filling?" never misroutes. Strong phrases ("book an appointment") always count.
- `graph.py`: guardrail node also writes fresh `booking_intent`; `_route_after_guardrail` returns booking when allowed + wants_booking (flagged still wins). New `booking` node -> END, never calls LLM or retrieval. `build_graph` takes optional injectable tool fns (defaults to real tools.py) so existing 2-arg calls are untouched.
- Booking node: event_slug substring match else first event; ISO time scraped from question + contact name/email triggers create_booking; slot offer lists real slots; every failure is ok=False + callback-worded Refusal, never a fake UID.
- Tests: `tests/agent/test_booking_graph.py` 4 tests (skip LLM/retrieval, book with contact, double-book callback, Q&A unchanged). Suite 113/113 green; test_graph/guardrail/verify unmodified.
- Next: callback list + scoreboard (SPEC_V2 §8).

## V2 step 3 done (2026-09-11 — callback list + scoreboard + UI, no live calls)
- `src/agent/callbacks.py` (new): `append_callback`/`read_callbacks` over `data/callbacks.jsonl` (gitignored); stores name/phone + question_hash (never raw text) + reason + UTC timestamp; logs reason only, never PHI. 5 tests.
- `src/eval/deflection.py` (new): pure `summarize_runs` over counts-only records (handled/booked/callback + p50/p95 + $/day at 500). 3 tests in tests/agent (keeps CI paths unchanged).
- `src/ui/app.py`: booking stage in status; slot buttons (display in CAL_TIMEZONE, wire stays UTC ISO); in-chat name/email confirm; receipt success view; refusal callback form; sidebar scoreboard + staff table + CSV; counts-only run log. Syntax-checked; streamlit not in offline suite.
- Suite 121/121 green. `.gitignore` gains `data/callbacks.jsonl` + `eval/results/`.
- Still open (need owner): live cal.com check (§9: slots fetch, book-then-cancel, past-time) + pyproject forbidden-dep removal (§10, needs approval) + Harbor/Ragas re-runs.

## Owner cal.com facts (2026-09-12 — from local .env + user message, secrets excluded)
- `.env` holds `CAL_URL=https://cal.com/ahmed-gamal-7acpyz/doctor` (username candidate `ahmed-gamal-7acpyz`, event slug `doctor`). No `CAL_USERNAME` / `CAL_API_KEY` / `CAL_TIMEZONE` keys in `.env` yet.
- User-reported local time 12:00am; commit tz is +0800. IANA clinic timezone still UNCONFIRMED — do not guess (candidates differ: Asia/Manila vs Africa/Cairo). Ask before the live check.
- 2026-09-12: user confirmed clinic timezone `Asia/Manila` (they typed "Maila", read as Manila typo; matches +0800 commits). Still to add to `.env`: `CAL_TIMEZONE=Asia/Manila`, `CAL_USERNAME=ahmed-gamal-7acpyz`.
- 2026-09-12: user said key saved but `.env` has NO `CAL_API_KEY` line yet (checked by name). Exact line needed: `CAL_API_KEY=cal_live_...` with no spaces around `=`. Note: existing `.env` lines with spaces around `=` break shell sourcing — keep new lines spaceless.
- Cancel endpoint for the live check confirmed (docs): `POST /v2/bookings/{uid}/cancel` + `{"cancellationReason": ...}` with owner Bearer key.
- `CAL_API_KEY` value never enters repo files, logs, or SHARED_CONTEXT. Live check stays blocked until key + IANA tz + test event type are confirmed.

## How to obtain cal.com facts (researched 2026-09-12, cal.com API v2 docs)
- API key: log in at cal.com → Settings → Security (API keys; some accounts show Settings → Developer → API keys) → Create new API key → copy the `cal_live_...` value (shown once). Paste into local `.env` as `CAL_API_KEY=...`. Test keys start `cal_`, live keys `cal_live_`. Rate limit 120 req/min on API-key tier.
- Username + event slug: read off the booking link `cal.com/<username>/<slug>`. Event Type ID: open the event's settings, numbers between slashes in the URL bar.
- Timezone: "12:00am" is a time, not a zone — need the IANA city name (e.g. `Asia/Manila`, `Africa/Cairo`). Find it in cal.com → Settings → General → Timezone, or match the city in the phone's Date & Time settings.
