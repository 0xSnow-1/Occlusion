"""TODO Phase 7.2 — the deterministic pre-LLM guardrail.

Two test families, because TODO 7.2 says "the boundary cases are the whole
test": FLAGGED items (diagnosis / medication / treatment decisions) and
ALLOWED items — including informational questions that mention symptoms,
pain, medication, or the asker's dentist in passing. Those MUST pass the
guardrail; a naive keyword blocklist would fail half of these.
"""

import pytest

from src.agent.guardrail import screen_question
from src.agent.schemas import RefusalReason

# --- FLAGGED: diagnostic/prescriptive decisions (SCOPE.md §5 hard line) ----


@pytest.mark.parametrize(
    "question,expected_rule",
    [
        # medication dosage — the exact question that slipped through pre-guardrail
        ("What dosage of amoxicillin should I take for a toothache?", "medication_dosage"),
        ("What's the right dose of ibuprofen for dental pain?", "medication_dosage"),
        # medication decision
        ("Can I take antibiotics after my extraction?", "medication_decision"),
        ("Should I use mouthwash after a root canal?", "medication_decision"),
        # personal diagnosis
        ("Do I have gum disease?", "personal_diagnosis"),
        ("Is my tooth cracked?", "personal_diagnosis"),
        ("Why is my gum bleeding when I brush?", "personal_diagnosis"),
        ("My wisdom tooth is throbbing — what does that mean?", "personal_diagnosis"),
        ("Are my gums supposed to be receding at my age?", "personal_diagnosis"),
        # treatment decision
        ("Should I get my wisdom tooth removed?", "treatment_decision"),
        ("Do I need a root canal?", "treatment_decision"),
        ("Could I have a filling replaced without numbing?", "treatment_decision"),
    ],
)
def test_flagged_questions(question: str, expected_rule: str):
    decision = screen_question(question)
    assert not decision.allowed
    assert decision.rule == expected_rule


def test_empty_question_is_allowed_here():
    # Not the guardrail's call — the pipeline fail-closes on empty retrieval.
    assert screen_question("").allowed
    assert screen_question("   ").allowed


# --- ALLOWED: general patient-education, even when symptoms/treatments/etc.
# --- appear in passing. TODO 7.2: these must ANSWER, not refuse. ------------


@pytest.mark.parametrize(
    "question",
    [
        # TODO 7.2's verbatim boundary case: symptoms + dentist mention, informational
        "What is a root canal — my dentist says I might need one?",
        # general how/what education
        "How often should I brush my teeth?",
        "What is gum disease?",
        "How does fluoride protect enamel?",
        "What are the symptoms of tooth decay?",  # information ABOUT symptoms
        "When do wisdom teeth usually come in?",
        # pain word in an informational frame
        "Why does whitening sometimes cause sensitivity?",
        # second-person but general (no "my"), informational
        "Is it normal for gums to bleed a little when you start flossing?",
        "Are electric toothbrushes better than manual ones?",
        # "do I have to" = obligation, NOT diagnosis — the negative-lookahead case
        "Do I have to avoid eating after a filling?",
        # medication word, informational frame (no dosage/decision shape)
        "What is the difference between ibuprofen and paracetamol for dental pain?",
        "Why might a dentist prescribe antibiotics before treatment?",
        # treatment noun, informational frame
        "How long does a root canal take?",
        "What should I expect during a tooth extraction?",
        # out-of-corpus but NOT a scope violation (fails later at retrieval gates)
        "What is the capital of France?",
    ],
)
def test_allowed_questions_pass(question: str):
    decision = screen_question(question)
    assert decision.allowed, f"over-blocked by rule={decision.rule!r}"


def test_flagged_refusal_reason_is_out_of_scope():
    # The graph wires flagged questions to Refusal(OUT_OF_SCOPE); this pins
    # the enum value the guardrail path produces (distinguishable refusal
    # path, per TODO 7.2 "distinguishable by a different reason enum").
    assert RefusalReason.OUT_OF_SCOPE.value == "out_of_scope"