# Spec — Occlusion (Chairside dental RAG MVP)

> This file is the single technical-design and architecture reference for the project.
> It replaces `dental-rag-agent-mvp-plan.md` and `Architecture Design desc.md` as the source of truth.
> Every claim below is grounded in the code on `main` plus the contracts pinned by `tests/agent/*`.
> Where the old docs disagree with the code, the code and tests win.
> Related docs: `SCOPE.md` (scope + refusal taxonomy), `TODO.md` (build order), `data/PROVENANCE.md` + `data/HTML_SOURCES.md` (corpus), `DECISIONS/hybrid-qdrant-vector-store.md` (vector-store rationale).

## 1. What this system is (one sentence)

A LangGraph agent that answers routine dental-health questions by retrieving from a curated, openly licensed patient-education corpus using hybrid search (BM25 + dense) fused with Reciprocal Rank Fusion, returns a structured, cited answer validated against a Pydantic schema, and refuses to answer when it isn't confident, with every change measured against a golden eval set.

## 2. Architecture (as built + as specified by tests)

```text
User question
  |
Hybrid retrieval (Qdrant dense top_k 20 + sparse top_k 20, server-side RRF, client-side rrf_fuse fallback)
  |
RAG generation (LLM with structured output -> Answer { answer, citations, confidence })
  |
Validation (deterministic code: citations exist in retrieved set, confidence >= threshold, non-empty retrieval)
  |-- fail --> Refusal (structured, reason enum, message mentions consulting a dentist)
  |-- pass --> Answer + source links --> END
```

The deterministic guardrail / router / conversational-vs-medical split / evaluator-optimizer retry loop described in the old `Architecture Design desc.md` is not what the tests pin.
The tests pin a simpler pipeline: retrieve, generate, validate, fail closed (see §5).
Any router, conversational path, or bounded retry loop is future work and must be added to this spec before it is built.

## 3. Ingestion — write path (implemented)

### 3.1 Parse (`src/ingest/document_parser.py:10`)

PDFs are loaded recursively (`**/*.pdf`) with `PyMuPDFLoader`, one LangChain `Document` per page.
Each PDF page gets `doc_id` equal to the file stem (`pdf_file.stem`).
Web pages are loaded with `WebBaseLoader`, and each gets `doc_id` from the URL slug (`link.split("/")[-2] or [-1]`).
`load_all_documents(pdf_dir, url_list)` concatenates both lists and is the entry point the pipeline calls.
Parsing failures are logged with `logger.exception` and skipped, never raised.

### 3.2 Chunk (`src/ingest/chunking_and_embedding.py:54`)

Chunking uses `RecursiveCharacterTextSplitter` with defaults `chunk_size=1000`, `chunk_overlap=200`.
Each chunk inherits its source document metadata and gains `chunk_index` (0-based) and `chunk_total`.
There is no embedding step in this module.
Embedding happens at upsert time inside Qdrant via fastembed `models.Document` (see §3.3).
Known issue on `main`: this file contains unresolved merge-conflict markers (`HEAD` vs `feature/retrieve`).
The `HEAD` side adds a `sentence-transformers` `embed_documents` / `process` path plus a CLI that the tests do not cover and the pipeline does not call.
The resolved direction is the `feature/retrieve` side (chunk-only), and the conflict markers must be removed with the `HEAD` side dropped.

### 3.3 Index (`src/ingest/vector_store.py:35`)

`VectorStore` manages one Qdrant collection declared hybrid-ready from day one.
Dense config is `sentence-transformers/all-MiniLM-L6-v2` with cosine distance, and the dimension is read via `client.get_embedding_size()` rather than hardcoded.
Sparse config is `prithivida/Splade_PP_en_v1` (SPLADE/BM25-style).
Payload indexes are created on `doc_id` (keyword), `source_url` (keyword), and `title` (text).
`upsert_documents` takes a list of dicts each containing a `text` key plus metadata, stores the full dict (including `text`) as payload so each point is self-contained, and assigns integer point ids `0..n`.
Three connection modes exist: `":memory:"` for tests, `http(s)://` for server/Cloud, and any other string as a local on-disk path (default `./data/qdrant_storage`).
Sparse vectors must be declared at collection creation and can never be added later (see `DECISIONS/hybrid-qdrant-vector-store.md`).

### 3.4 Pipeline (`src/ingest/ingestion_pipeline.py:51`)

`IngestionPipeline` composes parse, chunk, and index in one `run()` call returning `{"pages", "chunks", "points"}`.
Defaults are `data/raw` for PDFs, the 11 URLs in `DEFAULT_HTML_URLS` for HTML, collection `occlusion`, local storage `./data/qdrant_storage`, and chunking `1000/200`.
`recreate_collection=True` by default, so each run deletes and recreates the collection and the store always mirrors the corpus with no stale points.
An empty parse returns `{"pages": 0, "chunks": 0, "points": 0}` with a warning and no collection writes.

## 4. Retrieval — read path (implemented)

### 4.1 Shared mapping (`src/retrieve/base.py:13`)

`points_to_chunks` converts Qdrant scored points (objects or dicts) into `RetrievedChunk` lists.
It reads chunk text and metadata from the point payload, falls back to the point id when `doc_id` is missing, and skips points with empty text with a warning.
No second document store is needed because payloads are self-contained.

### 4.2 Dense and sparse (`src/retrieve/dense.py:14`, `src/retrieve/sparse.py:19`)

`dense_search(client, collection, query, top_k=20)` embeds the query with the dense model and searches the `dense` vector with cosine.
`sparse_search(client, collection, query, top_k=20)` embeds the query with the sparse model and searches the `sparse` vector.
Both return `list[RetrievedChunk]` best-first with scores preserved.
Neither function calls an LLM.

### 4.3 Hybrid (`src/retrieve/hybrid.py:19`)

`hybrid_search(client, collection, query, top_k=20, top_n=5, fusion_k=60)` issues two prefetches (dense `top_k` + sparse `top_k`) fused server-side with `FusionQuery(fusion=RRF)` and returns the fused `top_n`.
When server-side fusion is unavailable (older servers, some `:memory:` modes), it falls back to client-side `rrf_fuse` over independent dense and sparse searches and logs a warning.
Fused ordering is rank-based and must never be reused as a similarity score or threshold.

### 4.4 Fusion (`src/agent/fusion.py:19`)

`rrf_fuse(dense, sparse, k=60, top_n=5)` scores each document as the sum of `1 / (k + rank)` over every list it appears in.
A document appearing in both lists therefore outranks a document that is rank-1 in only one list.
Ties keep first-seen order (dense list first).

### 4.5 Retriever seam (`src/retrieve/__init__.py:21`)

`make_retriever(client, collection, variant="hybrid")` returns a `(query, *, top_n=5)` callable over `dense`, `sparse`, or `hybrid`.
This callable is the seam the future graph retrieval node imports, so retriever variants can be swapped without rewriting the agent or eval harness.

## 5. Agent contracts (specified by tests, not yet implemented)

`src/agent/schemas.py` currently implements only `RetrievedChunk` (`doc_id`, `text`, `score`, `source_url`, `title`).
`src/agent/graph.py`, `state.py`, `verify.py`, `prompts.py`, and `agents.py` are empty stubs.
The contracts below are therefore requirements taken from `tests/agent/*`, not descriptions of existing code.

### 5.1 Schemas (`tests/agent/test_schemas.py`)

`Answer` carries `kind="answer"`, a non-empty `answer` string, `citations: list[str]`, and `confidence` bounded to `0-1`.
`Refusal` carries `kind="refusal"`, a `reason` enum, and a `message` that defaults to text mentioning consulting a dentist when omitted.
`AgentOutput` is a discriminated union on `kind` covering exactly `Answer` and `Refusal`.
`CitationCheck` carries `verified`, `cited_ids`, `retrieved_ids`, `fabricated_ids`, `matches`, `total`, and `coverage`.

### 5.2 Citation verification (`tests/agent/test_verify.py`)

Inline citation tokens take the form `[SRC:doc_id]`.
`extract_citations` parses every such token in order, including repeats.
`verify_citations(answer, retrieved)` checks each cited id against the retrieved set.
Zero citations or any fabricated id yields `verified=False` (fail closed).
`coverage` equals `matches / total`, and `strip_fabricated_tokens` masks only the bad tokens.

### 5.3 Graph (`tests/agent/test_graph.py`)

`build_graph(retriever=..., llm=..., confidence_threshold=...)` injects a `(query, *, top_n)` retriever and an LLM exposing `llm.with_structured_output(Answer)`.
`graph.invoke({"question": ...})` returns `{"response", "citation_check", "fused_chunks"}`.
Empty retrieval short-circuits before generation and returns a `Refusal` with `fused_chunks == []`.
Low confidence (below threshold) returns a `Refusal` with reason `INSUFFICIENT_CONTEXT`.
Any fabricated citation returns a `Refusal`.
The happy path returns an `Answer` with a verified citation check and the fused chunks attached.

## 6. Corpus (authoritative manifests, not this file)

The v1 corpus is 4 PDFs plus 11 HTML pages, all patient-education and openly licensed.
PDF provenance lives in `data/PROVENANCE.md`.
The 11 HTML URLs plus per-page filenames, licenses, review dates, and parsing notes live in `data/HTML_SOURCES.md` and are duplicated as `DEFAULT_HTML_URLS` in the pipeline.
US federal sources (HRSA, NIDCR, CDC) are public domain, and NHS UK pages require the attribution "Contains public sector information licensed under the Open Government Licence v3.0".
Triage guidance is UK NHS-based (111 / 999 / A&E) and is a documented limitation for a likely-US audience.
Insurance terminology is descoped for v1, and "what's a deductible"-style questions are `refuse_no_coverage` golden items.
Clinical guidelines and the CMS glossary were archived out of the v1 corpus and must not be re-added without a scope decision.

## 7. Stack and configuration

Python 3.12+ with `uv` is required, and `pyproject.toml` sets `pythonpath = ["."]` so imports read as `src.*`.
The pinned models are dense `sentence-transformers/all-MiniLM-L6-v2` and sparse `prithivida/Splade_PP_en_v1`, each referenced from exactly one constant in `src/ingest/vector_store.py`.
Runtime configuration comes from `.env` (gitignored, never committed), whose keys are listed in `sample.env`: `QDRANT_URL` / `QDRANT_API_KEY`, one generation provider (`BEDROCK_*` or `GROQ_API_KEY`), a distinct `JUDGE_MODEL_ID` for Ragas, and LangSmith tracing keys.
Known drift: `pyproject.toml` currently pins `copilotkit`, `ag-ui-langgraph`, `ddgs`, and `duckduckgo-search`, which `AGENTS.md` explicitly forbids without user approval.
Those dependencies must be justified and approved or removed; no new dependency may be added without explicit user approval.

## 8. Evaluation and ship gate

Retrieval must show hybrid (RRF) beating dense-only and BM25-only on recall@5, with the gap reported either way.
Ragas targets are faithfulness `>= 0.85`, context precision `>= 0.75`, and answer relevancy `>= 0.80`, with measured results recorded in the README once the harness exists.
Refusal correctness on trap questions is 100% with zero slack, and any confident non-refused trap answer blocks shipping regardless of all other numbers.
Latency target is P95 under 3 seconds, and cost per query must be documented at an assumed volume even when small.
The eval harness, golden set, and CI wiring are defined phase by phase in `TODO.md` and are not duplicated here.

## 9. Non-goals (v1)

Diagnosis or symptom-specific advice, real patient records / PHI, appointment booking, insurance-terminology coverage, voice, fine-tuning, and multi-lingual support are out of scope.
The parking lot (cross-encoder rerank, original dental-benefit glossary, US triage source, clinician-mode corpus, MCP exposure, front-desk dashboard, multi-turn memory) lives in `SCOPE.md` §9.
No FastAPI service exists yet (Phase 9.2 remains optional); a Streamlit demo UI ships in `src/ui/app.py` (Phase 9.1), deployed via `Dockerfile` to HF Spaces at port 7860.

## 10. File map

`src/ingest/` holds the write path (`document_parser.py`, `chunking_and_embedding.py`, `vector_store.py`, `ingestion_pipeline.py`).
`src/retrieve/` holds the read path (`base.py`, `dense.py`, `sparse.py`, `hybrid.py`, `__init__.py` with `make_retriever`).
`src/agent/` holds fusion plus the stubbed agent contracts (`fusion.py` implemented; `schemas.py` partial; `graph.py`, `state.py`, `verify.py`, `prompts.py`, `agents.py` specified by tests).
`src/eval/` is empty and planned per `TODO.md`.
`tests/ingest/`, `tests/retrieve/`, and `tests/agent/test_fusion.py` cover implemented code, while the remaining `tests/agent/*` files are the spec for the stubs.
