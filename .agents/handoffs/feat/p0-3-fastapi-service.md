Branch: feat/p0-3-fastapi-service
Date: 2026-10-24
Scope: P0.3 FastAPI service boundary, service-first slice with the UI migration deferred

## What changed

- Added `src/service/`:
  - `app.py`: `create_app(pipeline=..., settings=...)` with `/health`, `/ready`, `/ask`, and `/metrics`.
  - `pipeline.py`: narrow `Pipeline` protocol, `GraphPipeline`, `AskResult`, and `PipelineUnavailable`.
  - `models.py`: typed request/response models with stripped, non-empty, length-limited questions.
  - `settings.py`: environment-backed collection, Qdrant path, threshold, timeout, max length, and Bedrock settings.
  - `metrics.py`: thread-safe in-process Prometheus text metrics for requests, durations, answers, refusals, readiness, and index points.
- Added `scripts/run_api.py` and `src/service/main.py` entry points.
- Added request IDs through `X-Request-ID`, 504 on timeout, and 503 on pipeline or graph infrastructure failure.
- Added `retrieval_error` and `generation_error` to `AgentState`; the graph still fails closed, and `GraphPipeline` maps either flag to 503.
- Added `tests/service/` with 21 tests.
- Added `DECISIONS/fastapi-service-boundary.md`.
- Added `fastapi` and `uvicorn` to `pyproject.toml` and `requirements.txt`; added dev-only `httpx` for FastAPI `TestClient`. `httpx` was already a transitive dependency.
- Updated CI, `.no-mistakes.yaml`, README, AGENTS.md, sample.env, and the P0.3 audit status.
- Streamlit UI is unchanged and still uses the in-process pipeline.

## Verification

- `uv run --python 3.12 pytest tests/ingest/ tests/retrieve/ tests/agent/ tests/eval/ tests/service/ -q` -> 193 passed.
- `uv lock --check` clean.
- `git diff --check` clean.
- Local E2E against the 133-point index:
  - `/health` -> `{"status":"ok"}`.
  - `/ready` -> `ready`, 133 points, `occlusion`, threshold 0.7.
  - Empty question -> 422.
  - 1001-character question -> 422 with `question is too long`.
  - Diagnostic trap -> 200 `Refusal(out_of_scope)`, 0 chunks.
  - Off-topic question -> 200 `Refusal(insufficient_context)`, 0 chunks.
  - Routine question -> 200 answer, 5 chunks, 3 citations.
  - `/metrics` reported request, outcome, readiness, and index-point series.
- `/openapi.json` -> 200 with all four paths.

## Decisions

- Service first, UI migration next. This keeps the live demo up until the API is deployed.
- `/health` never touches Qdrant or Bedrock; `/ready` checks the index only.
- A normal refusal stays 200. Graph infrastructure failures become 503.
- Graph invocations are serialized because local Qdrant path mode is single-process.
- Timeout is `asyncio.wait_for` around `asyncio.to_thread`; the HTTP response returns 504, but the worker thread cannot be cancelled.
- Metrics are process-local and deliberately avoid `prometheus_client`.

## Follow-ups

- Migrate `src/ui/app.py` to call the API over HTTP.
- Decide whether the API is deployed in the same container as Streamlit or on a separate host.
- Set `OCCLUSION_API_URL` in the UI deployment once the API is live.
- P0.2 live Ragas baseline still needs the owner's Bedrock credentials.
- Revisit process-local metrics and thread cancellation if the API runs with multiple workers.
