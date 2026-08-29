# Scope — Chairside (working title)
### A citation-grounded dental patient FAQ assistant

Status: pre-build. This document is the thing you check against before writing code, and the thing you re-read before adding a feature that isn't on the list below.

---

## 1. Problem statement (one sentence, no "AI")

Dental patients with routine questions — post-procedure care, preventive care, "is this normal or should I be worried" — drive a large share of the call volume that front-desk staff can't keep up with; an assistant that correctly answers the routine subset in seconds, and reliably refuses anything symptom- or record-specific, can absorb that load without pretending to be a clinician.

## 2. Evidence this problem is real

Not assumed — pulled from current industry data on dental front-desk operations:

- Front desk staff spend an estimated 50-60% of work hours on phone calls, handling 40-60 calls/day at 4-6 minutes each, largely insurance, procedure, and logistics questions.
- Practices miss roughly 20-35% of incoming calls during business hours because staff are simultaneously handling in-person patients.
- 45% of calls arrive outside standard 9-5 hours, when no one is answering at all.
- 67% of patients still prefer phone over online booking/FAQ pages for anything beyond the simplest scheduling — meaning a static FAQ page alone measurably under-serves this problem.

This is the "why AI earns its complexity" argument for the checklist: a static FAQ page handles the easy 50-60% (fixed phrasing, single-topic questions) but breaks on natural phrasing variety, multi-part questions ("can I take ibuprofen after the extraction AND is the swelling normal"), and produces no citation trail a patient or practice can audit.

## 3. Who is the user

**Primary:** a patient with a routine dental-care question, interacting through a text/chat interface (practice website widget or standalone demo).

**Secondary beneficiary (not built for in v1):** front-desk staff, who see reduced routine-question call volume. Their workflow isn't instrumented in v1 — no dashboard, no ticket queue. That's a v2 idea, not a v1 requirement.

## 4. In scope (v1)

- Text-based Q&A over a curated corpus of public dental patient-education content (NIDCR, CDC, HRSA, NHS UK — see `data/PROVENANCE.md`)
- Hybrid retrieval (BM25 + dense) fused with reciprocal rank fusion
- Every answer carries a citation back to the specific source chunk(s) it was grounded in
- A deterministic, non-LLM emergency/out-of-scope filter that runs before the RAG path and can override it
- An evaluation harness (golden set + Ragas metrics) that must pass before any change ships
- A live, publicly reachable demo (no login required)

**Jurisdiction note (triage):** Emergency-triage and post-procedure guidance is
sourced from **NHS UK (nhs.uk, OGL v3.0)** — the only clearly-licensed patient-level
source for that category. Answers will reflect NHS service navigation (111 / 999 /
A&E) and UK practice. This is a documented limitation for a likely-US audience:
we do not silently localize guidance; the README carries this as a known tradeoff.

## 5. Explicitly out of scope (v1) — and why

Cutting these isn't a limitation to apologize for in the README — it's the judgment call that makes the project defensible.

| Cut | Why |
|---|---|
| Diagnosis or symptom-specific advice | The LLM should never be the thing deciding whether a symptom is serious. This is a hard line, not a soft one. |
| Any real patient records / PHI | No real patient data touches this system, anywhere. Corpus is 100% public patient-education material. This sidesteps HIPAA obligations by construction, not by promise — say this explicitly in the README. |
| Appointment booking / scheduling integration | Different problem, different system (calendar APIs, practice management software). Not this project. |
| Insurance terminology — general or plan-specific | **Descoped for v1.** No clearly-licensed dental-specific glossary exists (NADP's is all-rights-reserved), and the CMS Uniform Glossary covers general medical coverage, not dental benefits. Rather than ship a half-covered category, "what's a deductible" will be refused as out-of-corpus. Revisit in v2 with an original, clearly-labeled glossary (see §9). |
| Voice/phone channel | Text only. Voice is a UI problem layered on top of the same retrieval core — not worth the added complexity for an MVP whose point is retrieval quality and evaluation. |
| Fine-tuning | Prompting + retrieval is the right default; nothing about this task (small, well-defined domain, no proprietary style/tone requirement) justifies fine-tuning. Knowing *not* to reach for it is itself the signal. |
| Multi-lingual support | Stretch, not v1. |

## 6. Success metrics — "good enough" in numbers

Treat these as first-pass targets to recalibrate once you have a real golden-set baseline, not commandments. Write down what you actually measured in the README next to these.

- **Retrieval:** hybrid (RRF) beats both dense-only and BM25-only baselines on recall@5 against the golden set — the size of the gap is the actual finding, report it either way.
- **Faithfulness (Ragas):** ≥ 0.85
- **Context precision (Ragas):** ≥ 0.75
- **Answer relevancy (Ragas):** ≥ 0.80
- **Refusal correctness:** 100% on the golden set's emergency/out-of-scope trap questions. This is the one metric with zero acceptable slack — a health-adjacent assistant that fails to refuse is a failed project regardless of how good the retrieval numbers look.
- **Latency:** P95 < 3s per query
- **Cost:** documented cost-per-query at an assumed volume (e.g. 500 queries/day), even if the number is small — the reasoning matters more than the number.

## 7. Kill / ship criteria

**Ship when:** all thresholds in §6 are met, refusal correctness is 100%, the app is deployed at a public URL, and CI runs the eval suite on every change.

**Keep iterating if:** retrieval or faithfulness numbers are close but under threshold, or latency/cost are off — these are normal first-pass gaps.

**Do not ship, no matter how good everything else looks, if:** any trap question in the golden set gets a confident, non-refused answer it shouldn't have gotten. Fix that before touching anything else.

**Stop-building trigger:** once the above is true and basic tracing (LangSmith) is live, stop. Move to the next portfolio project. Don't add voice, don't add booking, don't add multi-lingual — that's polish, and polish belongs in a "v2 ideas" section at the bottom of the README, not in the build queue.

## 8. What "done" looks like for this document

This scope file is done when you can read it back in six weeks and know, without re-deriving it, what you were building and why you said no to everything else. If a feature idea comes up mid-build, it goes in §9 below, not into the code.

## 9. v2 / parking lot (do not build now)

- Cross-encoder reranking on top of RRF
- Original dental-benefit glossary (project-authored, clearly labeled in the corpus) to revisit insurance terminology
- US-jurisdiction triage source, to revisit the NHS-UK-only limitation (§4)
- MCP server exposing this as a callable tool for other agents
- Front-desk-facing dashboard of deflected questions
- Multi-turn memory across a session
- Multi-lingual corpus and retrieval
