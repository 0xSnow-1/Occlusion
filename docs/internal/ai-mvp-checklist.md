# AI Engineering MVP Checklist
### For portfolio projects — and for building the instincts a Forward Deployed Engineer needs

---

## Why this is different from a normal software MVP

A regular MVP just has to prove people want the thing. An **AI MVP has to prove two things**: that the problem/solution fit is real, AND that the AI component behaves predictably enough to trust, at a cost that makes sense. Decisions about data, model choice, and failure handling are structural — they're expensive to unwind after the fact, so you make them deliberately, early, instead of discovering them under pressure.

For a *portfolio* project specifically: MVP doesn't mean "smallest thing that works." It means **the smallest deployed, evaluated, documented system that proves you can take something from prototype to production and know why you stopped.** A notebook that works on your laptop is a prototype, not an MVP — no matter how good the model output looks.

---

## Part 1 — The Readiness Checklist

Score yourself honestly. If every box in a section is checked, that layer is MVP-complete. If a whole project checks every box below, it's ready to ship and move to the next one — anything beyond this is polish, and polish belongs in your "v2" notes, not in the reason you keep delaying deployment.

### A. Problem & Scope
- [ ] I can state the user, the workflow, and the pain point in **one sentence**, without needing the word "AI" to make it sound impressive
- [ ] I checked whether a non-AI approach (rules, regex, a form, a classifier) would solve 80% of it — and can explain why AI earns its complexity here
- [ ] I've defined "good enough" in **numbers**: target accuracy/latency/cost, and the threshold below which I'd kill the feature

### B. Data
- [ ] I know exactly where my data comes from and its *real* quality — not the quality I hoped it would have
- [ ] I have a small, fixed **golden set** (20–100 examples) that every change gets tested against

### C. Architecture
- [ ] I chose prompt-only vs. RAG vs. fine-tune deliberately, starting from the simplest option and only adding complexity where the simple one demonstrably failed
- [ ] I picked a model based on the task, not hype, and estimated **cost per request at realistic usage volume**

### D. Evaluation — the part most portfolios skip entirely
- [ ] I've done manual error analysis on at least 50–100 real outputs/traces
- [ ] I have at least one automated eval (code-based or LLM-as-judge) that runs before I ship a change
- [ ] I can point to a number that improved because of an iteration — not just "it feels better now"

### E. Reliability & Guardrails
- [ ] There's an explicit fallback for when the model is wrong or unsure — it fails closed (refuses/flags) rather than confidently guessing
- [ ] Errors, rate limits, and timeouts are handled, not just the happy path
- [ ] There's logging or tracing so you can see what happened after the fact

### F. Deployment
- [ ] It's live at a URL a stranger can hit — not "runs on my machine"
- [ ] There's a health-check endpoint, and it survives a basic load test
- [ ] Secrets aren't in the repo; there's a one-command way to run it locally

### G. Documentation — this IS the interview
- [ ] README covers: problem, user, demo link, architecture diagram, eval results, how to run, and the tradeoffs you made and why
- [ ] You can explain in 2 minutes what you'd build next — and why you stopped here instead

### H. Kill / Ship Criteria — decide this BEFORE you build more
- [ ] You defined, in advance, what evidence means "ship it" vs. "keep iterating" vs. "this isn't worth finishing"
- [ ] You have an explicit stop-building trigger, e.g. *"once eval score crosses X and it's deployed with basic monitoring, I stop and start the next project."*

---

## Part 2 — Why this is FDE practice, not a detour

A Forward Deployed Engineer is, functionally, someone who takes a capable model, connects it to a client's real (messy) systems, tests against real data, and iterates based on what breaks — then feeds what they learned back into the product. That's the exact same loop as sections A–H above, just pointed at your own project instead of a client's. Every portfolio project that forces you to define scope, measure quality with real evals, and ship a working thing under a deadline is direct reps for that job — probably more relevant than any tutorial.

---

## Part 3 — Coding Agent Audit Prompt

Paste this into Claude Code, Cursor, or any agent with repo access once you *think* a project is done. Let it check the evidence instead of your gut.

```
You are auditing this repository against an "AI MVP readiness checklist."
Inspect the actual code, tests, README, and config — not just claims in comments.
For each item, respond with: PASS / PARTIAL / FAIL, one-line evidence (file:line, or
"not found"), and if PARTIAL/FAIL, the single smallest fix that would close the gap.

[Problem & Scope]
1. Is there a one-sentence problem statement (user + workflow + pain point) documented?
2. Is there evidence a simpler non-AI approach was considered and rejected, with a reason?
3. Are target accuracy/latency/cost thresholds documented anywhere?

[Data]
4. Is there a fixed evaluation/test dataset (golden set) checked into the repo?
5. Is data provenance and quality documented?

[Architecture]
6. Is the model/approach choice (prompt-only / RAG / fine-tune) justified anywhere?
7. Is there any cost-per-request estimate or token usage tracking?

[Evaluation]
8. Is there an automated eval script/suite that runs against the golden set?
9. Is there evidence of manual error analysis (notes, categorized failure types, etc.)?
10. Does the eval run in CI, or before merges/deploys?

[Reliability]
11. Is there explicit error/fallback handling for model failures, timeouts, bad input?
12. Is there logging or tracing of inputs/outputs?

[Deployment]
13. Is there a live deployed URL, Dockerfile, or clear deploy instructions?
14. Is there a health-check endpoint?
15. Are secrets/API keys excluded from version control (.env present, in .gitignore)?

[Documentation]
16. Does the README include: problem, demo link, architecture, eval numbers, how-to-run,
    and tradeoffs made?

[Kill/Ship Criteria]
17. Is there a documented "definition of done" or "what I'd build next" section?

Then output:
- A summary table: item | status | evidence
- Overall verdict: "MVP-ready" / "close — fix these N items" / "not MVP yet"
- The single highest-leverage next action if not ready
```

Run this on a project you *think* is finished before you start a new one. If it comes back "not MVP yet," fix only what's flagged — don't use it as an excuse to add features.

---

## Part 4 — Sources used in this research

- **Hamel Husain's blog** (hamel.dev) — free, written by someone who's trained engineers at OpenAI, Anthropic, and Google on this exact problem. Start with "Your AI Product Needs Evals" and the "minimum viable evaluation setup" FAQ answer.
- **Boldare's 12-decision AI MVP checklist** — the clearest breakdown of the *structural* decisions (data, architecture, risk, governance) that are expensive to unwind later.
- **Blockchain Council's AI portfolio guide** — a practical README template and repo structure recruiters actually respond to.
- Forward Deployed Engineer role descriptions from Anthropic, OpenAI, and Palantir — used to confirm the skill overlap between "ship an AI MVP" and "FDE work."
