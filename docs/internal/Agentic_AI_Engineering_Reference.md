# Agentic AI Engineering Reference Guide

**A practical operating system for learning and shipping AI systems in 2026**

This document consolidates the complete mindset, learning process, daily workflow, and concrete practices for becoming effective at AI engineering when you have no degree and are building projects to land roles. It is written as a single source of truth you can return to.

---

## 1. Core Mindset Shift

### Old paradigm (what creates impostor syndrome)
- “If I didn’t type every line myself, I don’t really know it.”
- “If I can’t read every line of syntax in the repo, I don’t have what it takes.”
- Competence = ability to recreate the implementation from memory.

### New paradigm (what actually matters)
You are the **intent + architecture + verification owner**.  
The agent is the **implementation engine**.

Understanding has layers:
1. **Intent / architecture** (highest value) — what the system should do and why.
2. **Behavioral / contract** — inputs, outputs, failure modes, acceptance criteria.
3. **Implementation / syntax** — exact library calls and idioms.

You are primarily responsible for levels 1 and 2. Level 3 is increasingly the agent’s job. You only go deep into syntax when something is broken, when a design decision depends on the details, or when you deliberately want to learn a pattern.

**Writing every parsing function, pipeline step, or boilerplate by hand is now mostly wasted motion** once you understand the shape of the solution.

### What competence looks like in 2026
- You can specify the right system.
- You can tell when the result is correct or incorrect.
- You can steer the agent to fix problems.
- You understand important trade-offs and failure modes.
- Over time you absorb common patterns through directed use.

Many strong engineers regularly ship code whose exact syntax they could not have written unaided that day. They still own the system.

---

## 2. Learning Process: “Learn Before You Do”

This is the most important section. Do not skip it.

### When you encounter a new topic (example: agent memory, RAG evaluation, tool use, multi-agent systems)

**Phase 0 – Orientation (do this before writing any code)**

1. **Get the landscape with an agent** (30–45 min)  
   Prompt something like:  
   > “Explain the current state of [topic] in 2026 for someone who will implement a minimal but real system this week. Cover core concepts, main approaches, key failure modes, important open-source systems, and how it is evaluated. Keep it practical.”

2. **Read 3–4 high-signal primary sources** (2–3 hours)  
   - Official docs or architecture overviews of leading systems.
   - One recent survey or strong paper introduction.
   - One practical implementation write-up or good README.
   - Benchmark or evaluation description so you understand how success is measured.

3. **Force yourself to articulate the problem** (30–45 min)  
   Write a short design brief in your own words:
   - What problem does this solve?
   - What are the minimum operations / components?
   - What does success look like? (Write concrete examples.)
   - How will I evaluate it?
   - Key design decisions I will have to make.

   Only when you can explain the above without looking at notes are you ready to build.

**Keep a running note file** while learning:
```markdown
## Core concepts I now understand
- 

## Key design decisions I will have to make
- 

## Open questions / things I still don’t get
- 

## Minimal viable architecture I am leaning toward
- 
```

This conceptual ownership is what prevents the later feeling of “the system works but I don’t understand the syntax → therefore I am a fraud.”

---

## 3. How to Use Courses

Courses (Anthropic, DeepLearning.AI, etc.) are for **concepts and mental models**, not for typing practice.

### Correct process
1. Watch / read for the *why* and *what* (patterns, failure modes, design principles).
2. Immediately turn every major concept into a small agent-driven experiment.
3. Give the agent a precise task that forces the new idea:
   - “Implement a minimal ReAct agent with three tools… show the full trajectory.”
   - “Implement the evaluation pattern from the course on this small golden set.”
4. Require demonstration of behavior (run it, show outputs, show trajectories).
5. Explore variations with the agent.
6. Only write code by hand when you are deliberately studying a low-level detail or the agent keeps failing on something subtle.

### Why this is better
- You practice the actual job skill: specifying intent, reviewing output, verifying behavior.
- You get far more volume of practice.
- You spend attention on architecture and evaluation instead of syntax.

**Rule**: After 20–40 minutes of course material → pause → spin up an agent → implement and verify the concept.

---

## 4. Handling “I Don’t Understand the Syntax”

When the agent produces working code whose syntax is opaque:

1. **First check the contract / behavior**, not the syntax.  
   Does it do what you asked? Run the verification you defined.

2. **Ask the agent to explain**:
   - “Explain this section line by line and why this library call is used.”
   - “What would break if we changed X?”
   - “Highlight the 3–4 most important lines.”
   - “Is there a simpler correct way to write this?”

3. **Only dig deeper when it matters**  
   - Working + sound design → note the pattern and move on.  
   - Suspicious or critical path → force a clearer rewrite or alternative.  
   - Recurring patterns → eventually internalize them through repetition.

4. **Optional lightweight understanding log**  
   For each major piece: what it is responsible for, key design decision, one thing you didn’t understand and how it was explained.

**Hard rule**: You are not allowed to rewrite working agent code by hand just because you don’t fully understand the syntax. Only rewrite if behavior is wrong, design is poor, or you need a clearer version for deliberate learning.

---

## 5. End-to-End Agentic Workflow (Your Tools)

### Your stack
- **Herdr** — terminal workspace manager for AI agents (persistent sessions, panes, agent state awareness: working / blocked / idle).
- **Treehouse** — manages a pool of git worktrees so each agent gets an isolated copy of the repo.
- **no-mistakes** — validation gate (rebase → review → test → document → lint → push → PR → CI) with auto-fix and ask-user findings.
- **opencode** (or equivalent) — the coding agent you run inside the panes.

### Daily startup
```bash
herdr
```

One-time per repo:
```bash
treehouse init
```

In separate panes:
```bash
# Pane 1 – main feature work
treehouse get
git switch -c feature/chunking
opencode

# Pane 2 – evals / tests
treehouse get
git switch -c feature/evals
opencode

# Pane 3 – docs / prompts / secondary work
treehouse get
git switch -c feature/prompts
opencode
```

**Important:** `treehouse get` creates a worktree but does NOT create a branch. You're in a detached HEAD state. Always run `git switch -c <branch-name>` after getting a worktree, or no-mistakes will fail with "detached HEAD" error.

### Giving tasks
Give each agent **one clear, verifiable task**. Never “make it better.”

Example:
> “Implement the document ingestion pipeline for PDFs and Markdown. Use [library]. Clean text, chunk with recursive splitting (size 512, overlap 50), preserve metadata. Expose `process_documents(path) -> list[Document]`. Include CLI entry point and unit tests on a sample. After writing, run the tests and show output.”

### When an agent finishes a unit of work
1. Review behavior and API (not every line of syntax).
2. Ask for explanations of opaque parts.
3. Put it through the validation pipeline:

```bash
# You should already be on a branch from treehouse get + git switch -c
no-mistakes axi run --intent "implemented X for Y"
no-mistakes axi status
# respond to gates
no-mistakes axi respond --action approve
# or
no-mistakes axi respond --action fix --findings F1,F2
# or with guidance
no-mistakes axi respond --action fix --findings F1 --instructions "your guidance"
no-mistakes axi sync
```

4. Only merge what passes the gate **and** that you have personally verified against your acceptance criteria / golden examples.

### After validation
```bash
no-mistakes axi sync
git push origin feature/...
gh pr create ...
# merge when ready
```

Clean up worktrees you are done with:
```bash
treehouse return
```

---

## 6. Concrete Project Example: Long-Term Agent Memory

This is the full pattern applied to a high-value AI engineering topic.

### Why this project
Long-term memory for agents is one of the highest-signal topics in 2026. Agents that forget between sessions are still the default. Systems that improve with experience (and can be measured) are what companies care about.

### Learning phase (do this first)
1. Ask an agent for the 2026 landscape of agent memory (categories, failure modes, systems like Mem0 / Zep / Letta-style, evaluation benchmarks).
2. Read 3–4 primary sources.
3. Write your own design brief: minimum operations (`add`, `search`, `get_relevant_context`, conflict handling), concrete multi-session examples, how you will evaluate success.
4. Only then start implementation.

### Implementation phases (using your workflow)
- **Core memory module** (buffer + vector store + simple fact/entity store + write-path logic) → no-mistakes.
- **Integration into a simple agent loop** that actually uses the memory tools and injects context → no-mistakes.
- **Evaluation harness** (10–15 multi-session golden scenarios + metrics + runnable report) → no-mistakes. This is what makes it portfolio-grade.
- Polish, README with architecture + failure analysis, optional demo UI.

Every chunk of work follows: Treehouse isolation → precise task → agent implements → you verify behavior + ask explanations → no-mistakes gate → sync / PR.

---

## 7. RAG Evaluation Metrics (Study Reference)

When you study evaluation (or any metrics-heavy topic), learn the concepts first, then implement a working harness.

### The core four (RAGAS-style)

| Metric              | What it measures                                      | Failure it catches                  | Layer      |
|---------------------|-------------------------------------------------------|-------------------------------------|------------|
| **Faithfulness**    | Are claims in the answer supported by retrieved context? | Hallucinations / invention         | Generation |
| **Answer Relevancy**| Does the answer address the actual question?          | Off-topic, verbose, or evasive answers | Generation |
| **Context Precision**| Of the retrieved chunks, how many are useful (and ranked well)? | Noisy retrieval, poor ranking     | Retrieval  |
| **Context Recall**  | Did we retrieve the information needed to answer?     | Missing relevant chunks            | Retrieval  |

**How they work (simplified)**:
- **Faithfulness**: Extract atomic claims from the answer → check each against context with an LLM judge → fraction supported.
- **Answer Relevancy**: Generate hypothetical questions the answer could be answering → measure similarity to the original question.
- **Context Precision**: LLM judges usefulness of each retrieved chunk; higher ranks of useful chunks score better.
- **Context Recall**: Check whether the information required by a reference / ground-truth answer is present in the retrieved context.

### Practical rules
- Evaluate retrieval and generation separately so you know which half is broken.
- Faithfulness only checks grounding in *retrieved* context — a faithfully summarized wrong or stale document still scores high.
- Prefer a small set of high-signal metrics + human calibration over a long list of generic scores.
- Build a golden set. Run the metrics after every meaningful change. Treat regressions like test failures.
- LLM-as-judge has biases (verbosity, position). Calibrate against human labels on a sample.

### Learning → building loop for metrics
1. Study the definitions and what each metric isolates.
2. Immediately implement a small evaluation script on a tiny golden set using an agent.
3. Run it, read the failure cases, improve the system or the judge prompts.
4. This evaluation harness itself becomes resume material.

---

## 8. Resume & Portfolio Reality

If you understand a concept and ship a working end-to-end system that uses it, **you put it on your resume**. That is what strong candidates do.

Hiring managers care about:
- Evidence you understand important concepts deeply enough to apply them.
- Working systems (not tutorials).
- Ability to evaluate whether something actually works.
- Clear thinking about trade-offs and failure modes.

They do **not** care whether you typed every line by hand.

### Strong resume pattern
Lead with the project and outcome, then list the relevant stack:

> Built a hybrid agent memory system (vector + structured facts) with multi-session evaluation harness. Achieved X% fact recall on custom golden set. Used Qdrant, sentence-transformers, custom write-path filtering, and LLM-as-judge evaluation.

A long list of libraries with no real systems is noise. A small number of defended projects with the stacks that powered them is signal.

---

## 9. Daily & Project Operating Rules (Summary)

1. Learn concepts first. Force yourself to articulate the problem before coding.
2. Use courses for mental models, then immediately practice through agents.
3. Specify clearly → agent implements → you verify behavior → ask for explanations of opaque syntax → only rewrite when necessary.
4. Run every meaningful unit of work through your validation gate (no-mistakes).
5. Keep agents isolated (Treehouse) and organized (Herdr).
6. Evaluation is not optional. Golden sets and measurable outcomes turn demos into portfolio pieces.
7. The impostor feeling that appears when syntax is opaque is normal and does not mean you lack competence. Follow the process above.
8. Ship real systems. Explain design decisions and failure analysis. That is what gets interviews.

---

## 10. Quick Command Reference

**Herdr**
- `herdr` — launch / attach
- `herdr status`

**Treehouse**
- `treehouse init`
- `treehouse get` → then run `git switch -c <branch-name>` (creates branch)
- `treehouse return`
- `treehouse status`

**no-mistakes**
- `no-mistakes axi run --intent "..."`
- `no-mistakes axi status`
- `no-mistakes axi respond --action approve`
- `no-mistakes axi respond --action fix --findings F1,F2`
- `no-mistakes axi respond --action skip`
- `no-mistakes axi logs --step review --full`
- `no-mistakes axi sync`
- `no-mistakes axi abort`

---

**This is the reference.**  
Return to the learning process section whenever you start something new. Return to the workflow section every day you build. Return to the metrics and evaluation section whenever you need to prove a system works.

The goal is not to type the fastest.  
The goal is to most reliably turn clear intent into correct, evaluated systems using agents as force multipliers.
