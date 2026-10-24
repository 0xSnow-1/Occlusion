"""Typed request and response models for the Occlusion HTTP service."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from src.agent.schemas import (
    AgentOutput,
    CitationCheck,
    GuardrailDecision,
    RetrievedChunk,
)

MAX_REQUEST_CHARS = 4000


class AskRequest(BaseModel):
    """One question submitted to the agent."""

    question: str = Field(min_length=1, max_length=MAX_REQUEST_CHARS)

    @field_validator("question", mode="before")
    @classmethod
    def _strip_question(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


class AskResponse(BaseModel):
    """The agent's terminal output plus the evidence behind it."""

    request_id: str
    response: AgentOutput
    chunks: list[RetrievedChunk] = Field(default_factory=list)
    citation_check: CitationCheck | None = None
    guardrail: GuardrailDecision
    latency_ms: float = Field(ge=0)
    points: int = Field(ge=0)


class HealthResponse(BaseModel):
    """Liveness response."""

    status: str = "ok"


class ReadyResponse(BaseModel):
    """Readiness response for the retrieval index."""

    status: str = "ready"
    points: int = Field(ge=0)
    collection: str
    confidence_threshold: float = Field(ge=0, le=1)
    model_id: str


__all__ = [
    "AskRequest",
    "AskResponse",
    "HealthResponse",
    "MAX_REQUEST_CHARS",
    "ReadyResponse",
]
