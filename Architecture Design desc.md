# Architecture Design — Description

**Companion document for:** `Architecture_diagram_v3.png` (canvas diagram)
**Project:** Occlusion (working title: *Chairside*) — citation-grounded dental patient-FAQ assistant
**Use:** present this file alongside the image — the image shows *what*, this describes *why*.

**Legend:** 🤖 = agent (LLM-backed node) · `NC` = normal conversation · `RAG` = retrieval-augmented medical path · colored boxes = data stores/schemas.

---

## The diagram has two halves

### Right half — Ingestion (offline, runs once per corpus update) — ✅ IMPLEMENTED (`src/ingest/ingestion_pipeline.py`)

```
CORPUS (PDFs + HTML) → Parse → Chunk/Split text → Index (fastembed @ upsert) → Qdrant
```

1. **CORPUS** — ~15 openly licensed patient-education documents (NIDCR, CDC, HRSA
   PDFs + NHS UK pages; provenance in `data/PROVENANCE.md`).
2. **Parse** (`document_parser.py`) — `PyMuPDFLoader` for PDFs (one LangChain
   `Document` per page) + `WebBaseLoader` for HTML pages; every document gets a
   `doc_id` (filename stem or URL slug).
3. **Chunk/Split text** (`chunking_and_embedding.py`) —
   `RecursiveCharacterTextSplitter`, 1000 chars / 200 overlap; each chunk
   inherits the source metadata and gains `chunk_index` / `chunk_total`.
4. **Index** (`vector_store.py`) — no separate embedding stage: chunk text is
   wrapped in a fastembed `models.Document` at upsert time, which produces two
   representations per chunk:
   - **Dense vector** (all-MiniLM-L6-v2, 384-dim, cosine) → semantic match.
   - **Sparse vector** (Splade_PP_en_v1, BM25-style IDF-weighted `(index, value)`
     pairs) → catches exact terminology that dense embeddings miss.
5. **Vector DB** — Qdrant, persisted locally at `./data/qdrant_storage`
   (gitignored; pass an `https://` URL to target Qdrant Cloud instead). Each
   point is **self-contained**: dense vector + sparse vector + payload holding
   the chunk text *and* its metadata (`doc_id`, `chunk_index`, ...) — so
   retrieval can feed matched chunks straight to the LLM. The pipeline
   recreates the collection each run, so the store always mirrors the corpus.

*Why both vector types: dense search finds paraphrases, BM25 finds exact terms
(drug names, procedure names). Neither alone is sufficient — that's the whole
argument for hybrid retrieval.*

### Left half — Runtime (per user question) — 🔲 DESIGNED (`src/agent/` scaffolded, not yet implemented)

**Step 1 — Deterministic guardrail (before any LLM).** `START → Query → Filter`.
The "Out-of-scope GUARDRAIL" is plain code: a rules/keyword layer built from the
scope's refusal taxonomy. It is the *smoke detector* — dumb but always reliable.
If `Flagged? = yes`, flow goes directly to **PRINT MESSAGE** with **NO LLM CALL**:
a fixed refusal message plus a structured reason code. The AI never gets the
chance to answer something it must refuse, and refusals cost zero tokens.

**Step 2 — Router (LLM, structured output).** Not flagged → `Router`, which uses a
Pydantic SO schema (`RoutedAgent → Literal["CONVERSATIONAL" | "MEDICAL"]`), so it
can only output one of two labels — it cannot invent a third path. This is a *UX*
decision (which experience fits the question), not a *safety* decision — safety
was settled in step 1.

**Step 3a — CONVERSATIONAL → NC agent** 🤖: casual chat, no retrieval, then END.

**Step 3b — MEDICAL → RAG path** 🤖:
- The **Retrieval tool** queries the Vector DB with two prefetches (dense top-k 20
  + sparse top-k 20).
- **Reciprocal Rank Fusion** merges both result lists by *rank*, not raw score —
  cosine and BM25 scores live on incompatible scales, so rank-based fusion is the
  reliable way to combine them.
- The RAG agent generates an answer constrained by the **MedicalAnswer** Pydantic
  schema: `{ answer, citation[], confidence }`.

**Step 4 — Validation node (deterministic code, not an LLM).** Mechanical checks:
schema valid · every cited doc_id actually exists in the retrieved set ·
confidence ≥ threshold.

- **`Validated? = yes`** → answer + source links → **END**.
- **`Validated? = no`** → **Evaluator-Optimizer** (the agentic pattern from
  Anthropic's *Building Effective Agents*): an LLM returns *structured feedback*
  — the issues found and a suggested re-retrieval action (never medical content)
  — which is fed back to the RAG agent for another retrieve-and-generate pass.
  **Bounded at max 3 loops**; if quality still fails, flow exits to the same
  PRINT MESSAGE refusal node. The refusal path is always the floor.

---

## Design principles the diagram encodes

| Principle | Where in the diagram |
|---|---|
| Fail closed — the LLM never decides what gets refused | Filter + PRINT MESSAGE (no LLM call) |
| Deterministic checks are code; LLM judgment is a separate, constrained node | Validation node vs Evaluator-Optimizer |
| Every output is schema-validated | Pydantic SO at the router *and* the medical answer |
| Every answer is auditable | citations in the schema, verified against retrieved chunks |
| Bounded loops, bounded cost | `max 3` on the evaluator loop, then refusal |
| Hybrid retrieval over single-method | Dense + Sparse → RRF |

## 60-second presentation script

> "A question first hits a deterministic guardrail — pure code, no AI — which can
> immediately refuse with a canned message. Otherwise a router classifies it into
> casual chat or a dental question. Dental questions trigger hybrid retrieval:
> dense embeddings for meaning, BM25 for exact terminology, fused by reciprocal
> rank fusion. The answer is generated into a strict Pydantic schema with
> citations and a confidence score, then validated by code. Failed validations
> go to an evaluator that returns structured feedback for one more retrieval pass
> — maximum three — and if it still can't produce a grounded, confident answer,
> the system refuses rather than guesses. Refusing is a feature, not a failure."

---

*Related docs: `SCOPE.md` (scope + refusal taxonomy) · `data/PROVENANCE.md`
(corpus licenses/sources) · `README.md` (project overview) · `TODO.md` (build
roadmap) · source pattern: anthropic.com/research/building-effective-agents.*
