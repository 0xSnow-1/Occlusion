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

import csv
import io
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Streamlit runs this file with src/ui/ (not the repo root) on sys.path,
# so make repo-root imports (src.*) work from any launch directory —
# same bootstrap convention as scripts/run_agent.py.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from zoneinfo import ZoneInfo

from src.agent.callbacks import append_callback, read_callbacks
from src.agent.graph import build_graph
from src.agent.schemas import Contact
from src.eval.deflection import summarize_runs
from src.ingest.vector_store import VectorStore
from src.retrieve import make_retriever

logger = logging.getLogger(__name__)

COLLECTION_NAME = "occlusion"
QDRANT_PATH = "./data/qdrant_storage"
CONFIDENCE_THRESHOLD = 0.7
STAFF_CODE = os.getenv("STAFF_CODE", "") or ""
CAL_TIMEZONE = os.getenv("CAL_TIMEZONE", "UTC") or "UTC"
BEDROCK_MODEL_ID = os.getenv(
    "BEDROCK_MODEL_ID", "global.anthropic.claude-haiku-4-5-20251001-v1:0"
)
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-east-1")

DISCLAIMER = (
    "Patient-education assistant over public dental documentation — "
    "not a diagnostic tool. Emergency/triage guidance follows NHS UK sources. "
    "Always consult a dentist for decisions about your own care."
)

SUGGESTED = [
    "How often should I brush my teeth?",
    "Is flossing really necessary?",
    "What are the signs of gum disease?",
    "What causes dry mouth?",
    "Can I book a cleaning tomorrow morning?",
]



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


def run_question(graph, question: str, contact: Contact | None = None) -> dict:
    """Stream one question through the graph, updating a status container per
    node, and return the final response + evidence for rendering/history."""
    stages = {
        "guardrail": "Scope check",
        "retrieve": "Retrieving evidence",
        "generate": "Drafting answer",
        "verify": "Verifying citations",
        "decide": "Applying safety gates",
        "booking": "Checking calendar",
    }
    state: dict = {
        "response": None,
        "chunks": [],
        "check": None,
        "gen_confidence": None,
        "slots": [],
        "receipt": None,
    }
    t0 = time.monotonic()
    payload_in: dict = {"question": question}
    if contact is not None:
        payload_in["contact"] = contact
    with st.status("Working…", expanded=True) as status:
        for update in graph.stream(payload_in, stream_mode="updates"):
            for node, payload in update.items():
                label = stages.get(node, node)
                if node == "guardrail":
                    flag = (
                        "flagged out-of-scope"
                        if not payload["guardrail"].allowed
                        else "in scope"
                    )
                    intent = payload.get("booking_intent")
                    extra = " + booking intent" if intent is not None and intent.wants_booking else ""
                    status.update(label=f"{label}: {flag}{extra}")
                    status.write(f"Guardrail: {flag}{extra}.")
                elif node == "booking":
                    state["slots"] = payload.get("slots", [])
                    state["receipt"] = payload.get("booking_receipt")
                    state["response"] = payload["response"]
                    status.update(
                        label=f"{label}: {len(state['slots'])} slots", state="complete"
                    )
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


def _display_slot(iso_utc: str) -> str:
    """Convert a UTC ISO time to clinic tz for display only (wire stays UTC)."""
    try:
        dt = datetime.fromisoformat(iso_utc.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))
        return dt.astimezone(ZoneInfo(CAL_TIMEZONE)).strftime("%a %d %b %H:%M")
    except (ValueError, TypeError):
        return iso_utc


def render_assistant(question: str, state: dict) -> None:
    """Render one assistant turn: answer/refusal/booking + trust panel."""
    response = state["response"]
    with st.chat_message("assistant"):
        receipt = state.get("receipt")
        slots = state.get("slots", [])
        if receipt is not None and receipt.ok:
            when = receipt.start_utc.isoformat() if receipt.start_utc else ""
            st.success(
                f"Booked {receipt.title or 'appointment'} at {when} UTC. "
                f"UID `{receipt.uid}`. A confirmation email was sent by cal.com."
            )
        elif response.kind == "answer" and slots:
            st.markdown(f"I found **{len(slots)}** open times. Pick one to continue:")
            grouped: dict[str, list] = {}
            for s in slots[:16]:
                iso = s.start_utc.isoformat() if hasattr(s.start_utc, "isoformat") else str(s.start_utc)
                try:
                    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
                    local = dt.astimezone(ZoneInfo(CAL_TIMEZONE))
                    day = local.strftime("%a %d %b")
                    label = local.strftime("%H:%M")
                except (ValueError, TypeError):
                    day, label = iso, iso
                grouped.setdefault(day, []).append((iso, label))
            n = 0
            for day, items in grouped.items():
                st.caption(f"**{day}** ({CAL_TIMEZONE})")
                for i in range(0, len(items), 4):
                    cols = st.columns(4)
                    for col, (iso, label) in zip(cols, items[i : i + 4]):
                        with col:
                            if st.button(label, key=f"slot-{iso}-{len(st.session_state.messages)}-{n}"):
                                st.session_state.picked_slot = iso
                                st.session_state.booking_question = question
                                st.rerun()
                        n += 1
        elif response.kind == "answer":
            st.markdown(response.answer)
            st.progress(
                min(max(response.confidence, 0.0), 1.0),
                text=f"Confidence {response.confidence:.2f} "
                f"(threshold {CONFIDENCE_THRESHOLD:.2f})",
            )
            check = state["check"]
            chips = " · ".join(
                f"`{c}`" for c in dict.fromkeys(check.cited_ids)
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


def _log_run(state: dict) -> None:
    """Append a counts-only run record for the scoreboard (no text stored)."""
    response = state["response"]
    receipt = state.get("receipt")
    if receipt is not None and receipt.ok:
        outcome = "booked"
    elif response.kind == "answer":
        outcome = "handled"
    else:
        outcome = "callback"
    st.session_state.runs.append(
        {"outcome": outcome, "latency_s": state.get("latency_s", 0.0)}
    )


def _callback_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["name", "phone", "question_hash", "reason", "timestamp"])
    for r in rows:
        cells = [
            str(r.get(k, "") or "")
            for k in ("name", "phone", "question_hash", "reason", "timestamp")
        ]
        writer.writerow(
            ["'" + c if c.startswith(("=", "+", "-", "@")) else c for c in cells]
        )
    return buf.getvalue()


def render_staff_callbacks() -> None:
    """Staff-only callback view (SPEC_V2 §8). Fail-closed: without a
    configured STAFF_CODE, or until the code is entered, no callback
    record is rendered or downloadable."""
    if not STAFF_CODE:
        st.caption(
            "Staff callback view needs `STAFF_CODE` set in .env. "
            "Callback records are never shown without it."
        )
        return
    if not st.session_state.get("staff_unlocked"):
        entered = st.text_input("Staff code", type="password", key="staff_code_input")
        if entered and entered == STAFF_CODE:
            st.session_state.staff_unlocked = True
            st.rerun()
        elif entered:
            st.error("Incorrect staff code.")
        return
    rows = read_callbacks()
    if rows:
        st.table(rows[-10:])
        st.download_button(
            "Download CSV",
            data=_callback_csv(rows),
            file_name="callbacks.csv",
            mime="text/csv",
        )
    else:
        st.caption("No callbacks yet.")


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
    if "runs" not in st.session_state:
        st.session_state.runs = []
    if "picked_slot" not in st.session_state:
        st.session_state.picked_slot = None
    if "booking_question" not in st.session_state:
        st.session_state.booking_question = None
    if "staff_unlocked" not in st.session_state:
        st.session_state.staff_unlocked = False

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
        score = summarize_runs(st.session_state.runs)
        st.header("Scoreboard (this session)")
        st.write(
            f"Answered **{score['handled']}** · Booked **{score['booked']}** · "
            f"Callback **{score['callback']}** · p50 **{score['p50_latency_s']}s** · "
            f"p95 **{score['p95_latency_s']}s** · ~$**{score['cost_per_day_usd']}**/day @500"
        )
        st.header("Callback list (staff)")
        render_staff_callbacks()
        if st.button("Clear conversation"):
            st.session_state.messages = []
            st.session_state.runs = []
            st.session_state.picked_slot = None
            st.session_state.booking_question = None
            st.rerun()

    for turn in st.session_state.messages:
        if turn["role"] == "user":
            with st.chat_message("user"):
                st.markdown(turn["content"])
        else:
            render_assistant(turn["question"], turn["state"])

    if st.session_state.picked_slot:
        st.info(
            f"Selected {_display_slot(st.session_state.picked_slot)} ({CAL_TIMEZONE}). "
            "Enter your details to confirm — or pick another slot above."
        )
        with st.form("confirm-booking"):
            name = st.text_input("Name")
            email = st.text_input("Email")
            if st.form_submit_button("Confirm booking"):
                if not name.strip() or not email.strip():
                    st.error("Name and email are required.")
                else:
                    full_q = f"{st.session_state.booking_question} {st.session_state.picked_slot}"
                    state = run_question(
                        graph, full_q, Contact(name=name.strip(), email=email.strip())
                    )
                    st.session_state.messages.append(
                        {"role": "assistant", "question": full_q, "state": state}
                    )
                    _log_run(state)
                    st.session_state.picked_slot = None
                    st.session_state.booking_question = None
                    st.rerun()
        if st.button("Clear selected slot"):
            st.session_state.picked_slot = None
            st.session_state.booking_question = None
            st.rerun()

    prompt = st.chat_input("Ask a routine dental-care question…")
    picked = None
    st.caption("Try one:")
    cols = st.columns(len(SUGGESTED))
    for col, q in zip(cols, SUGGESTED):
        with col:
            if st.button(q, key=f"try-{q[:20]}"):
                picked = q
    pending = picked or prompt
    if pending:
        prompt = pending
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        state = run_question(graph, prompt)
        st.session_state.messages.append(
            {"role": "assistant", "question": prompt, "state": state}
        )
        _log_run(state)
        render_assistant(prompt, state)
        if state["response"].kind == "refusal":
            with st.form(f"callback-{len(st.session_state.messages)}"):
                st.write("Leave details and we will call you back:")
                cb_name = st.text_input("Name")
                cb_phone = st.text_input("Phone")
                if st.form_submit_button("Request callback"):
                    if not cb_name.strip() or not cb_phone.strip():
                        st.error("Name and phone are required.")
                    else:
                        append_callback(
                            cb_name.strip(),
                            cb_phone.strip(),
                            prompt,
                            state["response"].reason,
                        )
                        st.success("Thanks — we will call you back.")


if __name__ == "__main__":
    main()
