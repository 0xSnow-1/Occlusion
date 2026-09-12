"""Cal.com API v2 wrappers for V2 booking (SPEC_V2 §3).

Pure server-side HTTP, no LLM, no prompts, no UI code. Stdlib only
(`urllib`) so no new dependency is needed.

Safety rules (all test-pinned):
- Auth header `Authorization: Bearer <CAL_API_KEY>` + per-endpoint
  `cal-api-version` header (event-types 2024-06-14, slots 2024-09-04,
  bookings 2024-08-13; a single shared version 404s two endpoints).
  Key read from env at call time, never logged, never committed.
- `User-Agent` must be a browser string: api.cal.com sits behind
  Cloudflare bot checks and blocks stock `Python-urllib/3.x` with 403/1010.
- 10 s timeout per call; any HTTP / network / auth / parse error returns
  `[]` (slots / event types) or `BookingReceipt(ok=False, error=...)`.
- Never raise into the graph; never log the key or full headers.
- Times are ISO-8601 UTC on the wire; timezone conversion happens at the
  UI boundary. The tool layer stores UTC only.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from src.agent.schemas import BookingReceipt, EventType, Slot

logger = logging.getLogger(__name__)

CAL_API_BASE = "https://api.cal.com/v2"
# cal.com pins a DIFFERENT cal-api-version per endpoint family (wrong value
# 404s). SPEC_V2 §3 named one version; live probes 2026-09-12 showed the
# real mapping below, which wins over the spec text.
CAL_API_VERSIONS = {
    "event-types": "2024-06-14",
    "slots": "2024-09-04",
    "bookings": "2024-08-13",
}
CAL_API_VERSION = CAL_API_VERSIONS["bookings"]
TIMEOUT_S = 10


def _api_key() -> str | None:
    return os.environ.get("CAL_API_KEY") or None


def _auth_headers(api: str = "bookings") -> dict[str, str]:
    key = _api_key()
    return {
        "Authorization": f"Bearer {key}" if key else "",
        "cal-api-version": CAL_API_VERSIONS.get(api, CAL_API_VERSION),
        "Content-Type": "application/json",
        # api.cal.com sits behind Cloudflare bot checks: stock urllib's
        # "Python-urllib/3.x" agent gets a 403 (error 1010). A browser
        # agent string passes. No behavior change beyond access.
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }


def _parse_dt(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        text = value.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def _do_request(
    method: str, url: str, headers: dict[str, str], payload: dict | None = None
) -> tuple[int, object]:
    """Low-level HTTP call; returns (status, parsed JSON or {}). Raises on error."""
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            status = getattr(resp, "status", 200)
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        try:
            raw = e.read().decode("utf-8", errors="replace")
        except Exception:
            raw = ""
        raise _HttpStatusError(e.code, raw) from e
    if not raw:
        return status, {}
    try:
        return status, json.loads(raw)
    except json.JSONDecodeError:
        return status, {}


class _HttpStatusError(Exception):
    def __init__(self, status: int, body: str = "") -> None:
        super().__init__(f"HTTP {status}")
        self.status = status
        self.body = body


def _unwrap_data(body: object) -> object:
    if isinstance(body, dict) and "data" in body:
        return body["data"]
    return body


def _parse_event_type(item: dict) -> EventType | None:
    try:
        duration = (
            item.get("duration_min")
            if item.get("duration_min") is not None
            else item.get("lengthInMinutes", item.get("length", item.get("duration")))
        )
        title = item.get("title", item.get("name"))
        return EventType(
            id=int(item["id"]),
            slug=str(item.get("slug", "")),
            title=str(title),
            duration_min=int(duration),
        )
    except (KeyError, TypeError, ValueError):
        return None


def list_event_types() -> list[EventType]:
    """GET /v2/event-types -> list[EventType]; empty list on any failure."""
    if not _api_key():
        logger.error("list_event_types: missing CAL_API_KEY")
        return []
    url = f"{CAL_API_BASE}/event-types"
    try:
        _, body = _do_request("GET", url, _auth_headers("event-types"))
        items = _unwrap_data(body)
        if not isinstance(items, list):
            logger.error("list_event_types: unexpected response shape")
            return []
        out: list[EventType] = []
        for item in items:
            if isinstance(item, dict):
                parsed = _parse_event_type(item)
                if parsed is not None:
                    out.append(parsed)
        logger.info("list_event_types: found %d event types", len(out))
        return out
    except _HttpStatusError as e:
        logger.error("list_event_types: HTTP %s", e.status)
        return []
    except Exception as e:
        logger.error("list_event_types: failed %s", type(e).__name__)
        return []


def _extract_slot_times(data: object) -> list[str]:
    """Handle cal.com slot shapes (all seen live 2026-09-12):
    {"data": {"2026-09-14": [{"start": ...}]}} (bare date-map),
    {"slots": {...}} wrapper, or a flat list. Entries use
    "time", "start", or "startTime" keys, or bare strings.
    """
    times: list[str] = []
    slots_obj = data
    if isinstance(data, dict) and "slots" in data:
        slots_obj = data["slots"]

    def _take(entry: object) -> None:
        if isinstance(entry, dict):
            for key in ("time", "start", "startTime"):
                if entry.get(key):
                    times.append(entry[key])
                    break
        elif isinstance(entry, str):
            times.append(entry)

    if isinstance(slots_obj, dict):
        for _day, entries in slots_obj.items():
            if isinstance(entries, list):
                for entry in entries:
                    _take(entry)
    elif isinstance(slots_obj, list):
        for entry in slots_obj:
            _take(entry)
    return times


def get_slots(
    eventTypeId: int, start: str, end: str, timeZone: str
) -> list[Slot]:
    """GET /v2/slots -> list[Slot]; empty list on any failure."""
    if not _api_key():
        logger.error("get_slots: missing CAL_API_KEY")
        return []
    query = urllib.parse.urlencode(
        {"eventTypeId": eventTypeId, "start": start, "end": end, "timeZone": timeZone}
    )
    url = f"{CAL_API_BASE}/slots?{query}"
    try:
        _, body = _do_request("GET", url, _auth_headers("slots"))
        data = _unwrap_data(body)
        out: list[Slot] = []
        for t in _extract_slot_times(data):
            dt = _parse_dt(t)
            if dt is not None:
                out.append(Slot(start_utc=dt, eventTypeId=int(eventTypeId)))
        logger.info("get_slots: found %d slots", len(out))
        return out
    except _HttpStatusError as e:
        logger.error("get_slots: HTTP %s", e.status)
        return []
    except Exception as e:
        logger.error("get_slots: failed %s", type(e).__name__)
        return []


def create_booking(
    eventTypeId: int,
    start_utc_iso: str,
    name: str,
    email: str,
    notes: str = "",
) -> BookingReceipt:
    """POST /v2/bookings -> BookingReceipt; ok=False on any failure."""
    if not _api_key():
        logger.error("create_booking: missing CAL_API_KEY")
        return BookingReceipt(ok=False, error="calendar unavailable: missing API key")
    if not name.strip() or not email.strip():
        return BookingReceipt(ok=False, error="name and email are required")
    url = f"{CAL_API_BASE}/bookings"
    # NOTE (live probe 2026-09-12): top-level "notes" is rejected with 400
    # ("property notes should not exist"). The parameter stays for caller
    # compat but is not sent; extra text belongs in bookingFieldsResponses.
    # Same probe: attendee.timeZone is REQUIRED (400 without it).
    tz = os.environ.get("CAL_TIMEZONE", "UTC") or "UTC"
    payload = {
        "eventTypeId": eventTypeId,
        "start": start_utc_iso,
        "attendee": {"name": name, "email": email, "timeZone": tz},
    }
    try:
        _, body = _do_request("POST", url, _auth_headers("bookings"), payload)
        data = _unwrap_data(body)
        if not isinstance(data, dict):
            return BookingReceipt(ok=False, error="calendar unavailable: bad response")
        uid = data.get("uid", data.get("id", data.get("bookingUid")))
        title = data.get("title", data.get("eventTitle"))
        start_raw = data.get("startTime", data.get("start", data.get("startUtc")))
        start_utc = _parse_dt(str(start_raw)) if start_raw else _parse_dt(start_utc_iso)
        if uid is None:
            logger.error("create_booking: response missing booking id")
            return BookingReceipt(ok=False, error="calendar unavailable: bad response")
        logger.info("create_booking: booked uid=%s", uid)
        return BookingReceipt(
            ok=True,
            uid=str(uid),
            title=str(title) if title else None,
            start_utc=start_utc,
        )
    except _HttpStatusError as e:
        logger.error("create_booking: HTTP %s", e.status)
        return BookingReceipt(ok=False, error=f"calendar unavailable: HTTP {e.status}")
    except Exception as e:
        logger.error("create_booking: failed %s", type(e).__name__)
        return BookingReceipt(ok=False, error="calendar unavailable")


__all__ = ["create_booking", "get_slots", "list_event_types"]
