# TODO.md — Dental Knowledge RAG Agent (MVP)

> **Goal (the one sentence):** A LangGraph agent that answers dental-health questions by retrieving
> from a curated corpus with hybrid search (BM25 + dense), fuses results with RRF, returns a
> structured, cited answer via Pydantic-validated output — and refuses to answer when it isn't
> confident — with every change measured against a golden eval set.

**Ground rules for this file:**
1. Every task has a **✅ Verify** gate. Do NOT check off a task or start the next one until the
   verification passes. This file is a sequence of checkpoints, not a suggestion list.
2. Tasks describe **what** to build, **inputs**, **outputs/side-effects**, **how to verify**, and
   **pitfalls** — never the implementation. You write 100% of the code yourself.
3. Target stack (already pinned by `pyproject.toml` + `.env`): Qdrant Cloud (free tier),
   `fastembed` for local embeddings + sparse/BM25 vectors, `docling` for document parsing,
   `langgraph` orchestration, `pydantic` v2 structured output, one LLM provider for generation
   (pick: Bedrock/Anthropic **or** Groq — don't split the generation path across both during MVP),
   `ragas` + `pytest` for evaluation, LangSmith for tracing, Streamlit/Gradio for the demo.
4. Checklist mapping per phase: **A** Problem/Scope, **B** Data, **C** Architecture,
   **D** Evaluation, **E** Reliability/Guardrails, **F** Deployment, **G** Docs, **H** Kill/Ship.

---

## Phase 0 — Decisions on paper & repo hygiene (Checklist: A, C, H)

> Do this before any retrieval code. These are structural decisions that are expensive to unwind.

### Task 0.1 — Write `SCOPE.md` (problem, user, refusal taxonomy)
- **What:** A short doc stating: the user (someone with a dental-health question), the workflow
  (ask → grounded, cited answer or refusal), the pain point (paraphrased/multi-part questions
  keyword search can't handle), explicit framing as an *information-retrieval assistant over
  public dental documentation — NOT a diagnostic tool*, and a two-column
  **informational vs. diagnostic/prescriptive** taxonomy with 5 example questions of each.
- **Inputs:** Plan §1–§3; your own judgment on scope boundaries.
- **Outputs / side-effects:** `SCOPE.md` in repo root. The taxonomy becomes the spec for Phase 7.
- **✅ Verify:** Read it cold. Can you state the one-sentence problem + one non-AI alternative you
  rejected (and why) without looking? If yes, it's done.
- **⚠️ Pitfalls:**
  - Writing it *after* building — the taxonomy drives Phase 7's refusal logic; improvising it
    later shows in the design.
  - Scoping the corpus to "everything dental." Pick 1–2 concrete sources; a bounded corpus is
    what makes the golden set and confidence thresholds meaningful.

### Task 0.2 — Define "good enough" numbers + kill/ship criteria (`SHIP_CRITERIA.md`)
- **What:** A table of pre-committed targets, e.g. faithfulness ≥ 0.85, context precision ≥ 0.7,
  citation accuracy ≥ 90%, p95 latency (pick the number after Phase 5 timing), cost per query.
  Below it: your explicit stop-building trigger — what evidence means "ship it" vs. "iterate"
  vs. "abandon."
- **Inputs:** Plan §5-A and §5-H; rough knowledge of your LLM provider's free-tier limits.
- **Outputs / side-effects:** `SHIP_CRITERIA.md`. Phase 6's CI eval compares against these numbers;
  Phase 10 makes the final call against them.
- **✅ Verify:** Every number in the table is measurable by something you plan to build in Phase 6.
  Any number without a corresponding metric/harness → fix the plan now.
- **⚠️ Pitfalls:**
  - Targets higher than what the corpus can support. If the corpus genuinely doesn't cover a
    topic, context recall on those questions is capped — targets must reflect what a *good*
    system over *this* corpus can achieve.
  - Deciding kill/ship criteria "when you get there." The point is committing now, while you're
    rational.

### Task 0.3 — Repo hygiene: secrets, env conventions, module layout
- **What:** Confirm `.env` is in `.gitignore`; create `sample.env` listing every required var with
  no real values; pick the module layout, e.g. `src/ingest/`, `src/retrieve/`, `src/agent/`,
  `src/eval/`, `src/ui/` — and resolve the currently empty `rag/` dir (use it or delete it; no
  dead directories).
- **Inputs:** Current `.env`, `.gitignore`, empty `src/`, `rag/`, `data/` dirs.
- **Outputs / side-effects:** `sample.env` committed; `.env` verified ignored; layout recorded in
  one or two lines (in `SCOPE.md` or a README skeleton).
- **✅ Verify:** `git status` must not list `.env` as untracked, and
  `git log --all --full-history -- .env` must return nothing (never committed).
- **⚠️ Pitfalls:**
  - Your `.env` contains an apparent typo: `DRANT_URL` (presumably `QDRANT_URL`). Fix the key now
    or normalize it in one config module — never special-case it at each call site.
  - Committing `.env` "just this once." If it ever gets committed, rotate the keys — git history
    keeps them even after removal.

---

## Phase 1 — Corpus acquisition & ingestion pipeline (Checklist: B)

### Task 1.1 — Select and document the corpus (provenance log)
- **What:** Choose 1–2 licensable sources (e.g. a national dental association's patient-education
  pages, WHO/CDC oral-health PDFs). Create `data/PROVENANCE.md`: what each source is, URL,
  license/terms, date accessed, how current it is, and what is deliberately NOT in the corpus.
- **Inputs:** Web access; candidate source pages.
- **Outputs / side-effects:** `data/PROVENANCE.md`; raw source files under `data/raw/`.
- **✅ Verify:** A stranger reading `PROVENANCE.md` could re-download the exact corpus and know its
  vintage. Spot-check 2 documents against the coverage notes.
- **⚠️ Pitfalls:**
  - Sources whose terms prohibit redistribution/derivative works. Check now, not after the repo
    is public.
  - "I'll remember where it came from." Unrecorded provenance fails checklist B and makes golden
    set ground truth unauditable.

### Task 1.2 — Parse documents to clean markdown with `docling`
- **What:** A manual-run ingestion script (not a service) that converts each raw PDF/HTML source
  to normalized markdown, preserving section headings, writing to
  `data/parsed/<source>/<docname>.md`.
- **Inputs:** `data/raw/*` (PDFs/HTML).
- **Outputs / side-effects:** One markdown file per source doc; a run log listing docs parsed,
  parse failures, and doc lengths.
- **✅ Verify:** Open 3 parsed outputs next to their originals. Headings preserved? Tables not
  garbled? No cross-page sentence butchery? If a doc parses badly, fix parser config or drop the
  doc and note it in PROVENANCE.
- **⚠️ Pitfalls:**
  - Multi-column PDF layouts silently scrambling reading order — corrupts chunks downstream in
    ways you won't notice until eval scores look inexplicably weird.
  - Parsing the whole corpus ad hoc every run. Make it idempotent (skip by checksum) or you'll
    re-embed and re-pay on every tweak.

### Task 1.3 — Chunking strategy (heading-aware)
- **What:** Split parsed markdown into chunks aligned with section boundaries, target size roughly
  a few hundred tokens (pick the number, write it down), with small overlap or parent-section
  context. Log per-doc chunk counts.
- **Inputs:** `data/parsed/**.md`.
- **Outputs / side-effects:** Chunk records with stable IDs; a stats report (chunk count, min/
  median/max token length) to sanity-check the distribution.
- **✅ Verify:** Read 10 random chunks with zero surrounding context. Each should be independently
  understandable (or carry its section heading as context). Length distribution must not have
  pathological outliers (3-token or 5000-token chunks).
- **⚠️ Pitfalls:**
  - Fixed-size character splitting that severs sentences mid-thought — embeddings of half-ideas
    retrieve badly, and Ragas faithfulness suffers because the context never contained the
    complete claim.
  - Unstable chunk IDs (derived from list index instead of doc + section path). They must survive
    re-ingestion, or your golden set's doc_ids and the Qdrant collection drift apart after any
    re-ingest.

### Task 1.4 — Chunk metadata schema (Pydantic) + versioned snapshot
- **What:** A Pydantic model for a chunk: `chunk_id`, `doc_id`, `source_url`, `title`,
  `section_path`, `content`, `token_count`, `ingested_at`, license info. Serialize the full chunk
  set to `data/chunks_v1.jsonl` (versioned — bump on schema/strategy changes).
- **Inputs:** Task 1.3 chunk records.
- **Outputs / side-effects:** Schema module + `data/chunks_v1.jsonl` — the single source of truth
  for embedding, retrieval, and eval ground truth.
- **✅ Verify:** Load the JSONL back through the Pydantic model — every line validates. `wc -l`
  count matches the chunk stats report from 1.3.
- **⚠️ Pitfalls:**
  - Optional fields that are actually required (`source_url`, `license`) — citations are only as
    trustworthy as this metadata, and gaps surface as broken links in the Phase 9 demo.
  - Regenerating `chunks_v1.jsonl` with different content under the same filename. Version the
    file; otherwise eval results become non-comparable overnight.

---

## Phase 2 — Golden set (Checklist: B, D)

### Task 2.1 — Write 20–30 golden Q/A/source triples by hand
- **What:** For each: a question a real person would ask (including paraphrases and multi-part
  forms), a reference answer you wrote by reading the source, and the doc_ids that should ground
  it. Store as a versioned JSONL (e.g. `data/golden_set_v1.jsonl`), validated by a Pydantic model.
- **Inputs:** `data/parsed/` and `data/chunks_v1.jsonl`.
- **Outputs / side-effects:** `data/golden_set_v1.jsonl`; this is *your first error-analysis pass* —
  you'll naturally discover corpus gaps while writing it.
- **✅ Verify:** Give 5 random triples to a friend (or revisit them a day later): could they tell
  which source supports the answer? Does every `doc_id` in the set exist in `chunks_v1.jsonl`
  (write a throwaway check for this — validation scripts aren't "implementation," they're tests)?
- **⚠️ Pitfalls:**
  - Generating the set wholesale with an LLM. The plan is explicit: hand-written, or LLM-assisted
    with you reading and correcting every one. An LLM-generated golden set measures the LLM's
    assumptions, not your corpus.
  - Only writing questions the corpus answers easily. Include hard paraphrases now, or your
    recall numbers will be flattered and hybrid vs. dense comparison in Phase 4 will be
    meaningless.

### Task 2.2 — Add 5–10 adversarial / out-of-scope questions
- **What:** Add questions that must be **refused or flagged**: diagnostic/prescriptive asks
  ("what antibiotic should I take…"), questions outside corpus coverage, and ambiguous or
  loaded questions. Mark each with an `expected_behavior` field (`refuse_diagnostic`,
  `refuse_no_coverage`, `answer`).
- **Inputs:** The refusal taxonomy from `SCOPE.md` (Task 0.1).
- **Outputs / side-effects:** Extended golden set; `expected_behavior` becomes the spec Phase 7
  is tested against.
- **✅ Verify:** For each adversarial item, you can point at the exact `SCOPE.md` taxonomy line
  that says why it's out of scope. Anything you can't justify, either justify or remove.
- **⚠️ Pitfalls:**
  - Adversarial cases that are actually answerable from the corpus (then `expected_behavior` is
    wrong and Phase 7 will chase ghosts).
  - Forgetting at least one **empty-retrieval** style case (question on-topic but zero relevant
    chunks) — this exercises a distinct failure path from "diagnostic question."

---

## Phase 3 — Dense retrieval baseline (Checklist: C)

### Task 3.1 — Provision the Qdrant Cloud collection (hybrid-ready)
- **What:** Create a collection configured for **both** dense and named sparse vectors from day
  one (dense: cosine; sparse: BM25/IDF-compatible), with payload indexes for the fields you'll
  filter/cite on (`doc_id`, `source_url`, `title`). Choose the dense vector size to match your
  chosen fastembed model.
- **Inputs:** `QDRANT_API_KEY` + URL from `.env`; the fastembed model you selected (write the
  model name + dim into `SCOPE.md` or a config constant — one source of truth).
- **Outputs / side-effects:** A named collection on Qdrant Cloud; a short note of its config
  (vector names, dims, distance metric).
- **✅ Verify:** Use the Qdrant dashboard or a client `get_collection` call: collection exists,
  dense + sparse vector configs match your notes, payload indexes present. Delete-and-recreate
  from scratch once to prove your provisioning path is reproducible.
- **⚠️ Pitfalls:**
  - Creating a dense-only collection now and needing a migration in Phase 4 — sparse vectors must
    be declared at collection creation.
  - Hardcoding the vector dimension in multiple places; the moment you swap embedding models,
    you'll miss one and get cryptic dimension-mismatch errors.

### Task 3.2 — Embed chunks with `fastembed` (local) and upsert
- **What:** A script that reads `data/chunks_v1.jsonl`, embeds chunk contents locally with
  fastembed, and upserts points (payload = your chunk metadata) with deterministic point IDs
  derived from `chunk_id`. Idempotent: re-running should upsert the same IDs.
- **Inputs:** `data/chunks_v1.jsonl`; Qdrant client + API key.
- **Outputs / side-effects:** Populated collection; run log with upsert count; verify count
  matches the JSONL line count.
- **✅ Verify:** Point count in Qdrant == chunk count in JSONL. Fetch one point by ID and confirm
  its payload matches the source line in the JSONL exactly (spot-check `doc_id`, `source_url`,
  `content` prefix).
- **⚠️ Pitfalls:**
  - Qdrant Cloud free tier **suspends after ~1 week of inactivity** and deletes after ~4. Embed a
    habit (or a scheduled GitHub Action) of pinging the instance.
  - Using random point IDs — re-upserting then duplicates the corpus. Derive point IDs from
    `chunk_id` so upserts are true upserts.

### Task 3.3 — Dense search function (cosine, top_k = 20)
- **What:** A query function: question text → embed → Qdrant dense search (top_k 20) → returns
  chunks with scores. This is a pure retrieval function, no LLM involved yet.
- **Inputs:** A question string; populated collection.
- **Outputs / side-effects:** Ordered list of (chunk, score). Reusable by both the agent graph
  (Phase 5) and the eval harness (Phase 6).
- **✅ Verify:** Run 5 golden-set questions manually. Relevant chunks should plausibly appear in
  the top 20. Then run one question with an obvious exact-terminology match (a specific drug,
  procedure, or code name) and note where it ranks — that miss is your Phase 4 motivation.
- **⚠️ Pitfalls:**
  - Testing with corpus sentences instead of real questions — self-retrieval always looks great
    and proves nothing.
  - Skipping scores in the return value; Phase 6's retrieval metrics and your debugging both need
    them.

### Task 3.4 — Baseline retrieval metrics on the golden set
- **What:** A small eval script (pytest-runnable) that, for each golden question with retrieval
  ground truth, computes recall@k and MRR for the dense-only retriever. Emit a results table
  (JSON/Markdown) with a timestamp.
- **Inputs:** `golden_set_v1.jsonl`; Task 3.3 retriever.
- **Outputs / side-effects:** `eval/results/dense_baseline_<timestamp>.json` + a printed summary.
  **This is your before-number** for the Phase 4 comparison.
- **✅ Verify:** Hand-check one metric by eye: take one question, count the ground-truth doc_ids
  in the top-k yourself, confirm the script's number matches. If your hand calc and the script
  disagree, the script is wrong — fix it before trusting anything else.
- **⚠️ Pitfalls:**
  - Defining "hit" loosely (partial doc_id matches counting as hits). Decide the matching rule
    (exact chunk? doc-level?) and write it down in the results file.
  - Saving results to a non-versioned scratch location — these baseline numbers are the first
    entry in your "what improved and why" story; commit them.

---

## Phase 4 — Sparse (BM25) + RRF hybrid retrieval (Checklist: C, D)

### Task 4.1 — Sparse/BM25 vector upsert
- **What:** Generate sparse vectors (fastembed's BM25-style sparse model, or equivalent
  IDF-weighted sparse representation) for every chunk and upsert them to the collection's sparse
  vector space, alongside — not replacing — the dense vectors.
- **Inputs:** `data/chunks_v1.jsonl`; existing collection (Task 3.1/3.2).
- **Outputs / side-effects:** Every point now carries both dense and sparse vectors; upsert log.
- **✅ Verify:** Fetch a point and confirm both vector fields are populated and non-empty. Run one
  sparse-only search for an exact terminology question (the one that ranked poorly in 3.3) — it
  should now surface relevant chunks.
- **⚠️ Pitfalls:**
  - Mixed upsert strategies (dense points with IDs X, sparse with IDs Y) — keep one point per
    chunk carrying both vectors.
  - Assuming sparse and dense scores are comparable. They're not (cosine is bounded, BM25 is
    unbounded) — that's precisely why the next task fuses on *rank*, not score.

### Task 4.2 — Hybrid query with Qdrant prefetch + RRF fusion
- **What:** Implement the Qdrant prefetch pattern: dense prefetch top_k 20 + sparse prefetch
  top_k 20, fused server-side with RRF (k ≈ 60, read the docs page in the plan §4-1 for the exact
  API). Return fused, ranked chunks.
- **Inputs:** Task 3.3/4.1 building blocks; Qdrant hybrid-queries docs.
- **Outputs / side-effects:** A `hybrid_search()` retriever — same return shape as `dense_search()`
  so downstream code and the eval harness can swap them freely.
- **✅ Verify:** Re-run the exact-terminology question from 3.3 — it should now rank better. Also
  run 3 paraphrased golden questions and confirm dense-favored results didn't collapse. Finally,
  hand-compute RRF for one tiny two-query case (e.g. a doc ranked 1st and 3rd) and confirm the
  fused ordering matches your hand calc.
- **⚠️ Pitfalls:**
  - Implementing RRF client-side on your own score normalization instead of using Qdrant's fusion
    — it defeats the point and adds a subtle bug surface. Use the prefetch API.
  - Forgetting that RRF returns rank-based ordering: don't reuse the raw fused score as if it
    were a similarity score anywhere (thresholds, UI confidence, etc.).

### Task 4.3 — (Optional) Cross-encoder reranking to top_n = 5
- **What:** Add an optional rerank stage: take the RRF top ~20, score pairs with a local
  cross-encoder (sentence-transformers), return top_n 5. Must be a toggleable stage, off by
  default until measured.
- **Inputs:** Hybrid search results; a local cross-encoder model.
- **Outputs / side-effects:** `hybrid_search(rerank=True|False)`; note the added p50/p95 latency.
- **✅ Verify:** Toggle it on for 5 golden questions: do top-5 results visibly improve (better
  ordering)? Record the latency delta. If ordering doesn't improve measurably, keep it off and
  write down why — "we measured, it didn't earn its latency" is a great interview answer.
- **⚠️ Pitfalls:**
  - Reranking before fusing (reranking dense-only results) — you're then just polishing half the
    signal.
  - Shipping it because it's cool, not because a metric moved. The Phase 6 harness will give you
    the real verdict; treat this task as scaffolding for that comparison.

### Task 4.4 — Hybrid vs. dense-only comparison — record the numbers
- **What:** Run the Task 3.4 eval script with the hybrid retriever (and with rerank on/off if
  built). Produce a side-by-side table: dense vs. hybrid (± rerank) on recall@k and MRR, plus a
  2–3 sentence interpretation of *which* question types each approach won on.
- **Inputs:** Golden set; both retrievers; Phase 3 baseline results.
- **Outputs / side-effects:** `eval/results/hybrid_vs_dense_<timestamp>.md` — **this is your first
  real eval story** and a README candidate section.
- **✅ Verify:** The table shows at least one concrete question where hybrid beats dense and you
  can articulate why (terminology match? paraphrase?). If hybrid never wins on anything, dig
  into why before proceeding — either your sparse indexing is broken or your golden set is too
  easy.
- **⚠️ Pitfalls:**
  - Comparing runs where the collection changed between measurements (re-ingested chunks, etc.).
    Both retrievers must run against the identical collection snapshot.
  - Only reporting averages. The per-question wins/losses are the interesting part and the
    evidence you'll show in interviews.

---

## Phase 5 — LangGraph agent, structured output, citation anchoring (Checklist: C, E)

### Task 5.1 — Pydantic answer schema
- **What:** Define the structured output model: `answer` (str), `citations` (list of doc_ids),
  `confidence` (bounded float or enum), plus a variant/model for the refusal path (e.g. refusal
  reason enum). This schema is the agent's *contract* — everything downstream depends on it.
- **Inputs:** Plan §3; the refusal taxonomy in `SCOPE.md`.
- **Outputs / side-effects:** Schema module shared by the agent graph and eval harness.
- **✅ Verify:** In a REPL/pytest, validate 3 hand-written sample outputs (a good answer, a
  refusal, and a malformed one) — the malformed one must raise a validation error, not pass.
- **⚠️ Pitfalls:**
  - `confidence` as a free float with no defined meaning — you'll need a threshold (Phase 7), so
    define what confidence represents *now* (self-reported? derived from retrieval scores? both?)
    and document it.
  - Free-text `citations` instead of a validated list of doc_id strings — the Phase 5.4
    verification step needs strict typing to be trustworthy.

### Task 5.2 — Prompt design with `[SRC:doc_id]` anchor tokens
- **What:** Build the generation prompt: chunks assembled with a `[SRC:doc_id]` token preceding
  each, system instructions to (a) answer only from provided context, (b) emit `[SRC:doc_id]`
  inline where claims are supported, (c) say "not enough information" rather than guess. Keep the
  prompt in its own module/versioned file — it's a first-class artifact you'll iterate on.
- **Inputs:** Hybrid search results (top 5); schema from 5.1.
- **Outputs / side-effects:** Prompt module; a "mock LLM" hook so tests can run without API calls.
- **✅ Verify:** Run 5 golden questions through the real LLM with the prompt. Every claim-bearing
  sentence should carry a citation token that matches a chunk you actually supplied. Read answers
  yourself for unsupported assertions — you are the error analyst here.
- **⚠️ Pitfalls:**
  - Assembling chunks without the anchor tokens and asking the model to "cite sources" — inline
    anchoring is the mechanism that makes verification mechanical rather than aspirational.
  - Stuffing all top_k 20 chunks into the prompt. The plan says top_n 5 post-rerank; more context
    ≠ better answers and it inflates latency/cost.

### Task 5.3 — LangGraph graph: retrieve → generate → validate
- **What:** A LangGraph state graph: entry node → retrieval node (calls `hybrid_search`) →
  generation node (LLM call with structured output per the schema) → validation node. State
  carries the question, retrieved chunks, raw LLM output, validated output. Wire LangSmith tracing
  on (your `.env` already has the keys).
- **Inputs:** Phases 3–5.2 components; generation provider credentials.
- **Outputs / side-effects:** A compiled graph invocable with a question, returning the validated
  Pydantic object; traces visible in your LangSmith project.
- **✅ Verify:** `python -c`-style invocation (or a tiny CLI entry) with 3 questions: end-to-end
  answer returned as a validated object; then open LangSmith and confirm you can see the full
  trace — every node, the prompt, the token counts, and the latency per node.
- **⚠️ Pitfalls:**
  - Letting the LLM's free-text output flow into the state unvalidated — always pass through the
    Pydantic parse inside the graph, or one malformed response poisons everything downstream.
  - Silent structured-output fallbacks. If the provider's structured-output mode isn't supported
    by the model you picked, you'll get JSON-mode attempts that occasionally fail — test with a
    long, awkward question deliberately.

### Task 5.4 — Citation verification post-processing
- **What:** A validation node step: extract every `[SRC:doc_id]` from the answer, verify each ID
  exists in the retrieved set for that query, and compute citation coverage (share of citations
  that are real; share of answer sentences carrying at least one). Mismatched/fabricated IDs →
  flag, strip, or fail the response per a rule you define and document.
- **Inputs:** Validated agent output; the retrieved chunk set stored in graph state.
- **Outputs / side-effects:** Post-processed answer with a citation-accuracy flag attached; this
  metric feeds Phase 6's harness directly.
- **✅ Verify:** Construct a hostile test: hand-craft an LLM-mock response citing a doc_id that
  was never retrieved. The verifier must catch it. Then confirm a legitimate answer passes
  untouched.
- **⚠️ Pitfalls:**
  - Verifying that IDs exist in the retrieved set but not that the *sentence* is supported by
    that chunk — the plan calls this "citation-shaped hallucination." Full support-checking comes
    via Ragas faithfulness in Phase 6; at minimum, log both signals separately.
  - Failing the whole answer because one citation is off. Decide the policy (strip the bad
    citation? regenerate? refuse?) deliberately — this is guardrail design, not plumbing.

### Task 5.5 — Cost & latency capture per call
- **What:** Extend the graph/logging to record per request: tokens in/out, provider cost
  estimate, retrieval latency, generation latency, end-to-end p50/p95 over a run batch. Emit as
  structured logs and/or a metrics summary function.
- **Inputs:** Graph from 5.3; provider usage metadata from responses.
- **Outputs / side-effects:** A `metrics` record per query; a batch summary you can paste into
  `SHIP_CRITERIA.md` to fill in the cost/latency rows.
- **✅ Verify:** Run a 10-question batch; confirm the summary shows plausible, non-zero token
  counts consistent with what you see in the LangSmith trace for one of them.
- **⚠️ Pitfalls:**
  - Trusting your own cost table forever — provider pricing changes; note the date of the prices
    you use.
  - Measuring latency only when the machine is idle and warm. Reranking (Phase 4.3) changes
    latency a lot on cold starts; measure both paths.

---

## Phase 6 — Eval harness, LangSmith discipline, CI (Checklist: D)

> Read Hamel Husain's evals essay (plan §4-7) *before* writing this harness, not after.

### Task 6.1 — Ragas harness over the golden set
- **What:** A script that runs the full agent over the golden set and computes Ragas metrics:
  faithfulness, context precision, context recall, answer relevancy. Emit a per-question breakdown
  (not just averages) plus an aggregate summary, versioned under `eval/results/`.
- **Inputs:** `golden_set_v1.jsonl`; compiled graph from 5.3; Ragas configured with your chosen
  judge model (`JUDGE_MODEL_ID` from `.env`).
- **Outputs / side-effects:** `eval/results/ragas_<timestamp>.json` + printed summary; the number
  CI tracks against `SHIP_CRITERIA.md` targets.
- **✅ Verify:** Take the single worst-scoring question and read its full trace. Can you
  articulate *why* it scored badly (retrieval miss? unsupported claim? vague question)? If you
  can't explain a score, you can't act on it — and you shouldn't trust the harness yet.
- **⚠️ Pitfalls:**
  - Feeding Ragas contexts in the wrong shape (Ragas wants the retrieved contexts per question —
    mismapped fields produce silently wrong scores). Validate the mapping on one question by hand.
  - Judging with the same model that generates — correlated errors inflate scores. Keep the judge
    model (`JUDGE_MODEL_ID`) distinct from the generator.

### Task 6.2 — Custom citation-accuracy metric
- **What:** Wrap the Phase 5.4 verifier into a metric over the golden set: % of answers where all
  cited doc_ids exist in the retrieved set (and % of sentences carrying a valid citation).
- **Inputs:** Task 5.4 verifier; agent outputs over the golden set.
- **Outputs / side-effects:** Citation-accuracy number reported alongside Ragas metrics in every
  results file — ungrounded RAG averages only ~65–74% here, so beating that is a differentiator.
- **✅ Verify:** If citation accuracy looks near-perfect while faithfulness is low, you're
  verifying ID *existence* but not claim *support* — note the distinction in the results file;
  don't average them away.
- **⚠️ Pitfalls:**
  - Treating "citation exists in retrieved set" as "claim is supported." Different claims; track
    both, name them precisely.
  - Adversarial items polluting the metric — refusals have no citations by design; exclude
    `expected_behavior: refuse_*` items explicitly.

### Task 6.3 — LangSmith conventions (tracing hygiene)
- **What:** Set a consistent tracing convention: run names like `eval|golden_v1|<git-sha>`,
  metadata tags for retriever variant (dense/hybrid/rerank), prompt version, model name — set in
  code at graph invocation, never by hand.
- **Inputs:** `.env` LangSmith keys; graph from 5.3.
- **Outputs / side-effects:** Every trace filterable by variant and commit; the raw material for
  Phase 8's manual error analysis.
- **✅ Verify:** Run the golden set twice with different retriever variants; in the LangSmith UI,
  filter by tag and confirm each run isolates correctly. If you can't filter it, fix the
  convention before Phase 8.
- **⚠️ Pitfalls:**
  - One giant default project where every run looks alike — the 50–100 trace review becomes
    impossible without clean filtering.
  - Tagging manually and forgetting half the runs; set tags programmatically.

### Task 6.4 — GitHub Actions: eval suite on every push
- **What:** A CI workflow that (a) runs the fast pytest suite (unit tests, no API calls) on every
  push, and (b) runs the full Ragas + citation eval on demand (`workflow_dispatch`) or nightly,
  posting the summary as a job artifact. Never put real keys in the workflow file.
- **Inputs:** `eval/` harness; pytest suite; provider keys added as GitHub repo secrets.
- **Outputs / side-effects:** `.github/workflows/eval.yml`; a results artifact per run.
- **✅ Verify:** Push a trivial commit → CI unit suite green. Trigger the eval workflow manually →
  artifact contains the metrics summary. Then deliberately break a unit test locally, push, and
  confirm CI catches it — an alarm you've never heard ring is not an alarm.
- **⚠️ Pitfalls:**
  - Running the full LLM-judged eval on *every* push — burns judge quota and adds ~20 min per
    commit. Split fast tests from slow evals.
  - Qdrant Cloud free tier suspends after ~1 week of inactivity — CI needs the DB alive; schedule
    a keep-alive ping or accept nightly-only evals and document that.

---

## Phase 7 — Guardrails & fail-closed behavior (Checklist: E)

### Task 7.1 — Confidence/coverage threshold → fail-closed response
- **What:** Implement the threshold rule from `SHIP_CRITERIA.md`: when confidence and/or citation
  coverage falls below threshold, or retrieval returns zero/weak results, the graph routes to a
  refusal node with the fixed fail-closed message — never a guess. Refusals must be structured
  output (schema from 5.1), not raw strings.
- **Inputs:** Confidence semantics defined in 5.1; thresholds from `SHIP_CRITERIA.md`.
- **Outputs / side-effects:** Conditional edge in the graph; refusal path exercised by adversarial
  golden items.
- **✅ Verify:** Run the Task 2.2 adversarial items — every `refuse_no_coverage` item refuses.
  Equally critical: spot-check that *answerable* items are NOT refused. A system that refuses
  everything is technically safe and completely useless; measure the over-refusal rate.
- **⚠️ Pitfalls:**
  - Threshold set from vibes. Sweep the threshold across a range, look at answer-rate vs. refusal
    precision, pin the number, document the sweep.
  - Unstructured refusal strings — downstream UI and eval both need the structured refusal with a
    reason enum.

### Task 7.2 — Diagnostic/prescriptive refusal layer
- **What:** Implement the informational vs. diagnostic taxonomy from `SCOPE.md`: questions asking
  for diagnosis, medication, or treatment decisions route to a distinct refusal ("this is a
  decision for a dental professional") **even when retrieval results exist**. Decide deliberately:
  prompt-level classification vs. rule-based.
- **Inputs:** `SCOPE.md` taxonomy; adversarial items marked `refuse_diagnostic`.
- **Outputs / side-effects:** Second refusal path, distinguishable by a different reason enum.
- **✅ Verify:** All `refuse_diagnostic` items refuse. Then run tricky *informational* items that
  mention symptoms in passing ("what is a root canal — my dentist says I might need one") — these
  must ANSWER, not refuse. The boundary cases are the whole test.
- **⚠️ Pitfalls:**
  - Over-blocking: a naive keyword blocklist ("pain", "antibiotic") refuses legitimate educational
    questions containing those words. Test the boundary, not just obvious cases.
  - Two refusal paths drifting apart in tone/disclaimer — keep both messages in one module.

### Task 7.3 — Error handling: empty retrieval, timeouts, malformed output
- **What:** Handle the three failure modes from plan §5-E without crashing: (1) zero/weak
  retrieval → fail-closed refusal; (2) LLM/DB timeouts & rate limits → bounded retry with backoff,
  then fail-closed; (3) Pydantic validation failure of LLM output → one bounded repair retry, then
  fail-closed. Every failure path logs a structured error event (visible in LangSmith).
- **Inputs:** Graph from 5.3; the failure taxonomy above.
- **Outputs / side-effects:** The graph cannot crash on any of the three paths; failures degrade
  to refusals.
- **✅ Verify:** Force each failure deliberately: query with a term that matches nothing; point
  the client at a bad URL (timeout); feed a malformed mock LLM response. Each must produce a clean
  refusal + a log entry — never a stack trace.
- **⚠️ Pitfalls:**
  - Unbounded retries: a hanging provider turns into a hung demo. Cap retries and total time.
  - Silent exception swallowing (`except: return refusal`) — always log exception type and
    message, or you'll debug incidents with zero evidence.

### Task 7.4 — Adversarial pass, end-to-end
- **What:** Run the entire golden set (normal + adversarial) through the guarded graph; produce a
  summary: for each `expected_behavior`, how many items behaved as specified.
- **Inputs:** Full golden set; guarded graph from 7.1–7.3.
- **Outputs / side-effects:** `eval/results/guardrails_<timestamp>.md`; any mismatch becomes a
  named TODO item, not a vibe.
- **✅ Verify:** 100% of adversarial items behave as specified AND the over-refusal rate on normal
  items is under a max you pick now. Any miss → fix, re-run, re-record.
- **⚠️ Pitfalls:**
  - Running this once and treating it as permanent. Re-run after *every* prompt or threshold
    change — guardrails regress silently.
  - Fixing a miss by widening refusal rules until normal questions break; adjust surgically and
    re-check the over-refusal rate.

---

## Phase 8 — Manual error analysis + one measured improvement (Checklist: D)

### Task 8.1 — Review 50–100 real traces; categorize failures
- **What:** Sit down with the LangSmith traces from golden-set runs (use the 6.3 filters) and
  categorize every failure into named types you define (e.g. retrieval miss, wrong-chunk
  retrieval, unsupported claim, bad citation, over-refusal, formatting). Write it up in
  `eval/ERROR_ANALYSIS.md` with counts and one example per type.
- **Inputs:** LangSmith traces (multiple retriever variants); Ragas per-question breakdown.
- **Outputs / side-effects:** `eval/ERROR_ANALYSIS.md` — the doc that teaches you what "good"
  looks like for *this* corpus, and the source of every improvement idea in 8.2.
- **✅ Verify:** For each failure category, you can name its most likely fix (chunking?
  retriever? prompt? threshold?). A category with no plausible fix usually means it's described
  too vaguely — split it.
- **⚠️ Pitfalls:**
  - Doing this after automating everything and trusting the metrics. The plan is explicit: manual
    analysis first; automated metrics without this context are just numbers.
  - Fixing things while reviewing. Review first, list fixes, then fix in order of impact —
    otherwise you get random-walk tuning.

### Task 8.2 — One measured improvement (before/after)
- **What:** Pick the single highest-impact fix from 8.1 (likely: reranker on/off, chunk size,
  prompt revision, or threshold change). Implement it, re-run the full harness, record
  before/after in one table with the question types affected.
- **Inputs:** `ERROR_ANALYSIS.md`; full eval harness from Phase 6.
- **Outputs / side-effects:** A concrete "here's what improved and why" story — the centerpiece of
  the README and your interviews. If the fix didn't help, that's also a result: record why and
  revert.
- **✅ Verify:** The before/after table shows movement on at least one `SHIP_CRITERIA.md` metric
  (or a documented, honest "no improvement, reverted"). No un-measured changes ship past this
  point — this discipline is the project's actual thesis.
- **⚠️ Pitfalls:**
  - Changing three things at once — you won't know which one moved the metric, and you can't tell
    the story.
  - Cherry-picking the metric that improved while ignoring one that regressed. Report both;
    tradeoff talk reads as senior, one-sided wins read as naive.

---

## Phase 9 — Demo UI + deployment (Checklist: F)

### Task 9.1 — Minimal demo UI (Streamlit or Gradio, pure Python)
- **What:** A small chat/box UI: question input → calls the compiled graph → renders the answer
  with clickable source links (from chunk `source_url` metadata), a confidence indicator, and
  refusals rendered distinctly. No React — plan §7's data says backend depth is the
  higher-leverage skill for your goal.
- **Inputs:** Compiled graph; refusal schema; chunk metadata for links.
- **Outputs / side-effects:** `src/ui/app.py` (or equivalent); runs locally on a free port.
- **✅ Verify:** Give it to a non-technical friend (or yourself on a phone): ask a question, get a
  cited answer, and understand *why* a refusal happened when one does. Every source link must
  resolve.
- **⚠️ Pitfalls:**
  - Leaking raw internals to the UI (bare chunk IDs as citations instead of human-readable source
    names + URLs).
  - Streamlit state bugs where one question contaminates the next — it reruns the whole script;
    understand its execution model before adding session state.

### Task 9.2 — (Optional) FastAPI service + health check
- **What:** Only if you want API/UI separation: a FastAPI wrapper exposing `POST /ask` (the graph)
  and `GET /health` (actually checks Qdrant reachability + provider config). Otherwise the
  Streamlit app with an in-app health indicator satisfies the checklist.
- **Inputs:** Compiled graph; uvicorn.
- **Outputs / side-effects:** `src/api/` with `/ask` and `/health`; the checklist's health-check
  box ticked.
- **✅ Verify:** `curl` the health endpoint (expect 200 + JSON status), then `/ask` with a valid
  question and an empty question — the empty one must return a clean 4xx or structured refusal,
  never a 500.
- **⚠️ Pitfalls:**
  - Building it "because real systems have APIs" when the demo is the only consumer — it's
    optional scope; skip it if it delays the ship date.
  - A health check that returns static OK without touching Qdrant — a liveness check that lies.

### Task 9.3 — Deploy to Hugging Face Spaces (or Streamlit Community Cloud)
- **What:** Prepare the app per the platform's requirements, configure secrets in the platform's
  secrets manager (never in the repo), deploy, confirm a stranger can hit the URL. Add a scheduled
  GitHub Action keep-alive ping so the Qdrant free tier doesn't suspend.
- **Inputs:** Working UI from 9.1; secrets (Qdrant, LLM, LangSmith); `sample.env` as the checklist
  of required platform secrets.
- **Outputs / side-effects:** A public demo URL; `.github/workflows/keepalive.yml`; deploy
  instructions in the README.
- **✅ Verify:** From an incognito window: ask 3 questions — one normal, one diagnostic (expect
  refusal), one nonsense (expect refusal). All behave; all links resolve; nothing crashes on first
  cold load.
- **⚠️ Pitfalls:**
  - Committing secrets to "make deploy easy" — use platform secrets; rotate anything that ever
    touched a committed file.
  - The Space sleeps on inactivity, so the first visitor after a gap hits a cold start —
    acceptable, but mention it in the README so an interviewer isn't surprised.

---

## Phase 10 — README, final audit, ship gate (Checklist: G, H)

### Task 10.1 — Write the README (yourself, per the field-guide structure)
- **What:** Sections: one-sentence problem statement → demo link → architecture diagram → eval
  numbers (before/after from 4.4 and 8.2, plus guardrail results) → how to run locally (one
  command, from `sample.env`) → tradeoffs made and why (prompt-only vs. RAG vs. fine-tune per
  plan §3; RRF over score blending; fail-closed) → what you'd build next and why you stopped here.
- **Inputs:** `SCOPE.md`, `SHIP_CRITERIA.md`, `eval/results/*`, `ERROR_ANALYSIS.md`,
  `PROVENANCE.md`.
- **Outputs / side-effects:** `README.md` replacing the current empty one.
- **✅ Verify:** A stranger (or the Part 3 audit prompt) can reconstruct *what the system does,
  how well it works, and why it's built that way* from the README alone, without reading code.
  Also time yourself: 2-minute explanation, checklist G.
- **⚠️ Pitfalls:**
  - The AI-generated README smell: generic praise of the architecture, no numbers, no tradeoffs.
    The field guide flags this — write it, then edit it hard.
  - Claiming medical-advice capability. Keep the SCOPE framing: grounded retrieval assistant over
    public dental documentation, not a diagnostic tool.

### Task 10.2 — Run the Part 3 audit prompt against the repo
- **What:** Paste the audit prompt from `ai-mvp-checklist.md` (Part 3) into an agent with repo
  access; it scores every checklist item PASS/PARTIAL/FAIL with evidence.
- **Inputs:** Finished repo; `ai-mvp-checklist.md` Part 3.
- **Outputs / side-effects:** Audit table + a short list of flagged items.
- **✅ Verify:** Fix ONLY what's flagged, with the smallest possible fixes — per the checklist's
  own instruction, don't use the audit as an excuse to add features.
- **⚠️ Pitfalls:**
  - Treating PARTIALs on deliberately descoped items (e.g. skipped FastAPI) as failures requiring
    work. Document the descope decision in the README instead of building it.
  - Re-running the audit after cosmetic commits to "farm" a better verdict — it's a mirror, not a
    scorecard to game.

### Task 10.3 — Ship gate decision
- **What:** Compare final numbers against `SHIP_CRITERIA.md`. Three pre-decided outcomes:
  **ship** (targets met, demo live, CI green → stop building, start the next project),
  **iterate** (one metric short, one named fix identified → one more measured improvement cycle,
  max), or **kill** (structurally below targets with no identified fix → write up findings
  honestly and move on — a documented kill is still a portfolio asset).
- **Inputs:** All eval results; the audit; the live demo.
- **Outputs / side-effects:** A dated decision recorded at the bottom of `SHIP_CRITERIA.md`.
- **✅ Verify:** The decision references specific recorded numbers, and — per checklist H — you
  actually honor the stop trigger. Starting "v2 polish" instead of the next project is a failed
  gate, whatever the numbers say.
- **⚠️ Pitfalls:**
  - Moving the goalposts after seeing the numbers — the entire value of Task 0.2 was committing
    while rational.
  - Treating "kill" as wasted work: a repo with an honest eval harness, guardrails, and a
    documented kill rationale demonstrates more engineering judgment than most shipped tutorial
    clones.

---

## Progress tracker

| Phase | Focus | Checklist | Status |
|---|---|---|---|
| 0 | Decisions on paper & repo hygiene | A, C, H | ☐ |
| 1 | Corpus + ingestion | B | ☐ |
| 2 | Golden set | B, D | ☐ |
| 3 | Dense retrieval baseline | C | ☐ |
| 4 | BM25 + RRF hybrid (+ optional rerank) | C, D | ☐ |
| 5 | LangGraph agent + citations | C, E | ☐ |
| 6 | Ragas harness + LangSmith + CI | D | ☐ |
| 7 | Guardrails & fail-closed | E | ☐ |
| 8 | Manual error analysis + one improvement | D | ☐ |
| 9 | Demo UI + deployment | F | ☐ |
| 10 | README + audit + ship gate | G, H | ☐ |

**Dependency notes:**
- Phases 0–2 gate everything: no retrieval code before the golden set exists (plan §8-1).
- Phase 6 depends on 5.3's graph, but the *retrieval* metrics in 3.4/4.4 are LLM-free — build
  them early and run them often.
- Phase 9 is deliberately last (plan §8-7): the README is easiest to write once the system works
  and has numbers.










