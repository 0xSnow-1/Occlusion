# Dental Knowledge RAG Agent — MVP Project Plan

**For:** Ahmed, 23, self-taught Python, no degree, targeting an AI engineering role
**Goal:** A portfolio project that proves production RAG + agent skills, no deployment budget required

---

## 1. What you're building, in one sentence

*A LangGraph agent that answers dental-health questions by retrieving from a curated corpus (guidelines, patient-education docs, dental association materials) using hybrid search (BM25 + dense), fuses results with Reciprocal Rank Fusion, and returns a structured, cited answer that refuses to answer when it isn't confident — with every change measured against a golden eval set.*

That sentence is also your README opener. Section G of your checklist wants exactly this.

---

## 2. Why this project, backed by data (not vibes)

I pulled the job-market analysis from the field guide you linked (895 AI-engineer postings, Jan 2026, builtin.com data) and cross-checked it against your plan point by point:

| Your plan | Job market signal |
|---|---|
| RAG as the core pattern | RAG appears in 35.9% of all AI-engineering postings — the single most common skill in the dataset |
| RAG + agents together | 70%+ of what AI-first roles actually build |
| LangGraph | 8.0% of postings (72 jobs) name it specifically; it's the #2 framework after LangChain |
| Vector DB (Qdrant) | 97 jobs mention vector databases explicitly |
| Evaluation (Ragas) | Only 39.6% of roles require it — the guide calls this **the emerging differentiator**, because RAG/agents are becoming baseline while measurement is not |
| Fine-tuning | Not needed — only ~20% of roles expect any fine-tuning, and it's explicitly called a specialization, not a core skill. Your instinct to skip it is correct |

And directly from the portfolio-strategy page of that same guide: a **"RAG-based FAQ/Support system"** with hybrid retrieval and reranking is named as *the* most in-demand project pattern, and a project with **"hybrid retrieval, cross-encoder reranking, confidence thresholds, precision@k metrics, and cost analysis"** is cited as the kind that scored 9/10 in a real interview. You are not building a generic tutorial clone — you're building the specific thing hiring managers say they want to see.

**Why dental health as the domain (not "RAG chatbot #4,891"):**
- It's a real, bounded domain (professional guidelines, patient FAQs) — good for a small, high-quality golden set (checklist section B).
- It forces you to think about **failure mode design** — a wrong dental answer isn't just embarrassing, it's a stated reason to fail closed, which directly demonstrates checklist section E (guardrails) instead of just talking about it abstractly.
- Domain-specific RAG (medical/legal/finance) is explicitly called out in the job data as the main *reason* fine-tuning gets used later — so even without fine-tuning now, you're building instincts for that track.

One honest caveat: don't market this as medical advice software. Frame it as a **grounded information-retrieval assistant over public dental-health documentation**, not a diagnostic tool. This isn't just a legal nicety — it's a *better engineering story*: "I explicitly scoped this system to refuse diagnosis and defer to a professional" is a stronger interview answer than pretending otherwise, and it's literally what checklist section E asks you to demonstrate.

---

## 3. System design

```
                         ┌─────────────────────────┐
   User question ───────▶│   LangGraph entry node   │
                         └────────────┬─────────────┘
                                      │
                          query preprocessing/rewrite
                                      │
                 ┌────────────────────┴────────────────────┐
                 ▼                                          ▼
      Qdrant dense search                         Qdrant sparse search
      (cosine, embedding model)                    (BM25, IDF-weighted)
      top_k = 20                                   top_k = 20
                 │                                          │
                 └────────────────────┬────────────────────┘
                                      ▼
                     Reciprocal Rank Fusion (RRF)
                     score(d) = Σ 1/(k + rank_i(d)), k≈60
                                      │
                          (optional) cross-encoder rerank
                          top_n = 5
                                      ▼
                  Chunks assembled with anchor tokens
                  [SRC:doc_id] preceding each chunk
                                      ▼
                       LangGraph agent node → LLM call
                  instructed to cite [SRC:doc_id] inline
                                      ▼
                Pydantic schema validates output:
                { answer, citations: [doc_id...], confidence }
                                      ▼
              Post-processing: verify every citation ID
              actually exists in the retrieved set
              (catches "citation-shaped hallucination")
                                      ▼
           confidence/coverage below threshold?
           → fail closed: "I don't have enough grounded
             information to answer this reliably — please
             consult a dentist" (never guess on health claims)
                                      ▼
                        Answer + real source links returned

   Cross-cutting, every step:
   - LangSmith traces (latency, tokens, cost per call)
   - Ragas eval harness (faithfulness, context precision/recall,
     answer relevancy, + your own citation-accuracy check) runs
     against a fixed golden set before any change ships
```

**Why each piece earns its place (this is your "prompt-only vs RAG vs fine-tune" justification for checklist section C):**
- **Hybrid retrieval over dense-only**: dense embeddings miss exact terminology (drug names, procedure codes, specific condition names) that dental documents are full of; BM25 catches those. This is the textbook case for hybrid search, not just a resume keyword.
- **RRF over score-blending**: dense (cosine) and BM25 (unbounded) scores live on different scales that shift per query — a fixed weighted average is unreliable without calibration data you don't have yet. RRF sidesteps this by fusing on rank, not raw score, which is exactly why it's the default fusion method in Qdrant, Elasticsearch, Azure AI Search, and Weaviate.
- **Citation anchoring**: embedding `[SRC:doc_id]` tokens into the prompt and instructing the model to emit them inline, then verifying each ID against what was actually retrieved, is a cheap, effective way to catch "fluent but unsupported" citations — a well-documented failure mode (citation accuracy in ungrounded RAG systems averages only ~65–74% without this kind of check).
- **Pydantic structured output**: guarantees your API always returns a parseable `{answer, citations, confidence}` object instead of you regex-parsing free text — and it's the pattern LangGraph's own docs recommend for agent output.
- **Fail-closed on low confidence**: this is checklist section E, made concrete. A health-adjacent agent that confidently guesses is a liability; one that says "I don't know, ask a professional" is a feature you can defend in an interview.

---

## 4. Curated resources (minimized — one best source per topic)

1. **Qdrant — Hybrid Queries (official docs)**: the canonical reference for how RRF/DBSF fusion actually works in Qdrant, with the prefetch pattern you'll use.
   https://qdrant.tech/documentation/search/hybrid-queries/

2. **Qdrant — Hybrid Search with Reranking (tutorial)**: end-to-end walkthrough — dense + BM25 prefetch, RRF fusion, then reranking. Closest thing to a template for your retrieval layer.
   https://qdrant.tech/documentation/tutorials-search-engineering/reranking-hybrid-search/

3. **RRF explained, with the formula and intuition**: short, clear, includes the original 2009 Cormack/Clarke/Buettcher paper reference if you want to go deeper.
   https://blog.serghei.pl/posts/reciprocal-rank-fusion-explained/

4. **LangChain/LangGraph — Structured Output (official docs)**: how `create_agent` + Pydantic schemas work together, including the `structured_response` state key you'll use.
   https://docs.langchain.com/oss/python/langchain/structured-output

5. **Ragas — Evaluate a simple RAG system (official getting-started guide)**: faithfulness, context precision/recall, answer relevancy — the exact metrics for your eval harness.
   https://docs.ragas.io/en/stable/getstarted/rag_eval/

6. **Eugene Yan — Patterns for Building LLM-based Systems**: the seven core patterns (evals, RAG, guardrails, defensive UX, etc.) — good for the "why AI earns its complexity here" and "trade-off fluency" parts of interviews.
   https://eugeneyan.com/writing/llm-patterns/

7. **Hamel Husain — Your AI Product Needs Evals**: the piece the field guide cites repeatedly as the reason evaluation is the differentiator. Read this before you write your eval harness, not after.
   https://hamel.dev/blog/posts/evals/

8. **AI Engineering Field Guide — Portfolio project ideas + what hiring managers actually look at**: your source repo, specifically the section on README writing and the "original project vs. tutorial" distinction — read this before you write a single line of code.
   https://github.com/alexeygrigorev/ai-engineering-field-guide/blob/main/portfolio/README.md

That's 8. I cut the ones that would've been redundant with what you already have (LangGraph general docs, Ragas conceptual overview, generic "what is RAG" explainers) — you don't need more surface area here, you need to build.

---

## 5. Your MVP checklist, filled in for this project

**A. Problem & Scope**
- One sentence: see section 1 above.
- Non-AI alternative considered: a keyword-only FAQ search (Ctrl+F basically) would handle exact-match questions but fails on paraphrased or multi-part questions — which is most of what people actually ask. That's your justification for going past a simple search.
- "Good enough" numbers to define *before* you build: e.g. faithfulness ≥ 0.85, context precision ≥ 0.7, citation accuracy ≥ 90% (every cited source must actually support the claim), p95 latency under some number you pick based on your LLM provider.

**B. Data**
- Source: pick 1–2 real, licensable corpora — dental association patient-education pages, public oral-health guideline PDFs (WHO, CDC, or a national dental association). Document provenance honestly in the README (what's in there, what isn't, how current it is).
- Golden set: 20–100 question/answer/source-doc triples, written by you, not generated wholesale by an LLM (some LLM-assisted generation is fine, but you should read and correct every one — this is also your first manual error-analysis pass).

**C. Architecture** — see section 3. Document the prompt-only vs. RAG vs. fine-tune decision explicitly in the README (checklist wants this on paper, not just in your head).

**D. Evaluation**
- Manual error analysis on 50–100 real traces before you trust any automated metric — do this first, it's what teaches you what "good" looks like for this specific corpus.
- Ragas metrics (faithfulness, context precision/recall, answer relevancy) plus your own citation-accuracy check (does every cited doc_id actually appear in the retrieved set, and does the sentence it's attached to actually follow from that chunk).
- Track one number over iterations — e.g. faithfulness score before/after adding the reranker — so you have a concrete "here's what improved and why" story for interviews.

**E. Reliability & Guardrails**
- Fail-closed below your confidence/coverage threshold (section 3).
- Explicit refusal for diagnostic/prescriptive questions ("what medication should I take for X") vs. informational ones ("what is X procedure") — this distinction is itself a good design decision to document.
- Handle empty retrieval results, API timeouts, and malformed LLM output (Pydantic validation failure) without crashing.

**F. Deployment (zero-budget version)** — see section 6 below.

**G. Documentation** — the README structure from the field guide: problem, demo link, architecture diagram, eval numbers (with before/after), how to run, and the tradeoffs you made and why. Skip the AI-generated README smell — write it yourself, or heavily edit.

**H. Kill/Ship criteria** — decide *before* you build more: e.g. "once faithfulness crosses 0.85 and citation accuracy crosses 90% on the golden set, with a working Streamlit/Gradio demo and CI running the eval suite — I stop and start the next project." Write this down now, not after you're 3 weeks in.

---

## 6. Zero-budget stack

You don't need to skip deployment — you need to pick the free tiers that don't expire mid-project:

| Layer | Free option | Notes |
|---|---|---|
| Vector DB | Qdrant Cloud free tier | 0.5 vCPU / 1GB RAM / 4GB disk, permanent, ~1M 768-dim vectors — plenty for a curated dental corpus. Suspends after 1 week of inactivity, deletes after 4 — just ping it periodically or re-activate before a demo/interview. |
| LLM (generation) | Google AI Studio (Gemini API free tier) or Groq (fast open-weight inference) | Both have genuinely usable free tiers as of 2026; pick one with structured-output/tool-calling support since you're using Pydantic schemas. |
| Embeddings | A local `sentence-transformers` model via FastEmbed, or Qdrant's free cloud inference | Avoids per-embedding API cost entirely if you self-host the embedding model. |
| Demo/UI | Hugging Face Spaces (free CPU tier) or Streamlit Community Cloud | HF Spaces free CPU is unmetered and permanent for light traffic — this is the "live at a URL a stranger can hit" checklist item, without needing a backend host. |
| Backend (if you separate API from UI) | Render free tier (spins down on inactivity — fine for a portfolio demo you ping before interviews) | Only needed if you want a real FastAPI service behind the demo rather than everything in one Streamlit/Gradio app. |
| Observability | LangSmith free tier | You already have this. |
| Evaluation | Ragas (open source, no cost) | You already have this. |
| CI/CD | GitHub Actions (free for public repos) | Run your Ragas suite on every push — this alone checks 3 checklist boxes at once. |

This gets you a live demo URL, a real vector DB, real LLM calls, tracing, and CI — for $0, with no card required anywhere in the stack.

---

## 7. Frontend vs. backend: what the data says

You asked directly whether to pick up React/TypeScript/shadcn now, or stay backend-focused (observability, evals, quant engineering). Here's what the job-market analysis actually shows:

- **93.1% of AI-first roles require skills beyond GenAI** — but the breakdown matters: GenAI + Ops (Docker/K8s/CI/CD) appears in 72% of roles, GenAI + web skills in only 49.1%. Backend/ops is the more universal add-on, not frontend.
- **React appears in 132/895 jobs overall (14.7%)**, and specifically **14.2% of AI-first roles vs. 20.8% of AI-support roles** — frontend is more associated with the *supporting* platform/tooling roles than the AI-first roles you're targeting.
- **Only 21.6% of AI-first roles need genuinely full-stack (both frontend and backend) skills** — the majority need backend depth, not full-stack breadth.
- Meanwhile **evaluation skills sit at just 39.6%** and are explicitly called "the differentiator" — this is a smaller, more valuable gap than frontend skills, which are already common knowledge among bootcamp grads.

**My read, given your actual constraint (land a role fast, currently Python-only):** stay backend + evals + observability for this project and the next 1–2 after it. Use Streamlit or Gradio (pure Python) for your demo UI — it satisfies the "live URL a stranger can hit" requirement without costing you weeks learning React. Depth in retrieval architecture, evaluation design, and cost/latency reasoning is what the data says separates candidates in interviews; a polished frontend does not show up in that list at all.

**When React/TypeScript becomes worth it:** later, if you specifically start targeting "AI-support" or full-stack AI-product roles (which do skew more frontend), or once you have 2–3 strong backend projects and want a portfolio site that showcases them well. It's not wasted time — TypeScript alone shows up in 23.4% of all postings — it's just not your highest-leverage next move given where you are now.

---

## 8. Suggested build order

Rough sequencing, not a rigid schedule — the field guide's own advice is 1–2 weeks per focused project rather than one giant one, but since this is a single project, break it into these phases and *treat each as a checkpoint*, not a monolith:

1. **Data + golden set first.** Before any retrieval code: pick your corpus, write 20–30 golden Q&A pairs by hand. You cannot evaluate what you haven't defined.
2. **Dense retrieval only.** Get a basic Qdrant collection + cosine search working end to end, even with a mediocre prompt. This is your baseline.
3. **Add BM25 + RRF.** Now you can measure whether hybrid actually beats dense-only on your golden set — this comparison *is* your first real eval story.
4. **LangGraph orchestration + Pydantic structured output + citation anchoring.** Wrap the retrieval in an agent, enforce the schema, add the citation-verification post-processing step.
5. **Ragas harness + LangSmith tracing, wired into GitHub Actions.** Now every future change is measured, not vibes.
6. **Guardrails and fail-closed behavior.** Add the confidence threshold and refusal logic — test it deliberately with adversarial/out-of-scope questions.
7. **Demo UI + deploy to HF Spaces/Streamlit, write the README.** Last, not first — the README is easiest to write once the system actually works.
8. **Run the Part 3 audit prompt from your own checklist** against the finished repo before calling it done.

---

## 9. Reusable session-starter prompt

Paste this at the start of any future planning session so you don't have to retype your context:

```
I'm Ahmed, 23, no degree, self-taught, and Python is currently my only
language. I'm building AI engineering portfolio projects to land an AI
engineering role — no formal CS background, so my projects have to do
the talking.

Constraints and preferences:
- I don't use coding agents (Cursor/Claude Code/etc.) as a primary builder.
  I want to solve problems myself and only invoke an agent when I'm
  genuinely stuck, so treat me as wanting to learn hands-on, not
  auto-generate the project.
- No budget for paid deployment/infrastructure. I need free-tier options
  or a way to make the project robust enough to demo without deploying,
  even though I know deployment is the norm.
- I already use LangSmith for observability and Ragas for evaluation —
  don't re-explain these from scratch, just tell me how to apply them
  to the specific project.
- I follow an "AI MVP Checklist" (attached/described separately) that
  scores readiness across: Problem & Scope, Data, Architecture,
  Evaluation, Reliability & Guardrails, Deployment, Documentation, and
  Kill/Ship Criteria. Map any project plan you give me onto this
  checklist explicitly.
- I reference alexeygrigorev's AI Engineering Field Guide
  (https://github.com/alexeygrigorev/ai-engineering-field-guide) for
  real job-market data — pull current data from it (skills analysis,
  portfolio guidance, get-hired advice) rather than assuming, since it's
  actively updated.

What I need from you for a new project:
1. An honest assessment of whether the project idea is valuable and why,
   backed by current job-market/industry data, not assumptions.
2. A concrete system design / architecture, with reasoning for each
   component choice (why this approach over the simpler alternative).
3. A short, curated list of the best reference URLs for the specific
   techniques involved — minimized, not exhaustive. I don't want a
   reading list, I want the 5-8 best links.
4. The MVP checklist mapped onto this specific project, section by
   section.
5. A zero-budget stack recommendation (free tiers, self-hosted options).
6. Where relevant: whether I should pick up any adjacent skill (e.g.
   frontend, a new language) given my goal of landing a role as fast as
   possible — backed by the same job-market data, not general advice.
7. At the end, give me an updated version of this exact prompt template
   so I can reuse it next time, adjusted for whatever changed.

Here's the project idea I want to plan: [DESCRIBE YOUR NEW PROJECT IDEA HERE]
```

---

*Sources used: alexeygrigorev/ai-engineering-field-guide (role/skills analysis, portfolio guidance, get-hired data — Jan 2026 snapshot, 895 postings), Qdrant official docs, LangChain/LangGraph official docs, Ragas official docs, Hamel Husain (hamel.dev), Eugene Yan (eugeneyan.com), and current (2026) free-tier documentation for Qdrant Cloud, Hugging Face Spaces, and Render.*
