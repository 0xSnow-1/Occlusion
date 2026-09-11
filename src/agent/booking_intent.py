"""Deterministic booking-intent parse (SPEC_V2 §2). No LLM, regex only.

Strict AND rule to protect the Q&A path: a booking word alone
("available services") or a visit word alone ("what is a filling?")
is NOT booking. Booking needs a booking word plus a day hint or a
visit keyword — or a strong phrase like "book an appointment".
"""

from __future__ import annotations

import logging
import re

from src.agent.schemas import BookingIntent

logger = logging.getLogger(__name__)

_BOOKING_WORD = re.compile(
    r"book|appointment|availab\w*|slot|schedul\w*|reschedul\w*", re.IGNORECASE
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
    r"|\breschedule\b",
    re.IGNORECASE,
)
_ISO_TIME = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?")


def parse_booking_intent(question: str) -> BookingIntent:
    """Parse booking desire from free text (never raises, never calls LLM)."""
    q = question or ""
    day_m = _DAY_HINT.search(q)
    visit_m = _VISIT_KW.search(q)
    wants = bool(_STRONG_PHRASE.search(q)) or bool(
        _BOOKING_WORD.search(q) and (day_m or visit_m)
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
