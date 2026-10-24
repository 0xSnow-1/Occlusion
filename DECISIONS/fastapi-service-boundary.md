# FastAPI Service Boundary

**Date:** 2026-10-24
**Status:** Accepted for the service core; Streamlit migration deferred
**File:** `src/service/`

## Decision

Expose the agent through a FastAPI app built by `create_app(pipeline=..., settings=...)`.
The HTTP layer owns request validation, request IDs, timeouts, health, readiness, and metrics.
`GraphPipeline` owns the lazy Qdrant and Bedrock construction and calls the compiled graph.

Endpoints:

- `GET /health` is pure liveness and never touches Qdrant or Bedrock.
- `GET /ready` checks collection existence and point count only.
- `POST /ask` accepts a stripped, length-limited question and returns the answer or refusal plus chunks, citation check, guardrail decision, latency, and point count.
- `GET /metrics` returns an in-process Prometheus text exposition.

The graph sets `retrieval_error` or `generation_error` when infrastructure fails.
`GraphPipeline` turns either flag into `PipelineUnavailable`, and `/ask` maps that to 503.
A normal off-corpus or guardrail refusal stays a 200 response.

Graph invocations are serialized inside `GraphPipeline` because local Qdrant path mode is a single-process store.
The Streamlit UI still uses the in-process pipeline in this change.
The HTTP migration is deferred until the API is deployed so the live demo stays up.

## Why

- The audit found no validation, length limit, timeout, request ID, health check, or metrics endpoint.
- A narrow `Pipeline` protocol keeps the HTTP layer testable with a fake pipeline and no Bedrock calls.
- Treating blank and whitespace-only input as 422 stops empty questions at the boundary instead of relying on the graph's refusal path.
- Distinguishing infrastructure failure from a safe refusal avoids presenting a broken dependency as a content decision.
- `/health` must not fail because Qdrant or Bedrock is down; only `/ready` and `/ask` should depend on them.
- A small local metrics registry avoids adding `prometheus_client` for four counters and one histogram.

## Evidence

- Offline suite: 193 passed.
- Service tests: 21.
- Local E2E against the 133-point index:
  - `/health` returned `{"status":"ok"}`.
  - `/ready` returned `ready`, 133 points, collection `occlusion`, threshold 0.7.
  - Empty question returned 422.
  - 1001-character question returned 422 with `question is too long`.
  - Diagnostic trap returned 200 with `Refusal(out_of_scope)` and zero chunks.
  - Off-topic question returned 200 with `Refusal(insufficient_context)` and zero chunks.
  - Routine question returned 200 with an answer, 5 chunks, and 3 citations.
  - `/metrics` reported request, outcome, readiness, and index-point series.

## Tradeoffs

- Timeouts use `asyncio.wait_for` around `asyncio.to_thread`.
  The HTTP response returns 504, but the worker thread cannot be cancelled.
  A hard per-request cancellation needs a process boundary or a cancellable client.
- Metrics are process-local and reset on restart.
  That is acceptable for one API process; multi-worker deployments need a shared registry or a Prometheus sidecar.
- The app serializes graph calls for the local Qdrant lock.
  Server Qdrant and a thread-safe Bedrock client could allow more concurrency later.
- The UI remains coupled to internals until the follow-up migration.
  This is a deliberate staging choice, not the target architecture.

## Alternatives rejected

- **UI talks to a same-container API now.** Rejected for this change because it needs a Docker process-manager change and live-demo redeploy.
- **UI talks to a separate API host now.** Rejected for this change because it needs an external deployment and a new `OCCLUSION_API_URL` secret before the demo can work.
- **Add `prometheus_client` for four metrics.** Rejected to keep the dependency surface small; revisit if metric coverage grows.
- **Return 200 for graph infrastructure failures.** Rejected because it hides a broken dependency behind a refusal.

## Reproduce

```bash
uv run pytest tests/service/ -q
uv run python scripts/run_api.py
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ready
curl http://127.0.0.1:8000/metrics
```
