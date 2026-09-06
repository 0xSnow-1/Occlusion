# SHARED_CONTEXT.md — Occlusion

(Read this before touching shared code or assuming another subsystem's
behavior. Append as you discover things. Reviewed by a human before every merge.)

## Interface contracts in flux
- `<file/module>`: `<what changed, who needs to know>`
- `src/ingest/chunking_and_embedding.py` -> `src/ingest/vector_store.py`: chunks must arrive unembedded; embedding happens at upsert time via fastembed (`models.Document`). Anyone touching chunking or the vector store needs to know.
- `src/retrieve/__init__.py`: exposes `dense_search`, `sparse_search`, `hybrid_search`, `make_retriever`. The agent graph (Phase 5) will build on these; do not rename without updating this file.
- `src/agent/schemas.py`: `RetrievedChunk` is shared by fusion and the graph; `Answer` vs `Refusal` discriminated union on `kind`. Still settling as the agent phase is built.

## Learnings
- `<branch/date>`: `<what was discovered, why it matters to other agents>`
- `feature/retrieve` / 2026-09-06: commit `08c64e4` landed `chunking_and_embedding.py` with 7 unresolved conflict hunks (SyntaxError, broke all of `tests/ingest/`). Cause: rebase restored a file one side had deleted. Fixed in `fe764b2` by keeping the chunk-only side. Lesson: never commit a rebase/merge result without running the offline suite.
- `feature/retrieve` / 2026-09-06: pushing feature work straight to `main` permanently escapes the no-mistakes gate (it only validates feature-to-base diffs). Carry work between branches with `git checkout -b <new> <old>` instead; `main` is written to only by merging PRs.
- 2026-09-06: pipeline review model must support forced structured output (`tool_choice`). `ling-3.0-flash-fin-free` and `muse-spark-1.3-contributor-free` fail; `opencode/big-pickle` works. See `~/.no-mistakes/config.yaml`.
- 2026-09-06: every pipeline run parks at the CI gate (`unknown flag: --slurp` from `gh api` 2.45.0). Repo has no `.github/workflows`, so there is nothing to check; skip or approve the CI step until the pipeline is fixed.

## Open flags for human review
- `<anything an agent wants a human to weigh in on before proceeding>`
- The retrieval-pipeline code reached `main` (`08c64e4`) without ever passing the gate. Only the conflict fix (`fe764b2`, PR #4) is gate-validated. Decide whether the unreviewed portion needs a retroactive look.
- No CI workflows exist yet, so the CI gate is always a manual approve/skip. Decide if/when to add CI.
