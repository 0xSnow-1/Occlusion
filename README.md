# Chairside — Citation-Grounded Dental Patient FAQ Assistant

> **Status: MVP in active development.** This README is maintained as the project
> evolves; sections marked *WIP* are filled in as those phases complete. The build
> roadmap lives in [TODO.md](TODO.md); scope decisions live in
> [SCOPE.md](SCOPE.md); data provenance lives in
> [data/PROVENANCE.md](data/PROVENANCE.md).

**Not medical advice.** Chairside is a grounded information-retrieval assistant
over public dental-health documentation. It is explicitly scoped to refuse
diagnostic, prescriptive, and emergency questions and defer to a dental
professional — refusal correctness is a hard requirement, not a nice-to-have.

---

## Problem (one sentence, no "AI")

Dental patients with routine questions — post-procedure care, preventive care,
"is this normal or should I be worried" — drive a large share of the call volume
that front-desk staff can't keep up with; an assistant that correctly answers the
routine subset in seconds, and reliably refuses anything symptom- or
record-specific, can absorb that load without pretending to be a clinician.

## What this system is (one sentence)

A LangGraph agent that answers routine dental-health questions by retrieving from
a curated, openly licensed patient-education corpus using hybrid search
(BM25 + dense) fused with Reciprocal Rank Fusion, returns a structured, cited
answer validated against a Pydantic schema — and refuses to answer when it isn't
confident — with every change measured against a golden eval set.

## Architecture

```
  User question
       │
  Entry node (LangGraph)
       │
  Emergency / out-of-scope filter        ← deterministic, non-LLM, can override
       │
  Hybrid retrieval
  ├── Qdrant dense search  (cosine, top_k 20)
  └── Qdrant sparse search (BM25,   top_k 20)
       │
  Reciprocal Rank Fusion (RRF, k ≈ 60)
       │
  [optional] cross-encoder rerank → top_n 5
       │
  Prompt assembly with [SRC:doc_id] anchor tokens
       │
  LLM generation → Pydantic structured output
       │                    { answer, citations, confidence }
  Post-processing
  ├── citation verification (every cited ID must exist in the retrieved set)
  └── confidence / coverage threshold
       │
  below threshold → FAIL CLOSED: "I don't have enough grounded information …"
       │
  Answer + source links

  Cross-cutting: LangSmith tracing (latency, tokens, cost) ·
  Ragas eval harness vs. golden set in CI before any change ships
```

## Corpus

A small, deliberately curated corpus of ~15 openly licensed patient-education
documents (US government public domain + UK Open Government Licence):

- **4 PDFs** — HRSA (HHS) oral-health guides, NIDCR/NIH patient fact sheet
- **11 HTML pages** — NIDCR, CDC, and NHS UK, converted to markdown during ingestion

Every document's source, license, access date, and coverage is documented in
[data/PROVENANCE.md](data/PROVENANCE.md); the HTML parse queue with per-page
filenames is in [data/HTML_SOURCES.md](data/HTML_SOURCES.md).

**License & attribution:** corpus content is US public domain (HRSA/NIDCR/CDC)
and Open Government Licence v3.0 (NHS UK). NHS-derived material:
*"Contains public sector information licensed under the Open Government Licence
v3.0."*

**Known limitations (documented, not hidden):**

- **Triage guidance is UK NHS–based** — the only clearly-licensed patient-level
  source for emergency-triage content is nhs.uk, so urgent-care answers reflect
  NHS navigation (111 / 999 / A&E). We do not silently localize.
- **Insurance terminology is out of scope** (v1) — no clearly-licensed
  dental-specific glossary exists; related questions are refused as
  out-of-corpus rather than half-answered.
- **Fillings/scale-and-polish aftercare** is covered at treatment-overview level
  only; dedicated public aftercare pages don't exist under an open license.

## Tradeoffs made (and why)

- **RAG over prompt-only:** a static FAQ page handles fixed-phrasing, single-topic
  questions but breaks on paraphrase and multi-part asks, and produces no
  auditable citation trail. (Full argument: SCOPE.md §2.)
- **No fine-tuning:** small, well-defined domain with no proprietary style/tone
  requirement — prompting + retrieval is the right default. Knowing *not* to
  fine-tune is the point.
- **Hybrid retrieval + RRF over dense-only:** dense embeddings miss exact
  terminology; BM25 catches it. RRF fuses on rank rather than raw score because
  cosine (bounded) and BM25 (unbounded) scores live on incompatible scales.
- **Fail-closed on low confidence:** a health-adjacent assistant that confidently
  guesses is a liability; one that says "consult a professional" is a feature.
- **Citation anchoring + verification:** `[SRC:doc_id]` tokens in the prompt,
  verified against the actual retrieved set — a mechanical check against
  "citation-shaped hallucination" (ungrounded RAG averages only ~65–74%
  citation accuracy).
- **Measured reranker (pending):** the cross-encoder rerank stage ships only if
  the eval harness shows it earns its latency.

## Evaluation

Targets are committed in advance (SCOPE.md §6); **measured results will be
recorded here as harness phases complete — none are claimed yet.**

| Metric | Target | Measured |
|---|---|---|
| Faithfulness (Ragas) | ≥ 0.85 | *WIP* |
| Context precision (Ragas) | ≥ 0.75 | *WIP* |
| Answer relevancy (Ragas) | ≥ 0.80 | *WIP* |
| Hybrid beats dense-only on recall@5 | yes (gap reported either way) | *WIP* |
| Refusal correctness (trap questions) | **100% — zero slack** | *WIP* |
| Latency P95 | < 3 s | *WIP* |
| Cost per query | documented @ ~500 queries/day | *WIP* |

**Hard ship gate:** any trap question answered confidently instead of refused =
do not ship, regardless of every other number.

## How to run (local) — *WIP*

```bash
# prerequisites: Python 3.12+, uv
uv sync
cp sample.env .env   # then fill in your keys
# ingestion + run commands land here as phases complete (TODO.md §1, §5, §9)
```

## Demo

*WIP — deploys to Hugging Face Spaces (free tier) in TODO.md Phase 9. URL will
be posted here.*

## What's next / why it stops here

*WIP — finalized at the ship gate (TODO.md Phase 10). v2 parking lot: cross-encoder
reranking, an original dental-benefit glossary, a US triage source, a
"clinician-mode" corpus (the archived clinical guidelines), MCP tool exposure —
all deliberately not in v1.*


