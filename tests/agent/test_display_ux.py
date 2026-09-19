"""Display UX: greeting intercept + human refusal gate captions.

Regression context: saying Hello ran the full RAG path and returned a
lecturing Gate-2 refusal, and every refusal caption rendered the raw enum
name (RefusalReason.INSUFFICIENT_CONTEXT). These tests pin the fix:
greeting-only messages are caught before the graph, and refusal captions
use human words plus the gate number that fired.
"""

from __future__ import annotations

import pytest

import src.ui.app as app


@pytest.mark.parametrize("text", ["Hello", "hello!", "hi", "hey", "good morning", "  Hi  "])
def test_greeting_only_messages_detected(text):
    assert app.is_greeting(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "Hello, how should I brush my teeth?",
        "hi, what dose of amoxicillin should I take?",
        "hey there dentist",
        "What is the capital of France?",
        "",
    ],
)
def test_non_greetings_pass_through(text):
    assert app.is_greeting(text) is False


def test_greeting_response_guides_without_citation_path():
    msg = app.greeting_response()
    assert "brush" in msg.lower() or "question" in msg.lower()
    assert "SRC:" not in msg


def test_gate_caption_gate0_guardrail():
    state = {
        "guardrail_allowed": False,
        "chunks": [],
        "check": None,
        "gen_confidence": None,
        "latency_s": 0.1,
    }
    caption = app.refusal_caption("out_of_scope", state)
    assert "Gate 0" in caption
    assert "RefusalReason" not in caption


def test_gate_caption_gate1_empty_retrieval():
    state = {
        "guardrail_allowed": True,
        "chunks": [],
        "check": None,
        "gen_confidence": None,
        "latency_s": 0.2,
    }
    caption = app.refusal_caption("insufficient_context", state)
    assert "Gate 1" in caption
    assert "RefusalReason" not in caption


def test_gate_caption_gate2_citation_check():
    class Check:
        verified = False

    state = {
        "guardrail_allowed": True,
        "chunks": ["c1"],
        "check": Check(),
        "gen_confidence": 0.95,
        "latency_s": 2.0,
    }
    caption = app.refusal_caption("insufficient_context", state)
    assert "Gate 2" in caption
    assert "RefusalReason" not in caption


def test_gate_caption_gate3_low_confidence():
    class Check:
        verified = True

    state = {
        "guardrail_allowed": True,
        "chunks": ["c1"],
        "check": Check(),
        "gen_confidence": 0.5,
        "latency_s": 2.0,
    }
    caption = app.refusal_caption("insufficient_context", state)
    assert "Gate 3" in caption
    assert "RefusalReason" not in caption
