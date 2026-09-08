FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# qdrant-client[fastembed] pulls the local embedding stack (dense
# all-MiniLM-L6-v2 + SPLADE sparse) used at setup ingest and query time;
# langchain-aws + boto3 is the Bedrock Haiku path (run-time bearer token).
RUN pip install --no-cache-dir "langgraph>=1.2" "pydantic>=2.0" \
    "qdrant-client[fastembed]>=1.12" "langchain-aws>=0.2" "boto3>=1.34"

WORKDIR /app

# Pinned sources under test (vendored from repo commit 01d6902;
# see code/README.md). Agent-visible by design; white-box task.
COPY code/src_agent /app/src/agent
COPY code/src_retrieve /app/src/retrieve
COPY code/src_ingest /app/src/ingest
RUN touch /app/src/__init__.py

# Task seed state (visible questions + frozen chunk snapshot — no expected results).
COPY questions.jsonl /app/questions.jsonl
COPY chunks_v1.jsonl /app/chunks_v1.jsonl
COPY run_live.py /app/run_live.py

# Build-time gate: offline only (snapshot ingest, retrieval probe, Gate-0
# short-circuit). No Bedrock call, no credentials needed at build.
RUN mkdir -p /logs && python3 /app/run_live.py --self-check
