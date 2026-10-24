"""Production pipeline adapter for the Occlusion HTTP service."""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Protocol

from src.agent.graph import build_graph
from src.agent.schemas import (
    AgentOutput,
    CitationCheck,
    GuardrailDecision,
    RetrievedChunk,
)
from src.ingest.vector_store import VectorStore
from src.retrieve import make_retriever
from src.service.settings import Settings

logger = logging.getLogger(__name__)


class PipelineUnavailable(RuntimeError):
    """The assistant cannot serve this request right now."""


@dataclass(frozen=True)
class AskResult:
    """One completed agent run, ready for the HTTP response model."""

    response: AgentOutput
    chunks: list[RetrievedChunk]
    citation_check: CitationCheck | None
    guardrail: GuardrailDecision
    latency_ms: float
    points: int


class Pipeline(Protocol):
    """The narrow seam the HTTP layer needs from the agent."""

    def ready(self) -> bool: ...

    def points(self) -> int: ...

    def ask(self, question: str, *, request_id: str) -> AskResult: ...


def build_bedrock_llm(settings: Settings):
    """Build the Bedrock chat model, forwarding the bearer token explicitly."""
    from langchain_aws import ChatBedrockConverse

    return ChatBedrockConverse(
        model=settings.bedrock_model_id,
        region_name=settings.bedrock_region,
        temperature=0,
        bedrock_api_key=os.getenv("AWS_BEARER_TOKEN_BEDROCK"),
    )


class GraphPipeline:
    """Lazy adapter from Qdrant and Bedrock to one compiled agent graph."""

    def __init__(
        self,
        settings: Settings,
        *,
        store: Any | None = None,
        graph: Any | None = None,
    ) -> None:
        self.settings = settings
        self._store = store
        self._graph = graph
        self._points = 0
        self._ready = False
        self._store_lock = threading.Lock()
        self._graph_lock = threading.Lock()
        self._ask_lock = threading.Lock()

    def _ensure_store(self) -> Any:
        if self._store is None:
            with self._store_lock:
                if self._store is None:
                    self._store = VectorStore(
                        collection_name=self.settings.collection_name,
                        qdrant_url=self.settings.qdrant_path,
                    )
        return self._store

    def _ensure_graph(self) -> Any:
        if self._graph is None:
            with self._graph_lock:
                if self._graph is None:
                    store = self._ensure_store()
                    retriever = make_retriever(
                        store.client,
                        self.settings.collection_name,
                        variant="hybrid",
                    )
                    self._graph = build_graph(
                        retriever=retriever,
                        llm=build_bedrock_llm(self.settings),
                        confidence_threshold=self.settings.confidence_threshold,
                    )
        return self._graph

    def _read_point_count(self, store: Any) -> int:
        count = store.client.count(
            collection_name=self.settings.collection_name
        ).count
        return max(count, 0)

    def ready(self) -> bool:
        try:
            store = self._ensure_store()
            if not store.collection_exists():
                self._ready = False
                self._points = 0
                return False
            self._points = self._read_point_count(store)
        except Exception as exc:
            logger.warning(
                "Readiness check failed: %s: %s",
                type(exc).__name__,
                exc,
            )
            self._ready = False
            return False

        self._ready = self._points > 0
        return self._ready

    def points(self) -> int:
        if not self._ready:
            self.ready()
        return self._points

    def ask(self, question: str, *, request_id: str) -> AskResult:
        start = time.perf_counter()
        try:
            store = self._ensure_store()
            if not store.collection_exists():
                raise PipelineUnavailable("retrieval index is not available")
            graph = self._ensure_graph()
            with self._ask_lock:
                state = graph.invoke({"question": question})
        except PipelineUnavailable:
            raise
        except Exception as exc:
            logger.error(
                "Pipeline unavailable (request_id=%s): %s: %s",
                request_id,
                type(exc).__name__,
                exc,
            )
            raise PipelineUnavailable("assistant unavailable") from exc

        if not isinstance(state, dict):
            logger.error("Graph returned a non-dict state (request_id=%s)", request_id)
            raise PipelineUnavailable("assistant unavailable")

        if state.get("retrieval_error") or state.get("generation_error"):
            logger.error(
                "Graph infrastructure failure (request_id=%s, "
                "retrieval_error=%s, generation_error=%s)",
                request_id,
                state.get("retrieval_error"),
                state.get("generation_error"),
            )
            raise PipelineUnavailable("assistant unavailable")

        response = state.get("response")
        guardrail = state.get("guardrail")
        if response is None or guardrail is None:
            logger.error(
                "Graph returned an incomplete state (request_id=%s)",
                request_id,
            )
            raise PipelineUnavailable("assistant unavailable")

        if self._points <= 0:
            try:
                self._points = self._read_point_count(store)
            except Exception:
                self._points = 0

        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        logger.info(
            "Agent finished (request_id=%s, kind=%s, latency_ms=%.2f)",
            request_id,
            response.kind,
            latency_ms,
        )
        return AskResult(
            response=response,
            chunks=state.get("fused_chunks") or [],
            citation_check=state.get("citation_check"),
            guardrail=guardrail,
            latency_ms=latency_ms,
            points=self._points,
        )


__all__ = [
    "AskResult",
    "GraphPipeline",
    "Pipeline",
    "PipelineUnavailable",
    "build_bedrock_llm",
]
