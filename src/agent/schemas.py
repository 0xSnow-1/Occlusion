"""Occlusion agent data contracts (TODO Phase 5.1).

These shapes are *the* contract of the system: the graph, the eval harness
(Phase 6) and the UI (Phase 9) all import from here. Keep this module free of
LangChain/LangGraph imports so it can be imported anywhere without side effects.

`Answer.confidence` semantics (see TODO Phase 5.1): a self-reported float in
[0, 1] emitted by the generation model. The graph's fail-closed gate (Phase 7)
combines it with citation coverage from `verify.CitationCheck` before deciding
whether to answer.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Union

from pydantic import BaseModel, Field, field_validator, model_validator


class RetrievedChunk(BaseModel):
    """One retrieval hit. Phases 3-4 (`src/retrieve`) produce these; the agent
    package only consumes them."""

    doc_id: str = Field(..., description="Stable source/document identifier")
    text: str = Field(..., min_length=1)
    score: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class Answer(BaseModel):
    """Structured, citation-grounded answer (generation node output)."""

    kind: Literal["answer"] = "answer"  # discriminator for AgentOutput
    answer: str = Field(..., min_length=1)
    citations: list[str] = Field(
        default_factory=list,
        description="doc_ids cited inline as [SRC:doc_id] in `answer`",
    )
    confidence: float = Field(..., ge=0.0, le=1.0)

    @field_validator("citations")
    @classmethod
    def _citations_are_ids(cls, v: list[str]) -> list[str]:
        for item in v:
            if not isinstance(item, str) or not item.strip():
                raise ValueError("citations must be non-empty doc_id strings")
        return v


class RefusalReason(str, Enum):
    """Fail-closed taxonomy (TODO Phase 7 + SCOPE.md refusal taxonomy)."""

    INSUFFICIENT_CONTEXT = "insufficient_context"
    OUT_OF_SCOPE = "out_of_scope"
    DIAGNOSTIC_REQUEST = "diagnostic_request"
    SENSITIVE_TOPIC = "sensitive_topic"


DEFAULT_REFUSAL_MESSAGES: dict[RefusalReason, str] = {
    RefusalReason.INSUFFICIENT_CONTEXT: (
        "I don't have enough grounded information to answer this reliably. "
        "Please consult a dentist."
    ),
    RefusalReason.OUT_OF_SCOPE: (
        "That question is outside the scope of what I'm built to answer. "
        "Please consult a dentist."
    ),
    RefusalReason.DIAGNOSTIC_REQUEST: (
        "I can't diagnose conditions or recommend treatments. "
        "Please consult a dentist."
    ),
    RefusalReason.SENSITIVE_TOPIC: "I'm not able to help with that.",
}


class Refusal(BaseModel):
    """Fail-closed response produced by the gate / `fail_closed` node."""

    kind: Literal["refusal"] = "refusal"
    reason: RefusalReason
    message: str | None = Field(
        default=None, description="Overrides the default refusal copy"
    )

    @model_validator(mode="after")
    def _default_message(self) -> "Refusal":
        if self.message is None:
            self.message = DEFAULT_REFUSAL_MESSAGES[self.reason]
        return self


AgentOutput = Union[Answer, Refusal]  # discriminated by `kind`


class CitationCheck(BaseModel):
    """Result of `verify.verify_citations` (TODO Phase 5.4).

    Feeds the eval harness (Phase 6) directly and the gate (Phase 7).
    """

    verified: bool  # policy outcome: did the answer pass citation verification?
    cited_ids: list[str]  # every [SRC:...] token found in the answer text
    retrieved_ids: list[str]  # doc_ids present in the retrieved chunk set
    fabricated_ids: list[str]  # cited but never retrieved (the failure list)
    matches: int
    total: int
    coverage: float = Field(..., ge=0.0, le=1.0)  # matches / total (0.0 if total == 0)