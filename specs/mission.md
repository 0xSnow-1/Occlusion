# Mission

## Purpose

Occlusion is a citation-grounded dental patient FAQ assistant.
It answers routine questions from a curated public corpus and refuses anything diagnostic, prescriptive, or out of corpus.
It exists so dental practices can absorb routine front-desk question load without the system pretending to be a clinician.

## Audience

**Primary: real dental practices.**
The product frame is a practice-facing text assistant (website widget or standalone demo) that front desks and patients can use for routine questions.
The secondary beneficiary is front-desk staff (reduced call volume); their dashboard is out of scope for v1 (SCOPE.md §3).

**Secondary: recruiters and interviewers.**
This is also a portfolio project that must demonstrate eval rigor, safety wiring, and honest measured results.
When the two audiences conflict, the practice-facing safety bar wins (refusal correctness is zero-slack).

## Scope

In scope (v1, from SCOPE.md §4):

- Text-based Q&A over the curated public corpus (HRSA/NIDCR/CDC public domain + NHS UK OGL v3.0)
- Hybrid retrieval (dense + SPLADE sparse) fused with RRF, plus a toggleable cross-encoder rerank stage (owner decision 2026-11-25: build and measure TODO Phase 4.3; keep off by default until it earns its latency)
- Inline `[SRC:doc_id]` citations verified against retrieved chunks; fail-closed on zero or fabricated citations
- Deterministic pre-LLM guardrail for diagnostic/prescriptive/out-of-scope questions
- Evaluation harness (golden set + Ragas with distinct judge + Harbor refusal trilogy) that gates changes
- A live, publicly reachable demo (Streamlit Community Cloud; already deployed)

Out of scope (v1, from SCOPE.md §5):

- Diagnosis or symptom-specific advice
- Any real patient records / PHI
- Appointment booking / scheduling (v2 idea in SPEC_V2.md; not v1)
- Insurance terminology
- Voice channel, fine-tuning, multi-lingual support
- Front-desk dashboard, multi-turn memory, MCP exposure (SCOPE.md §9 parking lot)

## Success criteria

Numbers from SCOPE.md §6 (owner-recalibrated where noted):

- Refusal correctness: 100% on golden-set trap questions (zero slack; ship blocker)
- Faithfulness (Ragas) ≥ 0.85 — measured baseline 0.9304
- Response relevancy ≥ 0.80 — measured 0.8938
- Context precision ≥ 0.75 — measured 0.7952 (open retrieval-ranking backlog)
- Hybrid (± rerank) beats dense-only and sparse-only on recall@5 vs the golden set, with the gap reported either way
- Latency P95 ~5 s accepted for v1 (owner decision 2026-09-19; staging must re-measure before any ship claim)
- Cost documented per query at assumed volume (~$0.01/query estimate on record)
- Ship gate (SCOPE.md §7): all thresholds met, public URL live, CI green; any confidently answered trap = do not ship

v1 closure also requires the open `docs/internal/TODO.md` ship-gate work (Phases 0.2, 6.3, 8, 10) and a recorded ship/iterate/kill decision.

## Open questions

- Where should `SHIP_CRITERIA.md` live? TODO Phase 0.2 never created it; thresholds currently live in SCOPE.md §6. Owner has not chosen a single source of truth.
- Does "real dental practices" as primary audience change any v1 success bar (for example, uptime, support, or compliance expectations) beyond SCOPE.md §6, or is it framing only until a practice actually pilots it?
- V2 receptionist booking (`docs/internal/SPEC_V2.md`) is written but explicitly out of v1 scope. Confirm it stays parked until the v1 ship-gate decision is recorded.
- Cross-encoder rerank (TODO 4.3) was deliberately off and listed in the SCOPE.md §9 parking lot. Owner decision 2026-11-25 puts it in the active roadmap; SCOPE.md §9 and README roadmap lines still need a matching edit when that step ships.
- Index parity: eval numbers use the frozen 120-chunk snapshot; the vendored demo index holds 133 points. Exact eval-demo parity is not guaranteed (live-HTML build variance).
