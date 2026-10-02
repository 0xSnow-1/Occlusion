# Optional container image for the Occlusion Streamlit demo.
#
# The live demo runs on Streamlit Community Cloud (see README Demo and
# docs/DEPLOY.md). This Dockerfile is an optional path for container hosts
# that want the same Streamlit app without Community Cloud, e.g. a Hugging
# Face Spaces Docker-SDK app (HF Docker SDK needs PRO as of 2026). No Spaces
# URL is published — this image is the available, not deployed, path. The
# Qdrant index is built at image-build time (data/qdrant_storage/ is
# gitignored at build, a fresh re-ingest happens in this image).
#
# Space settings (set manually at creation, nothing secret is baked in):
#   SDK: Docker · hardware: CPU basic (free) · port: 7860
#   Secrets (Settings → Variables and secrets — never in the repo):
#     AWS_BEARER_TOKEN_BEDROCK, BEDROCK_MODEL_ID, BEDROCK_REGION
# At boot the app reads them from the ambient environment (same boto3 chain
# as local .env use). Missing credentials fail loudly on the start page.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    USER_AGENT="OcclusionDentalRAG/0.1 (HF Spaces demo)"

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY data/raw/ ./data/raw/
COPY data/PROVENANCE.md data/HTML_SOURCES.md ./data/

RUN uv sync --frozen --no-dev

# Bake the Qdrant index into the image (needs build-time network: 11 HTML
# sources + fastembed model downloads). Live-HTML sources may vary; measured
# at 136 points (136 chunks from 28 pages; eval snapshot = 120 points).
RUN uv run python scripts/run_ingest.py

EXPOSE 7860

CMD ["uv", "run", "streamlit", "run", "src/ui/app.py", \
     "--server.port", "7860", \
     "--server.address", "0.0.0.0", \
     "--server.headless", "true"]
