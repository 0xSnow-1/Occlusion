"""Recruiter tour: the demo offers the three documented example questions.

The README "Try it in 60 seconds" trio (one routine answer, one trap
refusal, one off-topic refusal) must exist as clickable demo buttons and
must all reach the graph (none may be greeting-only). Pinned here so the
tour cannot silently rot when questions change.
"""

from __future__ import annotations

import src.ui.app as app


def test_example_questions_are_documented_trio():
    assert len(app.EXAMPLE_QUESTIONS) == 3
    assert len(set(app.EXAMPLE_QUESTIONS)) == 3
    assert all(q.strip() for q in app.EXAMPLE_QUESTIONS)


def test_trio_covers_answer_trap_and_offtopic():
    joined = " ".join(app.EXAMPLE_QUESTIONS).lower()
    assert "brush my teeth" in joined  # routine -> cited answer
    assert "amoxicillin" in joined  # trap -> Gate-0 refusal
    assert "capital of france" in joined  # off-topic -> honest refusal


def test_example_questions_all_reach_graph():
    for q in app.EXAMPLE_QUESTIONS:
        assert app.is_greeting(q) is False
