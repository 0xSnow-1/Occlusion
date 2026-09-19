"""Occlusion Gradio demo for Hugging Face ZeroGPU (free) Spaces.

Same production graph as the V1 Streamlit UI (`src/ui/app.py` is canonical
for wording — DISCLAIMER/OGL/citation helpers are duplicated here so this
module never imports streamlit): conversation history, cited answers with
confidence, distinctly rendered refusals, and a retrieved-evidence panel.
V1 scope only: no booking, no callbacks, no scoreboard. Each question is
independent — no multi-turn memory enters the graph.

Space layout (assembled at push time, NOT committed to this repo):
    <space-root>/src/...  (copied from this repo)
    <space-root>/data/qdrant_storage/  (vendored prebuilt index)
    <space-root>/requirements.txt  (see spaces/zerogpu/requirements.txt)
    <space-root>/README.md  (see spaces/zerogpu/README.md for frontmatter)
"""

from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path

import gradio as gr
from dotenv import load_dotenv

load_dotenv()

from src.agent.graph import build_graph
from src.ingest.vector_store import VectorStore
from src.retrieve import make_retriever

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
QDRANT_PATH = str(ROOT / "data" / "qdrant_storage")
COLLECTION_NAME = "occlusion"
CONFIDENCE_THRESHOLD = 0.7
BEDROCK_MODEL_ID = os.getenv(
    "BEDROCK_MODEL_ID", "global.anthropic.claude-haiku-4-5-20251001-v1:0"
)
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-east-1")

# Duplicated from src/ui/app.py (canonical copy) to avoid importing streamlit.
OGL_ATTRIBUTION = (
    "Contains public sector information licensed "
    "under the Open Government Licence v3.0."
)
DISCLAIMER = (
    "Patient-education assistant over public dental documentation — "
    "not a diagnostic tool. Emergency/triage guidance follows NHS UK sources. "
    "Always consult a dentist for decisions about your own care. "
    + OGL_ATTRIBUTION
)


def citation_link(doc_id: str, source_url: str | None) -> str:
    """Clickable markdown link when a URL is known, else a bare chip."""
    if source_url and source_url.startswith(("http://", "https://")):
        return f"[{doc_id}]({source_url})"
    return f"`{doc_id}`"


def _source_url_for(chunks, doc_id: str) -> str | None:
    """First known URL for a cited doc_id (None for legacy chunks)."""
    for c in chunks:
        if getattr(c, "doc_id", None) == doc_id and getattr(c, "source_url", None):
            return c.source_url
    return None


def _conf_bar(confidence: float) -> str:
    filled = int(round(min(max(confidence, 0.0), 1.0) * 10))
    return "█" * filled + "░" * (10 - filled)


_pipeline_lock = threading.Lock()
_pipeline = None


def get_pipeline():
    """Build the production pipeline once per container (lazy, thread-safe)."""
    global _pipeline
    if _pipeline is not None:
        return _pipeline
    with _pipeline_lock:
        if _pipeline is not None:
            return _pipeline
        from langchain_aws import ChatBedrockConverse

        store = VectorStore(
            collection_name=COLLECTION_NAME, qdrant_url=QDRANT_PATH
        )
        if not store.client.collection_exists(COLLECTION_NAME):
            raise RuntimeError(
                f"Collection {COLLECTION_NAME!r} not found in {QDRANT_PATH}. "
                "Vendor a prebuilt index (see spaces/zerogpu)."
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
        try:
            retriever("dental checkup", top_n=1)  # warm embedding models
        except Exception as exc:
            logger.warning("Warmup encode failed: %s: %s", type(exc).__name__, exc)
        _pipeline = (graph, points)
        return _pipeline


def run_turn(question: str) -> dict:
    """Stream one question through the V1 graph; return response + evidence."""
    graph, _ = get_pipeline()
    state: dict = {"response": None, "chunks": [], "check": None}
    t0 = time.monotonic()
    for update in graph.stream({"question": question}, stream_mode="updates"):
        for node, payload in update.items():
            if node == "retrieve":
                state["chunks"] = payload["fused_chunks"]
            elif node == "verify":
                state["check"] = payload["citation_check"]
            elif node == "decide":
                state["response"] = payload["response"]
    state["latency_s"] = round(time.monotonic() - t0, 2)
    return state


def _render_assistant(turn: dict) -> str:
    """Render one assistant turn as chat markdown (mirrors app.py)."""
    response = turn["response"]
    if response.kind == "answer":
        chips = " · ".join(
            citation_link(c, _source_url_for(turn["chunks"], c))
            for c in turn["check"].cited_ids
        )
        return (
            f"{response.answer}\n\n"
            f"{_conf_bar(response.confidence)} Confidence "
            f"{response.confidence:.2f} (threshold {CONFIDENCE_THRESHOLD:.2f})\n\n"
            f"Sources: {chips if chips else 'none'}\n\n_{OGL_ATTRIBUTION}_"
        )
    reason = (
        "out of scope for this assistant"
        if response.reason == "out_of_scope"
        else "not enough reliable sources"
    )
    return (
        f"⚠️ I'm not able to answer that — {reason}.\n\n{response.message}\n\n"
        f"_Gate `{response.reason}` · {turn['latency_s']:.1f}s · "
        "no citations emitted by design._"
    )


def _render_evidence(turn: dict | None) -> str:
    if not turn or not turn.get("chunks"):
        return "No chunks retrieved on this turn."
    parts = []
    for c in turn["chunks"]:
        label = (
            f"[{c.doc_id}]({c.source_url})" if c.source_url else f"**`{c.doc_id}`**"
        )
        text = c.text[:600] + ("…" if len(c.text) > 600 else "")
        parts.append(f"{label}\n\n{text}")
    return "\n\n---\n\n".join(parts)


def _render_status(turn: dict | None) -> str:
    if not turn:
        return "Ask a question to begin."
    check = turn.get("check")
    cov = f"{check.coverage:.0%}" if check is not None else "n/a"
    ver = check.verified if check is not None else "n/a"
    return (
        f"**Last run:** {len(turn.get('chunks', []))} chunks · "
        f"verified={ver} coverage={cov} · {turn.get('latency_s', 0):.1f}s"
    )


def submit(question: str, messages: list):
    """Chat send: run the graph and refresh chat + evidence + status."""
    question = (question or "").strip()
    if not question:
        yield messages, "", "Ask a question to begin.", "No chunks retrieved on this turn."
        return
    messages = messages + [{"role": "user", "content": question}]
    yield messages, "", "Working…", "Retrieving evidence…"
    try:
        turn = run_turn(question)
    except Exception as exc:
        logger.error("Pipeline failed: %s: %s", type(exc).__name__, exc)
        messages = messages + [
            {"role": "assistant", "content": f"⚠️ The assistant could not start: `{exc}`"}
        ]
        yield messages, "", "Pipeline failed — check collection and credentials.", "No chunks retrieved on this turn."
        return
    messages = messages + [{"role": "assistant", "content": _render_assistant(turn)}]
    yield messages, "", _render_status(turn), _render_evidence(turn)


def build_demo() -> gr.Blocks:
    try:
        _, points = get_pipeline()
        about = (
            f"**{points}** knowledge-base chunks · hybrid retrieval (BM25 + dense, RRF) · "
            f"model `{BEDROCK_MODEL_ID}` @ temperature 0 · "
            f"refusal threshold `{CONFIDENCE_THRESHOLD:.2f}`"
        )
    except Exception as exc:
        logger.error("Pipeline init failed: %s: %s", type(exc).__name__, exc)
        with gr.Blocks(title="Occlusion — Dental FAQ") as demo:
            gr.Markdown("# 🦷 Occlusion — Dental FAQ")
            gr.Markdown(DISCLAIMER)
            gr.Markdown(
                "⚠️ The assistant could not start. Check that the Qdrant "
                f"collection is ingested and Bedrock credentials are set. Details: `{exc}`"
            )
        return demo
    with gr.Blocks(title="Occlusion — Dental FAQ") as demo:
        gr.Markdown("# 🦷 Occlusion — Dental FAQ")
        gr.Markdown(DISCLAIMER)
        gr.Markdown(about)
        with gr.Row():
            with gr.Column(scale=3):
                chat = gr.Chatbot(label="Conversation", height=480)
                box = gr.Textbox(label="Ask a routine dental-care question…")
                with gr.Row():
                    send = gr.Button("Send", variant="primary")
                    clear = gr.Button("Clear conversation")
                with gr.Accordion("Retrieved evidence", open=False):
                    evidence_md = gr.Markdown("No chunks retrieved on this turn.")
            with gr.Column(scale=1):
                status = gr.Markdown("Ask a question to begin.")
                gr.Markdown(
                    "### About this demo\n\n"
                    "Cited answers or safe refusal — never a confident guess.\n\n"
                    "Each question is independent; no multi-turn memory enters the graph."
                )
        send.click(submit, inputs=[box, chat], outputs=[chat, box, status, evidence_md])
        box.submit(submit, inputs=[box, chat], outputs=[chat, box, status, evidence_md])
        clear.click(
            lambda: ([], "", "Ask a question to begin.", "No chunks retrieved on this turn."),
            inputs=[],
            outputs=[chat, box, status, evidence_md],
        )
    return demo


demo = build_demo()


if __name__ == "__main__":
    demo.launch()
