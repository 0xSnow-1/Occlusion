"""TODO Phase 5.4 — citation verification, including the hostile test."""

from src.agent.schemas import Answer, RetrievedChunk
from src.agent.verify import (
    extract_citations,
    strip_fabricated_tokens,
    verify_citations,
)

RETRIEVED = [
    RetrievedChunk(doc_id="ada-guide-001", text="..."),
    RetrievedChunk(doc_id="nih-2017", text="..."),
]


def _answer(text: str, citations=None, confidence=0.9) -> Answer:
    return Answer(answer=text, citations=citations or [], confidence=confidence)


def test_extract_citations_multiple_inline():
    text = "[SRC:ada-guide-001] one claim [SRC:nih-2017] and [SRC:ada-guide-001] again."
    assert extract_citations(text) == ["ada-guide-001", "nih-2017", "ada-guide-001"]


def test_legitimate_answer_verifies():
    answer = _answer(
        "Enamel loss is irreversible [SRC:ada-guide-001]. "
        "Fluoride helps [SRC:nih-2017]."
    )
    check = verify_citations(answer, RETRIEVED)
    assert check.verified
    assert check.coverage == 1.0
    assert check.fabricated_ids == []


def test_fabricated_citation_is_caught():
    # HOSTILE TEST (TODO 5.4): cites an id that was never retrieved.
    answer = _answer("SDF arrests caries [SRC:made-up-999].")
    check = verify_citations(answer, RETRIEVED)
    assert not check.verified
    assert check.fabricated_ids == ["made-up-999"]
    assert check.coverage == 0.0


def test_mixed_citations_partial_coverage():
    answer = _answer("Real [SRC:ada-guide-001] and fake [SRC:fake-001].")
    check = verify_citations(answer, RETRIEVED)
    assert not check.verified
    assert check.matches == 1 and check.total == 2
    assert check.coverage == 0.5


def test_no_citations_fails_closed():
    answer = _answer("A confident answer with no grounding at all.")
    check = verify_citations(answer, RETRIEVED)
    assert not check.verified
    assert check.coverage == 0.0


def test_strip_fabricated_tokens_masks_only_bad_ids():
    text = "Real [SRC:ada-guide-001] fake [SRC:fake-001] end"
    cleaned = strip_fabricated_tokens(text, ["fake-001"])
    assert cleaned == "Real [SRC:ada-guide-001] fake  end"