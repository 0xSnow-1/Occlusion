"""Occlusion Streamlit demo (TODO Phase 9.1).

Chat UI over the production graph: conversation history, live pipeline
status (guardrail -> retrieve -> generate -> verify -> decide), and a trust
panel per answer (confidence meter, citation chips, retrieved-evidence
expander). Refusals render distinctly. Each question is independent —
no multi-turn memory enters the graph.

Run locally:  `uv run streamlit run src/ui/app.py`
Requires: ingested collection (`uv run python scripts/run_ingest.py` first)
and Bedrock credentials in `.env` (`AWS_BEARER_TOKEN_BEDROCK`).
"""

from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

# Streamlit runs this file with src/ui/ (not the repo root) on sys.path,
# so make repo-root imports (src.*) work from any launch directory —
# same bootstrap convention as scripts/run_agent.py.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from src.agent.graph import build_graph
from src.ingest.vector_store import VectorStore
from src.retrieve import make_retriever

logger = logging.getLogger(__name__)

COLLECTION_NAME = "occlusion"
QDRANT_PATH = "./data/qdrant_storage"
CONFIDENCE_THRESHOLD = 0.7
BEDROCK_MODEL_ID = os.getenv(
    "BEDROCK_MODEL_ID", "global.anthropic.claude-haiku-4-5-20251001-v1:0"
)
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-east-1")

DISCLAIMER = (
    "Patient-education assistant over public dental documentation — "
    "not a diagnostic tool. Emergency/triage guidance follows NHS UK sources. "
    "Always consult a dentist for decisions about your own care."
)


def _bare_citation(raw: str) -> str:
    """Strip optional SRC: prefix from citation for display as bare doc_id."""
    return raw[4:] if raw.startswith("SRC:") else raw


@st.cache_resource(show_spinner="Connecting to knowledge base…")
def get_pipeline():
    """Build the production pipeline once per session (Qdrant path mode holds
    an exclusive lock — one shared client, never one per question)."""
    from langchain_aws import ChatBedrockConverse

    store = VectorStore(
        collection_name=COLLECTION_NAME, qdrant_url=QDRANT_PATH
    )
    if not store.client.collection_exists(COLLECTION_NAME):
        raise RuntimeError(
            f"Collection {COLLECTION_NAME!r} not found in {QDRANT_PATH}. "
            "Run `uv run python scripts/run_ingest.py` first."
        )
    retriever = make_retriever(store.client, COLLECTION_NAME, variant="hybrid")
    llm = ChatBedrockConverse(
        model=BEDROCK_MODEL_ID, region_name=BEDROCK_REGION, temperature=0
    )
    graph = build_graph(
        retriever=retriever,
        llm=llm,
        confidence_threshold=CONFIDENCE_THRESHOLD,
    )
    points = store.client.count(collection_name=COLLECTION_NAME).count
    return graph, points


def run_question(graph, question: str) -> dict:
    """Stream one question through the graph, updating a status container per
    node, and return the final response + evidence for rendering/history."""
    stages = {
        "guardrail": "Scope check",
        "retrieve": "Retrieving evidence",
        "generate": "Drafting answer",
        "verify": "Verifying citations",
        "decide": "Applying safety gates",
    }
    state: dict = {
        "response": None,
        "chunks": [],
        "check": None,
        "gen_confidence": None,
    }
    t0 = time.monotonic()
    with st.status("Working…", expanded=True) as status:
        for update in graph.stream({"question": question}, stream_mode="updates"):
            for node, payload in update.items():
                label = stages.get(node, node)
                if node == "guardrail":
                    flag = (
                        "flagged out-of-scope"
                        if not payload["guardrail"].allowed
                        else "in scope"
                    )
                    status.update(label=f"{label}: {flag}")
                    status.write(f"Guardrail: {flag}.")
                elif node == "retrieve":
                    state["chunks"] = payload["fused_chunks"]
                    status.update(
                        label=f"{label}: {len(state['chunks'])} chunks"
                    )
                    status.write(
                        f"Retrieved {len(state['chunks'])} chunks "
                        f"({', '.join(dict.fromkeys(c.doc_id for c in state['chunks']))})."
                    )
                elif node == "generate":
                    state["gen_confidence"] = payload["candidate"].confidence
                    status.update(
                        label=f"{label} (confidence {state['gen_confidence']:.2f})"
                    )
                elif node == "verify":
                    state["check"] = payload["citation_check"]
                    check = state["check"]
                    status.update(
                        label=f"{label}: verified={check.verified} "
                        f"coverage={check.coverage:.0%}"
                    )
                elif node == "decide":
                    state["response"] = payload["response"]
                    verdict = (
                        "accepted"
                        if state["response"].kind == "answer"
                        else "refused"
                    )
                    status.update(
                        label=f"{label}: {verdict}", state="complete"
                    )
    state["latency_s"] = round(time.monotonic() - t0, 2)
    return state


def render_assistant(question: str, state: dict) -> None:
    """Render one assistant turn: answer/refusal + trust panel."""
    response = state["response"]
    with st.chat_message("assistant"):
        if response.kind == "answer":
            st.markdown(response.answer)
            st.progress(
                min(max(response.confidence, 0.0), 1.0),
                text=f"Confidence {response.confidence:.2f} "
                f"(threshold {CONFIDENCE_THRESHOLD:.2f})",
            )
            chips = " · ".join(
                f"`{_bare_citation(c)}`" for c in response.citations
            )
            st.caption(f"Sources: {chips}" if chips else "Sources: none")
            with st.expander(
                f"Retrieved evidence ({len(state['chunks'])} chunks)"
            ):
                for c in state["chunks"]:
                    st.markdown(f"**`{c.doc_id}`**")
                    st.caption(
                        c.text[:600] + ("…" if len(c.text) > 600 else "")
                    )
        else:
            reason = (
                "out of scope for this assistant"
                if response.reason == "out_of_scope"
                else "not enough reliable sources"
            )
            st.warning(
                f"I'm not able to answer that — {reason}.\n\n{response.message}"
            )
            st.caption(
                f"Gate: `{response.reason}` · "
                f"{state['latency_s']:.1f}s · no citations emitted by design"
            )


def main() -> None:
    st.set_page_config(
        page_title="Occlusion — Dental FAQ",
        page_icon="🦷",
        layout="centered",
    )
    st.title("🦷 Occlusion — Dental FAQ")
    st.caption(DISCLAIMER)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    try:
        graph, points = get_pipeline()
    except Exception as exc:  # misconfigured env/collection: fail loudly
        logger.error("Pipeline init failed: %s: %s", type(exc).__name__, exc)
        st.error(
            "The assistant could not start. "
            "Check that the Qdrant collection is ingested and Bedrock "
            f"credentials are set. Details: `{exc}`"
        )
        st.stop()

    with st.sidebar:
        st.header("About this demo")
        st.write(
            f"**{points}** knowledge-base chunks · hybrid retrieval (BM25 + dense, RRF)"
        )
        st.write(f"Model `{BEDROCK_MODEL_ID}` @ temperature 0")
        st.write(f"Refusal threshold `{CONFIDENCE_THRESHOLD:.2f}`")
        if st.button("Clear conversation"):
            st.session_state.messages = []
            st.rerun()

    for turn in st.session_state.messages:
        if turn["role"] == "user":
            with st.chat_message("user"):
                st.markdown(turn["content"])
        else:
            render_assistant(turn["question"], turn["state"])

    prompt = st.chat_input("Ask a routine dental-care question…")
    if prompt:
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        state = run_question(graph, prompt)
        st.session_state.messages.append(
            {"role": "assistant", "question": prompt, "state": state}
        )
        render_assistant(prompt, state)


if __name__ == "__main__":
    main()
