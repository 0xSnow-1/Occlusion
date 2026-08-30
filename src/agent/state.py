"""GraphState — the graph's shared memory (TODO Phase 5.3).

Convention (langgraph-fundamentals): nodes return *partial* dicts and LangGraph
merges them by key. No reducers are needed here because every key is written by
exactly one node on the linear path. If you later add multi-turn memory or
parallel retrieval branches that must *append*, add
`Annotated[list, operator.add]` to the field — but for this MVP's single-pass
flow, last-write-wins is exactly correct.
"""

from __future__ import annotations

from typing import Literal, TypedDict

from .schemas import Answer, CitationCheck, Refusal, RetrievedChunk


class GraphState(TypedDict, total=False):
    question: str  # original user question (entry)
    query: str  # rewritten query (preprocess node output)
    fused_chunks: list[RetrievedChunk]  # hybrid retrieval result (retrieve)
    raw_llm_output: str  # debug echo of the generation node output
    answer: Answer | None  # structured generation output (generate)
    citation_check: CitationCheck | None  # verifier result (verify)
    response: Answer | Refusal | None  # what callers consume; set by verify/fail_closed
    metrics: dict  # TODO Phase 5.5: latency / tokens / cost per run


# Values returned by the gate router. "__end__" is LangGraph's END constant.
GateRoute = Literal["fail_closed", "__end__"]