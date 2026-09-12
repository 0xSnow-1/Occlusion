"""Deterministic booking-intent parse (SPEC_V2 §2). No LLM, regex only.

Booking is only ever an action request, never an informational question:
a booking word alone ("available services") or a visit word alone
("what is a filling?") is NOT booking. A booking word counts when it
carries a concrete signal: a strong phrase ("book an appointment"), a
picked ISO time, a day hint ("book a cleaning tomorrow morning"), or a
visit type tied to first-person language ("Can I book a cleaning?").
Impersonal and imperative requests count too — "any appointments
available next week", "slots open tomorrow", and "book a cleaning
tomorrow" reach the booking node with no first-person framing.
Advice- and timing-shaped sentences stay on the Q&A path even when they
carry booking words ("How often should I schedule my check-up?", "How
soon can I book a cleaning after a filling?"). A reference to the
caller's own appointment ("Can I drink coffee the morning of my
appointment?", "Can I floss right before my appointment today?") is a
timing question, never a booking request, unless the verb is a booking
action. Reschedule is a SPEC_V2 §11 non-goal that never books a new
appointment.
"""

from __future__ import annotations

import logging
import re

from src.agent.schemas import BookingIntent

logger = logging.getLogger(__name__)

_BOOKING_WORD = re.compile(
    r"book|appointment|availab\w*|slot|schedul\w*|reservation", re.IGNORECASE
)
_DAY_HINT = re.compile(
    r"tomorrow|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday|"
    r"next week|morning|afternoon|evening",
    re.IGNORECASE,
)
_VISIT_KW = re.compile(
    r"check-?up|cleaning|hygiene|tooth pain|emergency|filling", re.IGNORECASE
)
_STRONG_PHRASE = re.compile(
    r"\bbook\b.*\b(appointment|visit|slot)\b"
    r"|\bschedule\b.*\b(appointment|visit)\b"
    r"|\bmake\b.*\b(appointment|reservation)\b",
    re.IGNORECASE,
)
_FIRST_PERSON = re.compile(r"\b(i|i'd|i'll|i've|me|my|we|us|our)\b", re.IGNORECASE)
_POSSESSED_APPT = re.compile(
    r"\bmy ([a-z'-]+ ){0,2}(appointment|check-?up|cleaning|visit)\b", re.IGNORECASE
)
_BOOK_ACTION = re.compile(r"\b(book|schedul\w*)\b", re.IGNORECASE)
_ADVICE_FRAME = re.compile(
    r"\b(how often|how long|how soon|how frequently|how should|when should|"
    r"when can|should i|why|which|is it|does it|do i need|necessary|"
    r"recommend\w*)\b"
    r"|\bafter\b",
    re.IGNORECASE,
)
_RESCHEDULE = re.compile(r"reschedul\w*|re-schedul\w*", re.IGNORECASE)
_ISO_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?")


def parse_booking_intent(question: str) -> BookingIntent:
    """Parse booking desire from free text (never raises, never calls LLM)."""
    q = question or ""
    if _RESCHEDULE.search(q):
        return BookingIntent(wants_booking=False)
    day_m = _DAY_HINT.search(q)
    visit_m = _VISIT_KW.search(q)
    iso_m = _ISO_TIME.search(q)
    strong = _STRONG_PHRASE.search(q)
    book_word = _BOOKING_WORD.search(q)
    own_appt = _POSSESSED_APPT.search(q) is not None and _BOOK_ACTION.search(q) is None
    wants = False
    if book_word and not _ADVICE_FRAME.search(q) and not own_appt:
        wants = bool(strong) or bool(iso_m) or bool(day_m) or bool(
            _FIRST_PERSON.search(q) and visit_m
        )
    intent = BookingIntent(
        wants_booking=wants,
        event_slug=visit_m.group(0).lower() if visit_m and wants else None,
        day_hint=day_m.group(0).lower() if day_m and wants else None,
    )
    logger.debug("Booking intent: wants=%s event=%s day=%s", intent.wants_booking, intent.event_slug, intent.day_hint)
    return intent


def extract_start_iso(question: str) -> str | None:
    """Find an ISO-8601 datetime in the question (the picked slot), if any."""
    m = _ISO_TIME.search(question or "")
    return m.group(0) if m else None


__all__ = ["extract_start_iso", "parse_booking_intent"]