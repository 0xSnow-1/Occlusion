# Deploy (owner only)

## Streamlit Community Cloud (live demo)

Sign in at share.streamlit.io with GitHub → Create app → repo `0xSnow-1/Occlusion`,
branch `main`, main file `src/ui/app.py`, Python 3.12 → Advanced settings → Secrets
(TOML): `AWS_BEARER_TOKEN_BEDROCK`, `BEDROCK_MODEL_ID`, `BEDROCK_REGION` (plus
`LANGSMITH_TRACING="true"`, `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT` to enable
tracking) → Deploy. Dependencies install from `requirements.txt` at repo root.

The Qdrant index is vendored at `data/qdrant_storage/` (force-added, 133 points,
1.0 MB). Re-vendor after any corpus change with
`uv run python scripts/run_ingest.py` then `git add -f data/qdrant_storage`.
The parser's provenance allowlist and `.dockerignore` both exclude
`data/raw/_archive/`, so rejected sources cannot enter the index.

## Optional container/Spaces hosting (not currently deployed)

- `Dockerfile` builds a Streamlit image (port 7860) for container hosts, e.g. a
  Hugging Face Spaces Docker-SDK app. It bakes the index at build time
  (`uv run python scripts/run_ingest.py`), so a live-HTML re-fetch can make the
  baked size differ from the vendored index (measured 133 points on 2026-10-24;
  vendored index is 133 points).
- `spaces/zerogpu/` holds the frontmatter and requirements for an alternate
  Gradio-based Hugging Face ZeroGPU Space (`src/ui/gradio_app.py`), assembled at
  push time. Neither Spaces config has a published URL.