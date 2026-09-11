"""LangGraph agent implementation for dental RAG (TODO Phases 5.3 + 7.2)."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Callable, List

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agent import tools
from src.agent.booking_intent import extract_start_iso, parse_booking_intent
from src.agent.guardrail import screen_question
from src.agent.prompts import format_dental_qa_prompt
from src.agent.schemas import (
    AgentOutput,
    Answer,
    BookingReceipt,
    Refusal,
    RefusalReason,
    RetrievedChunk,
)
from src.agent.state import AgentState
from src.agent.verify import verify_citations

logger = logging.getLogger(__name__)


def _guardrail_node():
    """Guardrail node: deterministic pre-LLM scope check (TODO 7.2).

    The v3 architecture's "smoke detector" — flagged questions end the run
    here with a structured Refusal(OUT_OF_SCOPE); the LLM is never called
    and retrieval never runs.
    """
    def guardrail_node(state: AgentState) -> dict:
        decision = screen_question(state["question"])
        intent = parse_booking_intent(state["question"])
        logger.info(
            "Guardrail: allowed=%s rule=%s question=%.60s",
            decision.allowed,
            decision.rule,
            state["question"],
        )
        return {"guardrail": decision, "booking_intent": intent}
    return guardrail_node


def _retrieve_node(retriever: Callable[..., List[RetrievedChunk]]):
    """Retrieve node: calls retriever and stores results in state."""
    def retrieve_node(state: AgentState) -> dict:
        try:
            # Call retriever with top_n=5 (can be made configurable if needed)
            chunks = retriever(state["question"], top_n=5)
            logger.info(f"Retrieved {len(chunks)} chunks for question: {state['question'][:50]}...")
            return {"fused_chunks": chunks}
        except Exception as e:
            logger.error(f"Retrieval failed: {type(e).__name__}: {e}")
            # Fail closed: empty retrieval leads to refusal
            return {"fused_chunks": []}
    return retrieve_node


def _should_continue_to_generate(state: AgentState) -> str:
    """Route from retrieve node: continue to generate if we have chunks, else go to decide (refuse)."""
    if state["fused_chunks"]:
        return "continue"
    return "refuse"


def _route_after_guardrail(state: AgentState) -> str:
    """Route from guardrail node: flagged → refusal gate, booking → booking node."""
    if not state["guardrail"].allowed:
        return "decide"
    intent = state.get("booking_intent")
    if intent is not None and intent.wants_booking:
        return "booking"
    return "retrieve"


def _generate_node(llm):
    """Generate node: builds prompt with [SRC:doc_id] anchors and calls LLM."""
    def generate_node(state: AgentState) -> dict:
        # Build prompt with [SRC:doc_id] anchored chunks from the versioned
        # template in prompts/ (TODO 5.2). A missing template is a broken
        # install, not a runtime hiccup — let the error surface loudly
        # instead of silently swapping in a second copy of the prompt.
        prompt = format_dental_qa_prompt(
            question=state["question"],
            chunks=state["fused_chunks"],
            template_name="dental_qa_v2.3",
        )
        
        try:
            # Call LLM with structured output
            structured_llm = llm.with_structured_output(Answer)
            result = structured_llm.invoke([{"role": "user", "content": prompt}])
            logger.info(f"Generated answer with confidence: {result.confidence}")
            return {"candidate": result}
        except Exception as e:
            logger.error(f"Generation failed: {type(e).__name__}: {e}")
            # Return low-confidence answer to trigger refusal
            return {"candidate": Answer(
                answer="I encountered an error while generating the answer.",
                citations=[],
                confidence=0.0,
            )}
    return generate_node


def _verify_node():
    """Verify node: checks citation validity of generated answer."""
    def verify_node(state: AgentState) -> dict:
        citation_check = verify_citations(state["candidate"], state["fused_chunks"])
        logger.info(f"Citation verification: verified={citation_check.verified}, coverage={citation_check.coverage:.2f}")
        return {"citation_check": citation_check}
    return verify_node


def _booking_node(list_event_types_fn=None, get_slots_fn=None, create_booking_fn=None):
    """Booking node (SPEC_V2 §6): real cal.com availability + booking, no LLM.

    - Resolves event_slug to eventTypeId via list_event_types, else first event.
    - Default window is the next 7 days in CAL_TIMEZONE; lists real slots.
    - If the question names an ISO time and contact has name+email, books it.
    - Any failure yields BookingReceipt(ok=False) plus a callback offer.
      It never emits a fake UID and never invents a slot.
    """
    def booking_node(state: AgentState) -> dict:
        intent = state.get("booking_intent") or parse_booking_intent(state["question"])
        contact = state.get("contact")
        list_fn = list_event_types_fn or tools.list_event_types
        slots_fn = get_slots_fn or tools.get_slots
        book_fn = create_booking_fn or tools.create_booking

        try:
            events = list_fn()
        except Exception as e:
            logger.error("Booking: list_event_types failed %s", type(e).__name__)
            events = []
        if not events:
            receipt = BookingReceipt(ok=False, error="calendar unavailable")
            return {
                "slots": [],
                "booking_receipt": receipt,
                "response": _create_refusal(
                    RefusalReason.INSUFFICIENT_CONTEXT,
                    "The calendar is unavailable right now. "
                    "Please leave your name and phone number and we will call you back.",
                ),
            }

        slug = (intent.event_slug or "").lower()
        event = events[0]
        if slug:
            for e in events:
                if slug in e.slug.lower() or slug in e.title.lower():
                    event = e
                    break

        start_iso = extract_start_iso(state["question"])
        if contact is not None and contact.name and contact.email and start_iso:
            try:
                receipt = book_fn(event.id, start_iso, contact.name, contact.email)
            except Exception as e:
                logger.error("Booking: create_booking failed %s", type(e).__name__)
                receipt = BookingReceipt(ok=False, error="calendar unavailable")
            if receipt.ok:
                when = receipt.start_utc.isoformat() if receipt.start_utc else start_iso
                logger.info("Booking: booked uid=%s", receipt.uid)
                return {
                    "slots": state.get("slots", []),
                    "booking_receipt": receipt,
                    "response": Answer(
                        answer=(
                            f"Booked {receipt.title or event.title} at {when} UTC. "
                            f"UID {receipt.uid}. A confirmation email was sent by cal.com."
                        ),
                        citations=[],
                        confidence=1.0,
                    ),
                }
            logger.info("Booking: booking failed, offering callback")
            return {
                "slots": state.get("slots", []),
                "booking_receipt": receipt,
                "response": _create_refusal(
                    RefusalReason.INSUFFICIENT_CONTEXT,
                    f"That time did not work ({receipt.error or 'unavailable'}). "
                    "Please pick another time or leave your name and phone "
                    "number and we will call you back.",
                ),
            }

        tz = os.environ.get("CAL_TIMEZONE", "UTC") or "UTC"
        now = datetime.now(timezone.utc)
        start = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        end = (now + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            slots = slots_fn(event.id, start, end, tz)
        except Exception as e:
            logger.error("Booking: get_slots failed %s", type(e).__name__)
            slots = []
        if not slots:
            receipt = BookingReceipt(ok=False, error="calendar unavailable")
            return {
                "slots": [],
                "booking_receipt": receipt,
                "response": _create_refusal(
                    RefusalReason.INSUFFICIENT_CONTEXT,
                    "No open times came back from the calendar. "
                    "Please leave your name and phone number and we will call you back.",
                ),
            }
        times = ", ".join(s.start_utc.isoformat() for s in slots[:5])
        logger.info("Booking: offering %d slots", len(slots))
        return {
            "slots": slots,
            "booking_receipt": None,
            "response": Answer(
                answer=(
                    f"Available {event.title} times (UTC): {times}. "
                    "Reply with the time you want plus your name and email to confirm."
                ),
                citations=[],
                confidence=1.0,
            ),
        }
    return booking_node


def _decide_node(confidence_threshold: float):
    """Decide node: applies refusal gates and sets final response."""
    def decide_node(state: AgentState) -> dict:
        # Gate 0: Pre-LLM guardrail flagged the question (TODO 7.2) —
        # diagnostic/prescriptive/out-of-scope per SCOPE.md §5. Retrieval
        # and generation never ran; the refusal is deterministic.
        if not state["guardrail"].allowed:
            logger.info("Refusing at guardrail (rule=%s)", state["guardrail"].rule)
            return {"response": _create_refusal(RefusalReason.OUT_OF_SCOPE)}

        # Gate 1: Empty retrieval
        if not state["fused_chunks"]:
            logger.info("Refusing due to empty retrieval")
            return {"response": _create_refusal(RefusalReason.INSUFFICIENT_CONTEXT)}
        
        # Gate 2: Failed citation check
        if not state["citation_check"].verified:
            logger.info("Refusing due to failed citation check")
            return {"response": _create_refusal(RefusalReason.INSUFFICIENT_CONTEXT)}
        
        # Gate 3: Low confidence
        if state["candidate"].confidence < confidence_threshold:
            logger.info(f"Refusing due to low confidence: {state['candidate'].confidence} < {confidence_threshold}")
            return {"response": _create_refusal(RefusalReason.INSUFFICIENT_CONTEXT)}

        # All gates passed: return the candidate answer
        logger.info("Accepting generated answer")
        return {"response": state["candidate"]}
    return decide_node


def _create_refusal(reason: RefusalReason, message: str | None = None) -> AgentOutput:
    """Create a refusal with the given reason; message is the patient-safe
    default from schemas.py (fail closed by construction)."""
    if message is None:
        return Refusal(reason=reason)
    return Refusal(reason=reason, message=message)


def build_graph(
    retriever: Callable[..., List[RetrievedChunk]],
    llm,
    confidence_threshold: float = 0.7,
    *,
    list_event_types_fn=None,
    get_slots_fn=None,
    create_booking_fn=None,
) -> CompiledStateGraph:
    """Build and compile the LangGraph agent.

    Wiring (nodes and edges are defined above; this assembles them):

        guardrail -> retrieve -> [chunks? generate -> verify] -> decide -> END
            \\-(flagged)------------------------------^   (LLM never called)
                     \\---- (empty) -----------------^
            \\-(booking intent) -> booking -> END (no LLM, no retrieval)

    Args:
        retriever: Function signature (query: str, *, top_n: int) -> list[RetrievedChunk]
        llm: Language model with .with_structured_output(Answer) method
        confidence_threshold: Minimum confidence score to accept answer (0-1)
        list_event_types_fn/get_slots_fn/create_booking_fn: injectable
            booking tools (default to real cal.com wrappers in tools.py).

    Returns:
        Compiled StateGraph ready for invocation
    """
    graph_builder = StateGraph(AgentState)

    graph_builder.add_node("guardrail", _guardrail_node())
    graph_builder.add_node("retrieve", _retrieve_node(retriever))
    graph_builder.add_node("generate", _generate_node(llm))
    graph_builder.add_node("verify", _verify_node())
    graph_builder.add_node("decide", _decide_node(confidence_threshold))
    graph_builder.add_node(
        "booking",
        _booking_node(list_event_types_fn, get_slots_fn, create_booking_fn),
    )

    graph_builder.set_entry_point("guardrail")

    # Flagged questions (diagnostic/prescriptive/out-of-scope) go straight
    # to the refusal gate — retrieval and the LLM never run (TODO 7.2).
    # Booking questions go to the booking node — LLM and retrieval never run.
    # Allowed questions continue into the normal RAG path.
    graph_builder.add_conditional_edges(
        "guardrail",
        _route_after_guardrail,
        {"retrieve": "retrieve", "booking": "booking", "decide": "decide"},
    )

    # Empty retrieval skips generation entirely (LLM never called) and
    # goes straight to the refusal gate.
    graph_builder.add_conditional_edges(
        "retrieve",
        _should_continue_to_generate,
        {
            "continue": "generate",
            "refuse": "decide",
        },
    )
    graph_builder.add_edge("generate", "verify")
    graph_builder.add_edge("verify", "decide")
    graph_builder.add_edge("decide", END)
    graph_builder.add_edge("booking", END)

    return graph_builder.compile()


__all__ = ["build_graph"]