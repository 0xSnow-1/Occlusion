"""TODO Phase 5.1 — schema contract tests.

Good output validates; malformed output must raise, not slop through.
"""

import pytest
from pydantic import TypeAdapter, ValidationError

from src.agent.schemas import (
    AgentOutput,
    Answer,
    CitationCheck,
    Refusal,
    RefusalReason,
)


class TestAnswer:
    def test_valid_answer(self):
        answer = Answer(
            answer="Fluoride helps remineralize enamel.",
            citations=["ada-guide-001", "nih-2017"],
            confidence=0.92,
        )
        assert answer.kind == "answer"
        assert answer.citations == ["ada-guide-001", "nih-2017"]

    @pytest.mark.parametrize("bad_confidence", [1.01, -0.5])
    def test_confidence_bounds_enforced(self, bad_confidence):
        with pytest.raises(ValidationError):
            Answer(answer="x", citations=[], confidence=bad_confidence)

    def test_empty_answer_rejected(self):
        with pytest.raises(ValidationError):
            Answer(answer="", citations=[], confidence=0.5)

    def test_non_string_citation_rejected(self):
        with pytest.raises(ValidationError):
            Answer(answer="x", citations=[123], confidence=0.5)


class TestRefusal:
    def test_default_message_filled_when_omitted(self):
        refusal = Refusal(reason=RefusalReason.INSUFFICIENT_CONTEXT)
        assert "consult a dentist" in refusal.message

    def test_custom_message_wins(self):
        refusal = Refusal(reason=RefusalReason.OUT_OF_SCOPE, message="nope")
        assert refusal.message == "nope"


class TestAgentOutputDiscriminatedUnion:
    """AgentOutput must round-trip both members via the `kind` discriminator."""

    adapter = TypeAdapter(AgentOutput)

    def test_answer_member(self):
        obj = self.adapter.validate_python(
            {"kind": "answer", "answer": "x", "citations": [], "confidence": 0.5}
        )
        assert isinstance(obj, Answer)

    def test_refusal_member(self):
        obj = self.adapter.validate_python(
            {"kind": "refusal", "reason": "insufficient_context"}
        )
        assert isinstance(obj, Refusal)
        assert obj.reason == RefusalReason.INSUFFICIENT_CONTEXT

    def test_missing_kind_rejected(self):
        with pytest.raises(ValidationError):
            self.adapter.validate_python({"answer": "x", "citations": []})


class TestCitationCheck:
    def test_valid(self):
        c = CitationCheck(
            verified=False,
            cited_ids=[],
            retrieved_ids=[],
            fabricated_ids=[],
            matches=0,
            total=0,
            coverage=0.0,
        )
        assert c.coverage == 0.0