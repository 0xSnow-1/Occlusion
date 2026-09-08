FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN pip install --no-cache-dir "langgraph>=1.2" "pydantic>=2.0"

WORKDIR /app

# Pinned graph sources under test (vendored from repo commit d87520c;
# see code/README.md). Agent-visible by design; white-box task.
COPY code/src_agent /app/src/agent
RUN touch /app/src/__init__.py

# Task seed state (visible questions only — no expected results).
COPY questions.jsonl /app/questions.jsonl
COPY run_batch.py /app/run_batch.py

RUN mkdir -p /logs && python3 /app/run_batch.py --self-check
