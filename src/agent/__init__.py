"""Occlusion agent package — LangGraph retrieve -> generate -> verify pipeline.

Public surface: build the compiled graph with `build_graph(retriever=..., llm=...)`
and type contracts from `schemas`. See TODO Phase 5 for the build plan.
"""

from .fusion import rrf_fuse
from .graph import build_graph
from .prompts import SYSTEM_PROMPT, assemble_context
from .schemas import (
    AgentOutput,
    Answer,
    CitationCheck,
    Refusal,
    RefusalReason,
    RetrievedChunk,
)
from .state import GraphState
from .verify import extract_citations, verify_citations

__all__ = [
    "AgentOutput",
    "Answer",
    "CitationCheck",
    "GraphState",
    "Refusal",
    "RefusalReason",
    "RetrievedChunk",
    "SYSTEM_PROMPT",
    "assemble_context",
    "build_graph",
    "extract_citations",
    "rrf_fuse",
    "verify_citations",
]
