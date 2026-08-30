"""Agent construction for the Occlusion citation-grounded RAG agent.

Skeleton only — the bodies are yours to fill (TODO Phase 5).

What goes here (map to the plan):
  * which tools the agent can call (built in `tools.py`, imported at the bottom)
  * which generation model to use (sample.env Option A / Option B)
  * how the compiled graph from `graph.py` composes with a ``create_agent``
    tool-loop if you go that route (plan §3 keeps the LLM call inside a
    LangGraph node; a tool-based loop is the alternative worth weighing)

Verified against the installed versions (langgraph 1.1.10):
  * ``create_agent`` lives in ``langchain.agents`` — NOT in
    ``langgraph.prebuilt`` (that exports ``create_react_agent``, ``ToolNode``,
    ``tools_condition``, ...).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from langchain.agents import AgentState, create_agent
from langchain_core.documents import Document
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AnyMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool, tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.types import Command, RetryPolicy, Send

# Local contracts — schemas.py already exists; state.py holds GraphState.
from .schemas import (
    AgentOutput,
    Answer,
    CitationCheck,
    Refusal,
    RefusalReason,
    RetrievedChunk,
)
from .state import GraphState

# TODO Phase 4 / Phase 5 — once src/retrieve and tools.py exist, uncomment:
# from .tools import retrieval_tool, web_search_tool  # your tools


class RAGAgent:
    """Thin wrapper: owns the model, tools, maybe a checkpointer.

    TODO: decide whether you keep the plan's LangGraph pipeline (graph.py's
    `build_graph`) or a `create_agent` tool-loop; this wrapper should hide
    whichever you pick behind a single `.invoke(question)`.
    """

    def __init__(
        self,
        *,
        model: BaseChatModel,
        tools: Sequence[BaseTool] | None = None,
        checkpointer: MemorySaver = MemorySaver(),
    ) -> None:
        self.model = model
        self.tools = tools or []
        self.checkpointer = checkpointer
        ...

    def invoke(self, question: str) -> AgentOutput:
        """Run the pipeline for one user question and return Answer | Refusal."""
        ...


def build_agent(
    *,
    model: BaseChatModel,
    tools: Sequence[BaseTool],
    system_prompt: str | None = None,
    structured_responder: type[Answer] | None = None,
) -> RAGAgent:
    """TODO Phase 5.3 — agent factory.

    Wire the real `hybrid_search` (Phase 3/4) as a tool, attach the generation
    model, and return a ready-to-call RAGAgent. Keep the prompt from
    `prompts.SYSTEM_PROMPT` as a first-class artifact.
    """
    ...


def build_tools() -> list[BaseTool]:
    """TODO Phase 4/5 — wrap src/retrieve.hybrid_search into tools.

    Example shape (fill in):
        @tool
        def retrieval_tool(query: str) -> list[Document]:
            '''Hybrid BM25 + dense search over the dental corpus.'''
            ...
        return [retrieval_tool]
    """
    ...