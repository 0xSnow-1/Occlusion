# Occlusion audit: recruiter-ready v1

Date: 2026-09-15, corrected 2026-09-16 and 2026-09-19.
Scope: full codebase audit against README claims for a recruiter-runnable v1.
Method: repo evidence only (code, tests, docs, git status), per `SKILL (7).md` workflow.

Line framing (correction 2026-09-16): `main` is V1-only (Q&A, guardrail,
Gates 0-3, Streamlit UI; no booking, no callbacks, no scoreboard) with 111
offline tests green. V2 deltas plus the tests totaling 136 live on unmerged
`feature/New-v2`. An early draft of this report mixed the two lines; numbers
below are the corrected `main`-line ones.

## Verdict

Verdict: shippable except the public demo URL.
Core engineering is real (111/111 offline green; 78-item golden set loads;
hybrid RRF plus fail-closed gates pinned by tests).
B1-B5 fix branches all merged to `main`. Remaining P0 is the live demo link.

## 1. Skill audit (per `SKILL (7).md` workflow)

### 1.1 Existing skills

- `.agents/skills/occlusion-world/SKILL.md`: project world knowledge for eval work.
It covers the graph contract, guardrail and verify rules, the frozen chunk snapshot path, Harbor trilogy plus live-model notes, and the `SRC:` normalization gotcha.
- `SKILL (7).md` (repo root, untracked at audit time): the `project-skill-audit` procedure file itself, not a project skill.

### 1.2 Suggested updates

- `occlusion-world`: add a `Recruiter run path` table (offline pytest vs ingest vs Bedrock vs cal.com, with the keys each needs) and pin current main-line counts (111 tests, 78 golden items).

### 1.3 Suggested new skills

- `recruiter-demo-run`: Qdrant path-mode lock handling plus which env keys each demo mode needs.
Trigger: any demo, interview, or Harbor live task.
- `cal-booking-live-check`: SPEC_V2 section 9 live-check (slots fetch, book-then-cancel, past-time reject, per-endpoint versions, browser UA).
Trigger: any booking change (on the `feature/New-v2` line).
- `doc-sync-gate`: pre-merge check that spec, TODO tracker, provenance, and `AGENTS.md` match the code.
Trigger: pre-merge doc check.

### 1.4 Priority order

1. `doc-sync-gate`.
2. `recruiter-demo-run`.
3. `cal-booking-live-check`.
4. `occlusion-world` update.

## 2. README vs code (main line)

Verified true: hybrid dense (`all-MiniLM-L6-v2`) plus sparse (`Splade_PP_en_v1`) with server RRF plus `rrf_fuse` fallback (`src/retrieve/hybrid.py:19`, `src/agent/fusion.py:19`); guardrail-first graph with Gates 0-3 (`src/agent/graph.py`); `[SRC:doc_id]` verification fail-closed (`src/agent/verify.py`); injectable `build_graph`; 111/111 green.

Drift found and fixed by B1-B5: stale `spec.md` sections, unchecked `TODO.md` tracker, `PROVENANCE.md` TODOs, `AGENTS.md` ingest command, `sample.env` parity, forbidden deps removed, OGL sentence in product, clickable source links.

## 3. Recruiter run path blockers

Closed: placeholder contacts, offline `--pdf-only` path documented, env parity, forbidden-dep removal, source links, OGL attribution, latency/docker notes, hygiene items.
Open: live demo URL only.

## 4. Fix branches (all merged)

B1 `fix/v1-docs-sync`, B2 `fix/v1-env-deps`, B3 `fix/v1-source-links-ogl`, B4 `fix/v1-hygiene`, B5 `fix/v1-readme-demo`. Merge order used: B4, B1, B2, B3, B5. Each carried done criteria plus tests; final suite 111 green on `main`.

## 5. Deploy decision (2026-09-19, no-billing constraint)

Ruled out with evidence: HF Docker needs PRO (docs + user flow), Cloud Run needs a billing account, Modal needs a payment method on file (user flow; only $1 usable without it).
Chose Hugging Face Gradio + ZeroGPU free exception (documented: 2 Gradio Spaces on ZeroGPU for free accounts).
Artifacts: V1-only `src/ui/gradio_app.py` (mirrors `src/ui/app.py`, verified import + Blocks build); Space gets `src/` plus vendored `data/qdrant_storage/` (181 points, 1.4 MB) plus `spaces/zerogpu/requirements.txt` and `spaces/zerogpu/README.md` frontmatter. `modal_app.py` (Docker/Modal path) superseded, left uncommitted at repo root.

## 6. Verification evidence used

- `uv run pytest tests/ingest/ tests/retrieve/ tests/agent/ -q`: 111 passed on `main`.
- `data/golden_set_v1.jsonl`: 78 lines, schema loader accepts 78 items.
- `git check-ignore -v`: `.env` and `data/qdrant_storage/` correctly ignored.
- `rg` for forbidden deps in code: zero imports.
- `rg` for OGL sentence in `src/`: present in both UIs.
- `PYTHONPATH=. uv run --with "gradio>=6" -- python -c "import src.ui.gradio_app"`: `Blocks` builds.
