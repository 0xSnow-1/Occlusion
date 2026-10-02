# Research prompt: Occlusion deployment under a hard no-billing constraint

You are a deployment researcher. Your job is to answer one question with evidence: how does this project get a public, recruiter-clickable demo without spending money or registering billing info, and if that is impossible, what is the highest-conviction alternative.

## 1. Project context (read these before anything else)

- Repo: Occlusion, a chairside dental patient-education RAG assistant (Python 3.12, `uv`).
- `main` branch is V1-only and coherent: Q&A over a curated corpus, deterministic guardrail, fail-closed citation gates, Streamlit UI at `src/ui/app.py`, Gradio port at `src/ui/gradio_app.py` (mirrors the Streamlit UI exactly).
- 111 offline tests green (`uv run pytest tests/ingest/ tests/retrieve/ tests/agent/ -q`).
- Runtime needs: Python backend, torch plus sentence-transformers plus fastembed plus qdrant-client (roughly 2 to 4 GB RAM in practice), a prebuilt local Qdrant index (179 points, 1.4 MB on disk), embedding-model downloads at first boot (roughly 600 MB, one-time per fresh container), Bedrock credentials at runtime (`AWS_BEARER_TOKEN_BEDROCK`, `BEDROCK_MODEL_ID`, `BEDROCK_REGION`), generation via Bedrock Claude Haiku (API cost per query, not hosting cost).
- Key architecture facts: Qdrant runs in local path mode (single-process file lock, one accessor at a time), the index is gitignored and must be baked at build time or vendored, secrets must never enter the repo, cold starts are acceptable but multi-minute wakes are not demo-grade.
- Prior audit: `AUDIT_REPORT.md` (especially section 5, deploy decision). Prior deploy notes: `SHARED_CONTEXT.md` (Docker image verification, latency baseline). Deploy artifacts in repo: `Dockerfile` (HF Docker path), `spaces/zerogpu/requirements.txt` plus `spaces/zerogpu/README.md` (Space frontmatter), `src/ui/gradio_app.py`.

## 2. What was already tried (do not re-suggest these without new evidence)

Each entry below cost real effort. Treat them as settled unless the provider changed something after September 2026 with a primary-source changelog to prove it.

- Hugging Face Docker SDK: requires PRO (paywall introduced mid-2026, no announcement). Streamlit SDK retired entirely. Only Gradio, Docker, and Static remain. Static is free but has no backend.
- Hugging Face Gradio on CPU: also requires PRO. Only exception is Gradio on ZeroGPU for free accounts.
- Google Cloud Run: requires a billing account attached even to stay inside the free grant. Tried, blocked, abandoned.
- Modal: signup is free but only $1 of credit is usable until a payment method is on file; the advertised $30 stays locked behind billing info. Tried, blocked, abandoned.
- Hugging Face ZeroGPU with a Gradio port: fully built and pushed (`src/ui/gradio_app.py`, vendored 179-point index, secrets set). Killed at runtime by the supervisor: quote `No @spaces.GPU function detected during startup`. Root cause: ZeroGPU hardware mandates GPU-requesting code and this app is CPU-bound (local embeddings, Bedrock API generation). Wrapping CPU work in GPU decorators just to satisfy the supervisor was judged hacky and rejected. Lesson: ZeroGPU fits GPU-bound request functions, not persistent CPU chat servers.
- Solved along the way ( Mlore, not blockers): HF rejects binary pushes (the Qdrant `storage.sqlite` went up via the `git-xet` extension plus Git LFS, both installed user-local without sudo). Space `short_description` frontmatter limit is 60 characters. Template starter files must be deleted before pushing. The Space README frontmatter must point `app_file` at `src/ui/gradio_app.py`.

## 3. Hard constraints (non-negotiable)

- Zero money, zero billing info, zero credit cards. If a path needs any of these, even refundable holds, it is out. Say so in one line and move on.
- The demo must be clickable by a non-technical recruiter: public URL, no login, works from a phone browser.
- First-visit cold start under roughly one minute. Anything slower reads as broken to a hiring manager.
- Secrets (Bedrock token) must be settable without entering the repo. No exceptions.

## 4. Research tasks

### Task A: enumerate every remaining $0-no-billing host that could run this backend

- Check as of September 2026 or later, against primary sources only (pricing pages, official docs, dated changelog entries): Railway trial terms, Koyeb free tier (RAM ceiling is the key number), Render free tier (RAM ceiling), Fly.io (card requirement), Streamlit Community Cloud (RAM ceiling), Oracle Cloud free tier (card hold policy), GitHub Codespaces public ports (persistence story), Replit, PythonAnywhere, Hugging Face community or education grants, GitHub Student Pack style credit programs, AWS or GCP education programs that do not need billing, and any live alternative you find.
- For each candidate record: billing info required (yes or no, with source), RAM plus disk plus CPU ceilings, sleep and wake behavior, Docker support, secrets support, request timeouts, and estimated monthly cost at light demo traffic (a few dozen visits).
- Kill fast: the moment a candidate fails a hard constraint from section 3, record the exact failing fact with its source and stop analyzing that candidate.

### Task B: price the slim-down options honestly

- What would it take to fit a 512 MB to 1 GB free host: replacing local torch embeddings with an API embedding service, moving Qdrant to Qdrant Cloud free tier, dropping reranking or sparse vectors, splitting ingest offline from serving.
- For each change state what breaks or weakens in the portfolio narrative (local hybrid retrieval is currently a core differentiator), the engineering effort in days, and whether the resulting demo still demonstrates the claimed skills.

### Task C: answer the strategic question with hiring evidence, not vibes

- The repo owner believes most job postings require an actually deployed app rather than a toy demo. Test that belief: for junior and mid-level AI and data roles, what do hiring managers and recruiters actually open and weigh. Use primary or near-primary evidence (hiring-manager writeups, recruiter surveys, portfolio guides with stated methodology, dated 2024 or later). Forum anecdotes count only as color, never as proof.
- Rank these artifacts by hiring impact with reasons: live deployment, 2-minute demo recording, README quality, one-command local reproducibility, eval numbers and methodology writeup.
- Specify exactly what a demo recording must show and what the README structure must contain to maximize recruiter conversion if video-first wins.
- Deliver a verdict in one paragraph: deploy-first or video-first, with the single strongest reason.

## 5. Output format (follow exactly)

- Part 1: ranked options table with columns for host, billing needed, RAM, sleep behavior, effort, demo quality, and verdict. One row per candidate from Task A, including the killed ones with their killing fact.
- Part 2: slim-down analysis from Task B, or the sentence `No slim-down evaluated` with a reason.
- Part 3: the strategic verdict from Task C with cited evidence links and dates.
- Part 4: if deploy-first wins, exact step-by-step commands for the winner starting from this repo's `main` (assume Ubuntu plus `uv`, no sudo). If video-first wins, a shot list for the recording plus the README section outline.
- Rules for the whole report: every factual claim about a provider cites a primary-source URL plus the date you checked it. Distinguish one-time trial credits from recurring free tiers explicitly. Flag any claim you could not verify with the word UNVERIFIED. No invented free tiers. No paid options except a single clearly labeled `If billing ever becomes possible` appendix of at most three lines.

## 6. Failure shields (how not to waste this run)

- Do not recommend anything from section 2 without a dated primary source proving the blocker lifted.
- Do not confuse `free credits` with `no billing required`. They are different gates and this project fails the second one everywhere it has been tested.
- Do not propose architectures that change the eval story (different embeddings, different retrieval) without flagging in Task B that golden-set and Ragas numbers would need re-running.
- Verify version-sensitive claims (Gradio versions, ZeroGPU policies, free-tier RAM numbers) against current docs, never from memory. Your training data is stale on all three.
