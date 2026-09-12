"""Graph working memory (TODO Phase 5.3): one invocation, one `AgentState`.

This is a TypedDict — a *shape* for the dict LangGraph passes between
nodes, not a validator. Everything that must survive contact with bad
data is a Pydantic model from `schemas.py`, validated at construction.

Design rule: every field has exactly one producer and is written once
per run, so all fields use LangGraph's default overwrite semantics —
deliberately NO reducers. A reducer on `fused_chunks` would turn a
per-run derivation into an accumulating ledger: silent today (one write
per invoke), a landmine under a Phase 7 regenerate loop (stale chunks
would persist and outrank fresh ones by list position), and it would
break the exact-equality contract in tests/agent/test_graph.py. If a
future chat-history field ever arrives, that field — and only that one —
gets `Annotated[list, operator.add]`.

Flow: `question` → guardrail node writes `guardrail` (flag → decide writes
a terminal `Refusal`, LLM never called) → retrieve node writes
`fused_chunks` → generate node writes `candidate` (a validated `Answer`) →
verify node writes `citation_check` → routing writes `response` (an
`Answer` or a `Refusal`). Consumers (UI, eval harness) read exactly
`response`.
"""

from __future__ import annotations

from typing import TypedDict

from src.agent.schemas import (
    Answer,
    BookingIntent,
    BookingReceipt,
    CitationCheck,
    Contact,
    GuardrailDecision,
    Refusal,
    RetrievedChunk,
    Slot,
)


class AgentState(TypedDict):
    """Shared memory for one graph run (see module docstring for flow)."""

    question: str
    """The user's dental question. Input only; never rewritten."""

    guardrail: GuardrailDecision
    """Deterministic pre-LLM scope check (TODO 7.2). Flagged → refuse, END."""

    fused_chunks: list[RetrievedChunk]
    """RRF-fused retrieval results, best first. Empty → refuse (fail closed)."""

    candidate: Answer
    """Validated-but-unverified LLM output; input to verification and gates."""

    citation_check: CitationCheck
    """Outcome of citation verification against `fused_chunks`."""

    response: Answer | Refusal
    """Terminal output, set by the answer path OR the refuse node."""

    confidence_threshold: float
    """Confidence gate; injected as a default by `build_graph`."""

    booking_intent: BookingIntent | None
    """Parsed booking desire; written by intent parse inside guardrail routing."""

    slots: list[Slot]
    """Real open times from get_slots; written by the booking node."""

    booking_receipt: BookingReceipt | None
    """Proof a booking worked or failed; written by the booking node."""

    contact: Contact | None
    """Attendee details collected in-chat before booking confirm."""

__all__ = ["AgentState"]
