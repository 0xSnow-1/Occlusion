"""LangGraph agent implementation for dental RAG (TODO Phases 5.3 + 7.2)."""

from __future__ import annotations

import logging
from typing import Callable, List

from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agent.guardrail import screen_question
from src.agent.prompts import format_dental_qa_prompt
from src.agent.schemas import (
    AgentOutput,
    Answer,
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
        logger.info(
            "Guardrail: allowed=%s rule=%s question=%.60s",
            decision.allowed,
            decision.rule,
            state["question"],
        )
        return {"guardrail": decision}
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
    """Route from guardrail node: flagged → refusal gate, else → retrieval."""
    return "retrieve" if state["guardrail"].allowed else "decide"


def _generate_node(llm):
    """Generate node: builds prompt with [SRC:doc_id] anchors and calls LLM."""
    def generate_node(state: AgentState) -> dict:
        # If no chunks, return empty update (handled by decide node)
        if not state["fused_chunks"]:
            return {}
        
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


def _create_refusal(reason: RefusalReason) -> AgentOutput:
    """Create a refusal with the given reason; message is the patient-safe
    default from schemas.py (fail closed by construction)."""
    return Refusal(reason=reason)


def build_graph(
    retriever: Callable[..., List[RetrievedChunk]],
    llm,
    confidence_threshold: float = 0.7,
) -> CompiledStateGraph:
    """Build and compile the LangGraph agent.

    Wiring (nodes and edges are defined above; this assembles them):

        guardrail -> retrieve -> [chunks? generate -> verify] -> decide -> END
            \\-(flagged)------------------------------^   (LLM never called)
                     \\---- (empty) -----------------^

    Args:
        retriever: Function signature (query: str, *, top_n: int) -> list[RetrievedChunk]
        llm: Language model with .with_structured_output(Answer) method
        confidence_threshold: Minimum confidence score to accept answer (0-1)

    Returns:
        Compiled StateGraph ready for invocation
    """
    graph_builder = StateGraph(AgentState)

    graph_builder.add_node("guardrail", _guardrail_node())
    graph_builder.add_node("retrieve", _retrieve_node(retriever))
    graph_builder.add_node("generate", _generate_node(llm))
    graph_builder.add_node("verify", _verify_node())
    graph_builder.add_node("decide", _decide_node(confidence_threshold))

    graph_builder.set_entry_point("guardrail")

    # Flagged questions (diagnostic/prescriptive/out-of-scope) go straight
    # to the refusal gate — retrieval and the LLM never run (TODO 7.2).
    # Allowed questions continue into the normal RAG path.
    graph_builder.add_conditional_edges(
        "guardrail",
        _route_after_guardrail,
        {"retrieve": "retrieve", "decide": "decide"},
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

    return graph_builder.compile()


__all__ = ["build_graph"]