# Roadmap

A living list. Each step is small enough to plan, build, and review on its own.
Update it between features.
Tick a step only after it is built, validated, and merged.

This file is a **thin index** over `docs/internal/TODO.md` (detailed tasks, inputs, pitfalls, and verify gates live there).
Do not duplicate task text here; point at the TODO phase/task and add only owner decisions or deltas.

**Owner decisions shaping this roadmap (2026-11-25):**

- Next priority is the **v1 ship gate** (close open TODO phases), **plus** building and measuring the **cross-encoder rerank** (TODO Phase 4.3), which the owner wants in v1 despite the prior parking-lot placement.
- Primary audience for mission purposes is **real dental practices** (see `specs/mission.md`).

## Phase A: Cross-encoder rerank (measured)

- [ ] A.1 Owner approval for the cross-encoder choice: `Xenova/ms-marco-MiniLM-L-6-v2` through `fastembed` `TextCrossEncoder`, so no new Python dependency. Approved 2026-11-25; decision record `DECISIONS/cross-encoder-rerank.md` ticks when PR #24 merges.
- [ ] A.2 First, before any code, capture the rerank-off baseline on the frozen 120-chunk snapshot: recall@5, MRR, and p50/p95 retrieval latency under `eval/results/`. Then implement the toggleable rerank stage per `docs/internal/TODO.md` Task 4.3: hybrid top ~20, cross-encoder, top_n 5; default **off**; same return shape as `hybrid_search`.
- [ ] A.3 Run the rerank-on comparison against the A.2 baseline on the identical snapshot: recall@5, MRR, ordering quality, and latency delta in one side-by-side table. If it does not earn latency, keep it off and write down why.
- [ ] A.4 If on: re-run hybrid vs dense comparison (Task 4.4), the cost-gated Ragas context-precision check, and the offline suite; update README and this roadmap; move cross-encoder out of SCOPE.md §9 parking lot in the same change.

**A.2/A.3 outcome (2026-11-25; tick A.2 and A.3 on merge).**
Measured on the frozen 120-chunk snapshot with identical snapshot and golden sha256 values (`eval/results/rerank_baseline_off.json`, `eval/results/rerank_on.json`, table in `eval/results/rerank_comparison.md`).
Rerank on raises recall@5 from 0.9857 to 1.0000 and MRR@5 from 0.8981 to 0.9095.
It adds 1254.6 ms at p50 and 1708.9 ms at p95, about 17 times the retrieval time.
The gain does not earn the latency, so the stage ships off by default.
A.4 stays closed because it applies only when rerank ships on.

## Phase B: Ship-gate paperwork (TODO Phase 0)

- [ ] B.1 Create `SHIP_CRITERIA.md` (TODO Task 0.2) **or** record owner decision that SCOPE.md §6 remains the single source of truth and mark Task 0.2 superseded. Every number must map to a metric you can run.
- [ ] B.2 Finish Task 0.3 leftover: confirm `.env` never in git history (`git log --all --full-history -- .env` empty) and note the result.

## Phase C: Eval completeness (TODO Phase 6 + 8)

- [ ] C.1 Verify LangSmith run tags/metadata conventions (TODO Task 6.3): filterable by retriever variant, prompt version, model; fix conventions in code if missing.
- [ ] C.2 Manual error analysis over golden-set traces (TODO Task 8.1): categorize failures into `eval/ERROR_ANALYSIS.md` with counts and examples.
- [ ] C.3 One measured improvement with before/after table (TODO Task 8.2). Candidate: use Phase A rerank results if they moved a metric; otherwise pick the highest-impact fix from C.2. One change at a time.

## Phase D: Docs, audit, ship decision (TODO Phase 10)

- [ ] D.1 Align README with as-built reality after Phases A–C (targets, rerank status, eval numbers, open backlogs). Keep claims measured.
- [ ] D.2 Run the Part 3 audit prompt (TODO Task 10.2) and fix only what is flagged, smallest fixes.
- [ ] D.3 Ship-gate decision (TODO Task 10.3): ship / iterate / kill against the Phase B criteria; record the dated decision with specific numbers. Honor the stop trigger — no v2 feature work before this is recorded.

## Parked (do not start until Phase D ship decision)

- V2 receptionist booking (`docs/internal/SPEC_V2.md`) — cal.com integration; explicitly out of v1 (SCOPE.md §5)
- Remaining SCOPE.md §9 parking lot: original dental-benefit glossary, US triage source, clinician-mode corpus, MCP tool exposure, front-desk dashboard, multi-turn memory, multilingual
- Medical-tailored embedding swap (SHARED_CONTEXT.md eval roadmap step 6) — goes last; invalidates prior retrieval/Ragas numbers; needs full re-baseline

## Done (context only; details in TODO.md progress tracker)

Phases 1–5 and 7 are complete on `main` (corpus, golden set, dense, hybrid RRF, LangGraph agent + citations, guardrails). Live demo is deployed. Recorded baselines: Ragas faithfulness 0.9304, Harbor trilogy 204/204, live-model pass 192/202 (10 boundary over-refusals = open calibration backlog in `SHARED_CONTEXT.md`).
