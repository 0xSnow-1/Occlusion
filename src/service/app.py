"""FastAPI boundary for the Occlusion dental RAG agent."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse

from src.service.metrics import Metrics
from src.service.models import (
    AskRequest,
    AskResponse,
    HealthResponse,
    ReadyResponse,
)
from src.service.pipeline import GraphPipeline, Pipeline, PipelineUnavailable
from src.service.settings import Settings

logger = logging.getLogger(__name__)

_KNOWN_ENDPOINTS = {"/health", "/ready", "/ask", "/metrics"}


def create_app(
    *,
    pipeline: Pipeline | None = None,
    settings: Settings | None = None,
) -> FastAPI:
    """Build the HTTP app with an injectable pipeline for offline tests."""
    service_settings = settings if settings is not None else Settings.from_env()
    service_pipeline = (
        pipeline if pipeline is not None else GraphPipeline(service_settings)
    )
    metrics = Metrics()

    app = FastAPI(title="Occlusion API", version="0.1.0")
    app.state.pipeline = service_pipeline
    app.state.settings = service_settings
    app.state.metrics = metrics

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", "").strip()
        if not request_id:
            request_id = uuid.uuid4().hex
        request_id = request_id[:128]
        request.state.request_id = request_id

        endpoint = (
            request.url.path
            if request.url.path in _KNOWN_ENDPOINTS
            else "other"
        )
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            logger.exception(
                "Unhandled request error (request_id=%s)", request_id
            )
            response = JSONResponse(
                status_code=500,
                content={
                    "detail": "internal server error",
                    "request_id": request_id,
                },
            )

        duration_s = time.perf_counter() - start
        response.headers["X-Request-ID"] = request_id
        if endpoint != "/metrics":
            metrics.observe_http(endpoint, response.status_code, duration_s)
        return response

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse()

    @app.get(
        "/ready",
        response_model=ReadyResponse,
        responses={503: {"description": "Retrieval index is not ready"}},
    )
    async def ready() -> ReadyResponse:
        try:
            is_ready = await asyncio.to_thread(service_pipeline.ready)
        except Exception:
            logger.exception("Readiness check failed")
            is_ready = False

        if not is_ready:
            metrics.set_ready(False, 0)
            raise HTTPException(
                status_code=503,
                detail="retrieval index is not ready",
            )

        points = await asyncio.to_thread(service_pipeline.points)
        metrics.set_ready(True, points)
        return ReadyResponse(
            points=points,
            collection=service_settings.collection_name,
            confidence_threshold=service_settings.confidence_threshold,
            model_id=service_settings.bedrock_model_id,
        )

    @app.post(
        "/ask",
        response_model=AskResponse,
        responses={
            503: {"description": "Assistant unavailable"},
            504: {"description": "Request timed out"},
        },
    )
    async def ask(payload: AskRequest, request: Request) -> AskResponse:
        request_id = request.state.request_id
        if len(payload.question) > service_settings.max_question_length:
            raise HTTPException(status_code=422, detail="question is too long")

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    service_pipeline.ask,
                    payload.question,
                    request_id=request_id,
                ),
                timeout=service_settings.request_timeout_s,
            )
        except TimeoutError:
            logger.warning("Request timed out (request_id=%s)", request_id)
            raise HTTPException(status_code=504, detail="request timed out")
        except PipelineUnavailable:
            logger.warning(
                "Assistant unavailable (request_id=%s)", request_id
            )
            raise HTTPException(status_code=503, detail="assistant unavailable")
        except Exception:
            logger.exception("Ask failed (request_id=%s)", request_id)
            raise HTTPException(status_code=503, detail="assistant unavailable")

        metrics.set_ready(result.points > 0, result.points)
        reason = (
            result.response.reason.value
            if result.response.kind == "refusal"
            else None
        )
        metrics.observe_outcome(result.response.kind, reason)
        return AskResponse(
            request_id=request_id,
            response=result.response,
            chunks=result.chunks,
            citation_check=result.citation_check,
            guardrail=result.guardrail,
            latency_ms=result.latency_ms,
            points=result.points,
        )

    @app.get("/metrics", response_class=PlainTextResponse)
    async def metrics_endpoint() -> PlainTextResponse:
        return PlainTextResponse(
            metrics.render(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    return app


__all__ = ["create_app"]
