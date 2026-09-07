"""Shared data contracts for retrieval and the agent (TODO Phases 3-5.1).

Everything cross-module is a Pydantic model: retrieval returns
`RetrievedChunk`s, the LLM must produce a valid `Answer`, and any terminal
output is an `AgentOutput` (Answer | Refusal, discriminated on `kind`).
Validation happens at construction — a malformed value never becomes an
instance — so downstream code can trust these types.

`state.py` (graph working memory) composes these types; the TypedDict
itself validates nothing.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter, field_validator


class RetrievedChunk(BaseModel):
    """One ranked chunk returned by retrieval.

    Example:
        RetrievedChunk(
            doc_id="nhs-gum-disease",
            text="Brush twice a day with fluoride toothpaste ...",
            score=0.83,
            source_url="https://www.nhs.uk/conditions/gum-disease/",
        )
    """

    doc_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    score: float | None = None
    source_url: str | None = None
    title: str | None = None


class RefusalReason(str, Enum):
    """Why the agent refused. Values are the wire format (JSON / eval logs).

    `INSUFFICIENT_CONTEXT` covers the RAG-side fail-closed gates (empty
    retrieval, low confidence, failed citation check). `OUT_OF_SCOPE` is
    the SCOPE.md trap taxonomy (diagnostic/prescriptive, out-of-corpus).
    The Phase 7 deterministic filter reuses this enum; extend it there,
    not ad hoc at refusal sites.
    """

    INSUFFICIENT_CONTEXT = "insufficient_context"
    OUT_OF_SCOPE = "out_of_scope"


_DEFAULT_REFUSAL_MESSAGE = (
    "I can't answer that with the information I have. For anything urgent, "
    "painful, or specific to your own situation, please consult a dentist."
)


class Answer(BaseModel):
    """The LLM's structured output on the answer path (TODO 5.1).

    `confidence` is the model's *self-reported* certainty that the answer
    is grounded in the supplied chunks — defined now (TODO 5.1 pitfall) so
    the Phase 7 threshold compares a fixed quantity; recalibrate there.
    """

    kind: Literal["answer"] = "answer"
    answer: str = Field(min_length=1)
    citations: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)

    @field_validator("answer")
    @classmethod
    def _answer_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("answer must not be blank")
        return v


class Refusal(BaseModel):
    """The structured output on any fail-closed path.

    The default message is patient-safe by construction: a refusal site
    that forgets to write one still tells the user to consult a dentist.
    """

    kind: Literal["refusal"] = "refusal"
    reason: RefusalReason
    message: str = Field(default_factory=lambda: _DEFAULT_REFUSAL_MESSAGE)


AgentOutput = Annotated[Answer | Refusal, Field(discriminator="kind")]
"""Terminal agent output; dispatch on `kind`. Validate raw dicts via
`TypeAdapter(AgentOutput).validate_python(...)` — the eval harness and
future API layer depend on this round-tripping both members."""


class GuardrailDecision(BaseModel):
    """Outcome of the deterministic pre-LLM guardrail (TODO 7.2).

    Produced by `src/agent/guardrail.py`, never by the LLM. Defaults are
    fail-closed: a bare `GuardrailDecision()` is NOT allowed, mirroring
    `CitationCheck`.
    """

    allowed: bool = False
    rule: str | None = None
    """Which guardrail rule fired (None when allowed) — for logs and eval."""


class CitationCheck(BaseModel):
    """Result of verifying inline `[SRC:doc_id]` tokens (TODO 5.4).

    Produced by `src/agent/verify.py`, never by the LLM. Defaults are
    fail-closed: a bare `CitationCheck()` verifies nothing.
    """

    verified: bool = False
    cited_ids: list[str] = Field(default_factory=list)
    retrieved_ids: list[str] = Field(default_factory=list)
    fabricated_ids: list[str] = Field(default_factory=list)
    matches: int = 0
    total: int = 0
    coverage: float = Field(default=0.0, ge=0, le=1)


__all__ = [
    "AgentOutput",
    "Answer",
    "CitationCheck",
    "GuardrailDecision",
    "Refusal",
    "RefusalReason",
    "RetrievedChunk",
]
