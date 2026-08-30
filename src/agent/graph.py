"""LangGraph scaffold — retrieve -> generate -> verify -> (gate) -> answer/refusal.

Layout (TODO Phase 5.3 + Phase 7):

    START -> preprocess -> retrieve -> generate -> verify -- gate --> END (answer)
                                                     |
                                                     +-> fail_closed -> END (refusal)

`preprocess` is an identity hook by default so query rewriting can be dropped in
later without rewiring the graph.

TODO (your code, per the session-starter prompt):
  - retriever:  the Phase 3/4 hybrid_search component from `src/retrieve/`
  - llm:        a provider ChatModel (sample.env Option A/B) supporting
                `.with_structured_output(Answer)`
  - Phase 7:    expand the gate with the SCOPE.md refusal taxonomy
                (diagnostic vs informational intent detection)
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import RetryPolicy

from .fusion import rrf_fuse
from .prompts import HUMAN_TEMPLATE, SYSTEM_PROMPT, assemble_context
from .schemas import Answer, Refusal, RefusalReason, RetrievedChunk
from .state import GateRoute, GraphState
from .verify import verify_citations

# Transient provider/Qdrant errors get retried; unexpected errors bubble up
# (langgraph-fundamentals: transient -> retry, unexpected -> raise).
TRANSIENT_ERRORS = RetryPolicy(max_attempts=3, initial_interval=1.0)


class HybridRetriever(Protocol):
    """`src/retrieve.hybrid_search` contract (Phase 4)."""

    def __call__(self, query: str, *, top_n: int) -> Sequence[RetrievedChunk]: ...


def _coerce_answer(raw: object) -> Answer:
    """Parse raw structured-output into `Answer`, *inside* the graph.

    TODO 5.3 pitfall: never let free text flow into state unvalidated. Providers
    sometimes return a pydantic model, a dict, or JSON (possibly wrapped in
    markdown fences) even when `.with_structured_output` is used.
    """
    if isinstance(raw, Answer):
        return raw
    if isinstance(raw, dict):
        return Answer.model_validate(raw)
    if hasattr(raw, "content"):
        content = getattr(raw, "content")
        if isinstance(content, dict):
            return Answer.model_validate(content)
        if isinstance(content, str):
            try:
                return Answer.model_validate_json(content)
            except Exception:
                json_text = content[content.find("{") : content.rfind("}") + 1]
                return Answer.model_validate_json(json_text)
    raise ValueError(
        "structured output did not match the Answer schema "
        f"(got {type(raw).__name__}); refusing to pass it downstream"
    )


def _stringify(raw: object) -> str:
    """Debug echo of the raw generation output (state.raw_llm_output)."""
    if isinstance(raw, Answer):
        return raw.model_dump_json()
    if isinstance(raw, str):
        return raw
    content = getattr(raw, "content", None)
    return content if isinstance(content, str) else str(raw)


def build_graph(
    *,
    retriever: HybridRetriever,
    llm: object,  # provider ChatModel with .with_structured_output(Answer)
    top_n: int = 5,
    confidence_threshold: float = 0.5,
    rewrite_query: Callable[[str], str] | None = None,
    checkpointer=None,  # Phase 9 / multi-turn only (sample.env: not needed for MVP)
) -> CompiledStateGraph:
    """Assemble and compile the retrieve -> generate -> verify -> gate graph."""

    def _preprocess(state: GraphState) -> dict:
        question = state["question"].strip()
        return {"query": rewrite_query(question) if rewrite_query else question}

    def _retrieve(state: GraphState) -> dict:
        query = state.get("query") or state["question"]
        chunks = list(retriever(query, top_n=top_n))
        return {"fused_chunks": chunks}

    def _generate(state: GraphState) -> dict:
        context = assemble_context(state["fused_chunks"], limit=top_n)
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(
                content=HUMAN_TEMPLATE.format(question=state["query"], context=context)
            ),
        ]
        structured_llm = llm.with_structured_output(Answer)
        raw = structured_llm.invoke(messages)
        return {"answer": _coerce_answer(raw), "raw_llm_output": _stringify(raw)}

    def _verify(state: GraphState) -> dict:
        answer = state["answer"]
        check = verify_citations(answer, state["fused_chunks"])
        return {"citation_check": check, "response": answer}

    def _gate(state: GraphState) -> GateRoute:
        """Fail-closed gate (Phase 7). One failure condition -> refuse."""
        if not state.get("fused_chunks"):
            return "fail_closed"
        answer = state.get("answer")
        check = state.get("citation_check")
        if answer is None or check is None or not check.verified:
            return "fail_closed"
        if answer.confidence < confidence_threshold:
            return "fail_closed"
        return END

    def _fail_closed(state: GraphState) -> dict:
        # TODO Phase 7: expand taxonomy per SCOPE.md — e.g. route
        # diagnostic vs informational intent to different reasons here.
        return {"response": Refusal(reason=RefusalReason.INSUFFICIENT_CONTEXT)}

    builder = StateGraph(GraphState)
    builder.add_node("preprocess", _preprocess)
    builder.add_node("retrieve", _retrieve, retry_policy=TRANSIENT_ERRORS)
    builder.add_node("generate", _generate, retry_policy=TRANSIENT_ERRORS)
    builder.add_node("verify", _verify)
    builder.add_node("fail_closed", _fail_closed)

    builder.add_edge(START, "preprocess")
    builder.add_edge("preprocess", "retrieve")
    builder.add_edge("retrieve", "generate")
    builder.add_edge("generate", "verify")
    builder.add_conditional_edges(
        "verify",
        _gate,
        {"fail_closed": "fail_closed", END: END},
    )
    builder.add_edge("fail_closed", END)

    return builder.compile(checkpointer=checkpointer, name="occlusion_rag_agent")