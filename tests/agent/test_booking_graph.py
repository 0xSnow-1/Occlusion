"""SPEC_V2 §9 — booking graph tests (mocked tools, never real cal.com).

Booking intent skips LLM/retrieval; Q&A path stays byte-identical;
double-book falls back to a callback offer.
"""

from datetime import datetime, timezone

import pytest

from src.agent.graph import build_graph
from src.agent.schemas import (
    Answer,
    BookingReceipt,
    Contact,
    EventType,
    Refusal,
    RefusalReason,
    RetrievedChunk,
)

STUB_CHUNK = RetrievedChunk(
    doc_id="ada-guide-001",
    text="Silver diamine fluoride (SDF) can arrest early caries lesions.",
)
EVENT = EventType(id=456, slug="cleaning", title="Cleaning", duration_min=30)
SLOT_TIME = datetime(2026, 9, 12, 9, 0, tzinfo=timezone.utc)

BOOK_Q = "Can I book a cleaning tomorrow morning?"


class CountingRetriever:
    def __init__(self):
        self.calls = 0

    def __call__(self, query: str, *, top_n: int):
        self.calls += 1
        return [STUB_CHUNK]


class CountingLLM:
    def __init__(self, output):
        self._output = output
        self.calls = 0

    def with_structured_output(self, schema):
        assert schema is Answer
        return self

    def invoke(self, messages):
        self.calls += 1
        return self._output


def _slot():
    from src.agent.schemas import Slot

    return Slot(start_utc=SLOT_TIME, eventTypeId=456)


def test_booking_intent_skips_llm_and_retrieval():
    retriever = CountingRetriever()
    llm = CountingLLM(
        Answer(answer="should never be used [SRC:ada-guide-001].", citations=["ada-guide-001"], confidence=0.9)
    )
    tool_calls = {"slots": 0}

    def fake_slots(eventTypeId, start, end, timeZone):
        tool_calls["slots"] += 1
        return [_slot()]

    graph = build_graph(
        retriever=retriever,
        llm=llm,
        list_event_types_fn=lambda: [EVENT],
        get_slots_fn=fake_slots,
        create_booking_fn=lambda *a: (_ for _ in ()).throw(AssertionError("must not book yet")),
    )
    out = graph.invoke({"question": BOOK_Q})
    assert retriever.calls == 0
    assert llm.calls == 0
    assert tool_calls["slots"] == 1
    assert isinstance(out["response"], Answer)
    assert "2026-09-12" in out["response"].answer
    assert len(out["slots"]) == 1
    assert out["booking_receipt"] is None


def test_booking_creates_booking_when_contact_and_time():
    retriever = CountingRetriever()
    llm = CountingLLM(
        Answer(answer="unused [SRC:ada-guide-001].", citations=["ada-guide-001"], confidence=0.9)
    )
    receipt = BookingReceipt(ok=True, uid="abc123", title="Cleaning", start_utc=SLOT_TIME)

    graph = build_graph(
        retriever=retriever,
        llm=llm,
        list_event_types_fn=lambda: [EVENT],
        get_slots_fn=lambda *a: [_slot()],
        create_booking_fn=lambda *a: receipt,
    )
    out = graph.invoke(
        {
            "question": "Book cleaning 2026-09-12T09:00:00Z tomorrow morning please",
            "contact": Contact(name="Ana", email="ana@mail.com"),
        }
    )
    assert retriever.calls == 0
    assert llm.calls == 0
    assert out["booking_receipt"].ok is True
    assert isinstance(out["response"], Answer)
    assert "abc123" in out["response"].answer


def test_double_book_falls_back_to_callback_offer():
    graph = build_graph(
        retriever=CountingRetriever(),
        llm=CountingLLM(
            Answer(answer="unused [SRC:ada-guide-001].", citations=["ada-guide-001"], confidence=0.9)
        ),
        list_event_types_fn=lambda: [EVENT],
        get_slots_fn=lambda *a: [_slot()],
        create_booking_fn=lambda *a: BookingReceipt(ok=False, error="slot already taken"),
    )
    out = graph.invoke(
        {
            "question": "Book cleaning 2026-09-12T09:00:00Z tomorrow morning please",
            "contact": Contact(name="Ana", email="ana@mail.com"),
        }
    )
    assert out["booking_receipt"].ok is False
    assert isinstance(out["response"], Refusal)
    assert out["response"].reason == RefusalReason.INSUFFICIENT_CONTEXT
    assert "call you back" in out["response"].message


def test_qa_path_unchanged_and_booking_tools_untouched():
    retriever = CountingRetriever()
    llm = CountingLLM(
        Answer(
            answer="SDF arrests early caries [SRC:ada-guide-001].",
            citations=["ada-guide-001"],
            confidence=0.9,
        )
    )

    def _boom(*a, **k):
        raise AssertionError("Q&A must never call cal.com")

    graph = build_graph(
        retriever=retriever,
        llm=llm,
        list_event_types_fn=_boom,
        get_slots_fn=_boom,
        create_booking_fn=_boom,
    )
    out = graph.invoke({"question": "Does silver diamine fluoride work?"})
    assert retriever.calls == 1
    assert llm.calls == 1
    assert isinstance(out["response"], Answer)
    assert out["citation_check"].verified


@pytest.mark.parametrize(
    "question",
    [
        "How often should adults schedule dental cleanings?",
        "How often should I schedule my check-up?",
        "When should I book my next cleaning?",
        "Can I reschedule my cleaning appointment for tomorrow?",
        "How soon can I book a cleaning after a filling?",
        "Can I schedule a cleaning right after a filling?",
    ],
)
def test_informational_and_reschedule_questions_stay_on_qa_path(question):
    retriever = CountingRetriever()
    llm = CountingLLM(
        Answer(
            answer="SDF arrests early caries [SRC:ada-guide-001].",
            citations=["ada-guide-001"],
            confidence=0.9,
        )
    )

    def _boom(*a, **k):
        raise AssertionError(f"must never reach cal.com: {question!r}")

    graph = build_graph(
        retriever=retriever,
        llm=llm,
        list_event_types_fn=_boom,
        get_slots_fn=_boom,
        create_booking_fn=_boom,
    )
    out = graph.invoke({"question": question})
    assert retriever.calls == 1
    assert llm.calls == 1
    assert isinstance(out["response"], Answer)
    assert out.get("booking_receipt") is None


@pytest.mark.parametrize(
    "question",
    [
        "Any appointments available next week?",
        "Do you have any slots open tomorrow?",
        "Book a cleaning tomorrow morning!",
    ],
)
def test_impersonal_and_imperative_requests_reach_booking_node(question):
    retriever = CountingRetriever()
    llm = CountingLLM(
        Answer(answer="unused [SRC:ada-guide-001].", citations=["ada-guide-001"], confidence=0.9)
    )
    tool_calls = {"slots": 0, "book": 0}

    def fake_slots(eventTypeId, start, end, timeZone):
        tool_calls["slots"] += 1
        return [_slot()]

    graph = build_graph(
        retriever=retriever,
        llm=llm,
        list_event_types_fn=lambda: [EVENT],
        get_slots_fn=fake_slots,
        create_booking_fn=lambda *a: (_ for _ in ()).throw(
            AssertionError(f"must not book without contact: {question!r}")
        ),
    )
    out = graph.invoke({"question": question})
    assert retriever.calls == 0
    assert llm.calls == 0
    assert tool_calls["slots"] == 1
    assert isinstance(out["response"], Answer)
    assert "2026-09-12" in out["response"].answer
    assert len(out["slots"]) == 1
    assert out["booking_receipt"] is None
