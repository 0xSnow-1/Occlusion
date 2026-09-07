"""Deterministic pre-LLM guardrail (TODO Phase 7.2).

The "smoke detector" from the v3 architecture: plain regex rules, zero LLM
calls, zero tokens. Questions asking for a diagnosis, a medication decision,
or a treatment decision are flagged `out_of_scope` and routed to a refusal
BEFORE retrieval or generation run — even though retrieval would find chunks
(SCOPE.md §5: diagnosis/symptom advice is a hard line, not a soft one).

Deliberate tradeoff (documented, per TODO 7.2): rules are pattern-based, so
they are precise on decision-shaped questions but can over-block an edge-case
educational phrasing ("are my gums supposed to bleed when flossing?"). The
inverse error — answering a prescriptive question — is the zero-slack ship
gate, so rules bias toward flagging. The over-refusal rate is measured in
Phase 7.4, not vibes-checked here.

Boundary rules the tests pin (TODO 7.2 "the boundary cases are the whole
test"): general patient-ed questions pass even when they mention symptoms,
pain, treatments, or the writer's dentist ("what is a root canal — my dentist
says I might need one" must ANSWER). Hence: no bare keyword blocklist;
"pain", "antibiotic" etc. only fire in decision-shaped patterns.
"""

from __future__ import annotations

import logging
import re

from src.agent.schemas import GuardrailDecision

logger = logging.getLogger(__name__)

# Medication terms — only fire in combination with decision-shaped patterns.
_MEDICATION = (
    r"(amoxicillin|penicillin|antibiotic\w*|ibuprofen|paracetamol|aspirin|"
    r"advil|tylenol|nurofen|painkiller|pain killer|prescription|prescrib\w*|"
    r"medication\w*|medicine|sedat\w*|anaesthetic|anesthetic|nitrous oxide|"
    r"anticoagulant\w*|warfarin|steroid\w*|mouthwash)"
)

# Body parts for personal-state questions. Longer alternatives first so
# word boundaries resolve ("toothache" before "tooth").
_BODY_PART = (
    r"(toothache|wisdom teeth|wisdom tooth|teeth|tooth|gums|gum|jaw|mouth|"
    r"tongue|throat|lip|molar\w*|incisor\w*|filling\w*|crown\w*|implant\w*|"
    r"denture\w*|braces|aligner\w*|enamel|root)"
)

# Treatment nouns for decision questions.
_TREATMENT = (
    r"(root canal\w*|extraction\w*|extract\w*|filling\w*|crown\w*|implant\w*|"
    r"braces|aligner\w*|denture\w*|surgery|wisdom tooth removal|pull\w*|"
    r"remov\w*|whitening|veneer\w*|sealant\w*|scale and polish|biopsy)"
)

_SYMPTOM = (
    r"(hurt\w*|aching|ache|throbbing|bleeding|swollen|sensitive|wobbly|"
    r"loose|cracked|chipped|broken|black|discolou?red|infected|receding|numb)"
)

# (rule_name, pattern). First match wins; order = strongest signal first.
_RULES: list[tuple[str, str]] = [
    # -- Medication decisions: dosage/decision-shaped + a medication term --
    ("medication_dosage", rf"\b(dosage|dose|dosing)\b.{{0,60}}\b{_MEDICATION}\b"),
    ("medication_dosage", rf"\b{_MEDICATION}\b.{{0,60}}\b(dosage|dose|dosing)\b"),
    (
        "medication_decision",
        rf"\b(should|can|could) i (take|use|apply|drink|chew|crush|stop|start)\b"
        rf".{{0,60}}\b{_MEDICATION}\b",
    ),
    # -- Personal diagnosis: the question is about the asker's own state --
    # "do I have" but NOT "do I have to" (which is obligation, not diagnosis).
    ("personal_diagnosis", r"\bdo i have\b(?!\s+to\b)"),
    ("personal_diagnosis", rf"\b(is|are|was|were) my {_BODY_PART}\b"),
    ("personal_diagnosis", rf"\b(why|how come)\b.{{0,30}}\bmy {_BODY_PART}\b"),
    (
        "personal_diagnosis",
        rf"\bmy {_BODY_PART}\b.{{0,60}}\b{_SYMPTOM}\b",
    ),
    (
        "personal_diagnosis",
        rf"\bmy (bleeding|swollen|sensitive|aching|throbbing|wobbly|loose|"
        rf"cracked|chipped|broken|receding) {_BODY_PART}\b",
    ),
    # -- Treatment decisions: should/could I get/have <treatment>, do I need --
    (
        "treatment_decision",
        rf"\b(should|could) i (get|have|undergo|go for)\b.{{0,40}}\b{_TREATMENT}\b",
    ),
    ("treatment_decision", rf"\bdo i need\b.{{0,40}}\b{_TREATMENT}\b"),
]

_COMPILED = [(name, re.compile(p, re.IGNORECASE)) for name, p in _RULES]


def screen_question(question: str) -> GuardrailDecision:
    """Classify a question against the SCOPE.md taxonomy (pure code, no LLM).

    An empty/whitespace question is ALLOWED here — it is not the guardrail's
    call; the pipeline fail-closes on it later (empty retrieval → refusal).
    """
    if not question or not question.strip():
        return GuardrailDecision(allowed=True)

    for name, pattern in _COMPILED:
        if pattern.search(question):
            logger.debug("Guardrail rule %r matched question: %.80s", name, question)
            return GuardrailDecision(allowed=False, rule=name)

    return GuardrailDecision(allowed=True)


__all__ = ["screen_question"]