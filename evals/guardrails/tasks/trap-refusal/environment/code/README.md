# Pinned sources under test

`src_agent/` is a verbatim copy of the production graph code at repo commit
`d87520c`, renamed so the Docker build context (`environment/`) stays
self-contained:

- `src_agent/__init__.py` ← `src/agent/__init__.py`
- `src_agent/schemas.py` ← `src/agent/schemas.py`
- `src_agent/state.py` ← `src/agent/state.py`
- `src_agent/guardrail.py` ← `src/agent/guardrail.py`
- `src_agent/verify.py` ← `src/agent/verify.py`
- `src_agent/fusion.py` ← `src/agent/fusion.py`
- `src_agent/graph.py` ← `src/agent/graph.py`
- `src_agent/prompts/` ← `src/agent/prompts/` (`__init__.py`, `dental_qa_base.md`)

The image copies this tree to `/app/src/agent`. When the repo graph changes,
re-vendor these files, record the new commit here, and regenerate
`tests/fixtures/hashes.json` (see `tests/verify_refusal.py`).
