# SPEC_V2 — Occlusion V2: AI Receptionist (Q&A + Real cal.com Booking)

> Status: spec, not yet implemented. V1 (`spec.md` + code on `main`) is untouched by this file.
> V2 adds a parallel booking path on a real cal.com calendar. Q&A retrieval, guardrail,
> verification, and Gates 0–3 stay exactly as pinned by `tests/agent/*`.
> Related: `SCOPE.md` (problem + refusal taxonomy), `TODO.md` (build order),
> `SHARED_CONTEXT.md` (current pointer), cal.com API v2 docs (slots + bookings).

## 1. What changes (one paragraph)

V1 answers routine dental questions with citations or refuses safely. V2 keeps that path
byte-for-byte and adds a second path: when the user wants an appointment, the graph routes
to a new `booking` node that reads real availability from the owner's cal.com account and
creates a real booking. No insurance terminology, no fake slots, no guessed times. A failed
booking degrades to the existing callback offer, never to an invented confirmation.

## 2. Architecture delta

```text
guardrail (existing, deterministic pre-LLM)
 |-- booking intent  -> booking node -> tools.py -> cal.com API v2 -> receipt -> END
 |-- Q&A intent      -> retrieve -> generate -> verify -> decide -> END (unchanged)
 |-- flagged         -> decide (Gate 0 refusal) -> callback capture -> END (unchanged)
```

Intent detection for V2 is deterministic regex, not an LLM classifier:

- Booking signals: `book|appointment|available|slot|schedule|reschedule` plus day hints
  (`tomorrow|monday|next week|morning|afternoon`) or visit keywords
  (`checkup|check-up|cleaning|hygiene|tooth pain|emergency|filling`).
- Everything else follows the V1 Q&A path. An LLM intent classifier is deferred to V2.1.

`_route_after_guardrail` in `src/agent/graph.py` is extended to return
`{"retrieve", "booking", "decide"}`. The `booking` node never calls the LLM and never
touches retrieval; the Q&A nodes never call cal.com.

## 3. `src/agent/tools.py` (new module)

Pure server-side wrappers around cal.com API v2. No LLM, no prompt, no UI code.

| Function | Cal.com endpoint | Input | Output |
|---|---|---|---|
| `list_event_types()` | `GET /v2/event-types` | none (auth header only) | `list[EventType]` |
| `get_slots(eventTypeId, start, end, timeZone)` | `GET /v2/slots?eventTypeId=&start=&end=&timeZone=` | int + ISO-8601 UTC bounds + IANA tz | `list[Slot]` |
| `create_booking(eventTypeId, start_utc_iso, name, email, notes="")` | `POST /v2/bookings` | int + ISO-8601 UTC + attendee | `BookingReceipt` |

Rules (all test-pinned):

- Auth: `Authorization: Bearer <CAL_API_KEY>` + `cal-api-version: 2024-08-13` headers,
  key read from env at call time, never logged, never committed.
- Timeout 10 s per call; HTTP/network/auth errors return `BookingReceipt(ok=False, error=...)`
  or empty slot list — never raise into the graph.
- Rate limit 120 req/min (cal.com API-key tier) is respected; no retry storm — one attempt,
  failure surfaces to the user as "calendar unavailable, leave details for callback."
- Times are ISO-8601 UTC on the wire; timezone conversion happens once at the UI boundary
  using `CAL_TIMEZONE`. The tool layer stores UTC only.
- A slot the API did not return must never be confirmed. No fallback invention.

## 4. Schemas (`src/agent/schemas.py` additions)

```python
class EventType(BaseModel):
    id: int
    slug: str
    title: str
    duration_min: int

class Slot(BaseModel):
    start_utc: datetime
    eventTypeId: int

class BookingIntent(BaseModel):
    wants_booking: bool = False
    event_slug: str | None = None
    day_hint: str | None = None

class BookingReceipt(BaseModel):
    ok: bool = False
    uid: str | None = None
    title: str | None = None
    start_utc: datetime | None = None
    error: str | None = None

class Contact(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
```

Validation at construction, same convention as existing schemas. `BookingReceipt(ok=False)`
is the only failure channel — no exceptions cross into graph state.

## 5. State (`src/agent/state.py` additions)

```python
booking_intent: BookingIntent | None   # written by intent parse (inside guardrail routing)
slots: list[Slot]                      # written by booking node (get_slots result)
booking_receipt: BookingReceipt | None # written by booking node (create_booking result)
contact: Contact | None                # written by UI before booking confirm
```

One producer per field, default overwrite semantics, deliberately no reducers — same rule
as the existing `AgentState` docstring. A future chat-history field is the only thing that
ever gets `Annotated[list, operator.add]`.

## 6. Graph (`src/agent/graph.py` changes)

- New `booking` node: resolve `event_slug -> eventTypeId` (via `list_event_types` cache),
  default window next 7 days in `CAL_TIMEZONE`, call `get_slots`; if the user already picked
  a time and `contact` has name+email, call `create_booking` and write `booking_receipt`.
- Double-book / past-time / API-down all yield `BookingReceipt(ok=False, error=...)`; the
  node response asks for another time or offers callback capture. It never emits a fake UID.
- Existing nodes (`guardrail`, `retrieve`, `generate`, `verify`, `decide`) and Gates 0–3 are
  unchanged. `tests/agent/test_graph.py`, `test_guardrail.py`, `test_verify.py` must stay
  green without modification.

## 7. UI (`src/ui/app.py` changes)

- Booking intent renders real slot buttons from `state.slots` (UTC converted to clinic tz
  for display only), collects name + email in-chat, then confirms via the booking node.
- Success shows receipt time + UID + "confirmation email sent by cal.com."
- Failure shows the API error in plain words + callback form (name + phone + reason).
- No `?embed=1` mode in V2 (deferred to V2.1).

## 8. Callback list + scoreboard (V2 scope)

- Callback capture: `contact (name/phone) + question_hash + reason + timestamp` appended to
  `data/callbacks.jsonl` (gitignored; no raw PHI in logs). Staff view = sidebar table + CSV
  download. This is the escalation path for every refusal and every failed booking.
- Scoreboard: per-session and totals of `handled (answer) / booked (receipt ok) /
  callback (refusal or booking fail)`, plus P50/P95 latency and $/query at 500/day.
  Computed in `src/eval/deflection.py` from structured run logs (counts only, no text).

## 9. Tests / eval (must pass before ship)

- `tests/agent/test_tools.py` (mocked HTTP): slot parse, booking parse, API-down ->
  `ok=False`, auth header present, key never appears in logs.
- `tests/agent/test_booking_graph.py`: booking intent skips LLM/retrieval; Q&A path
  byte-identical; double-book falls back to callback offer.
- Live check (needs owner cal.com + `CAL_API_KEY`): slots fetch, book-then-cancel on a test
  event, past-time rejected. Times recorded, test booking cancelled immediately.
- Regression: Harbor trilogy stays 204/204, Ragas baseline re-run recorded (no threshold
  change without human approval). Trap-refusal 100% still blocks ship.

## 10. Config / hygiene (V2 pre-req)

- `.env` adds `CAL_API_KEY` (`cal_live_...`), `CAL_USERNAME`, `CAL_TIMEZONE`. `sample.env`
  documents all three with empty values. `.env` stays gitignored, never committed.
- `pyproject.toml`: remove `copilotkit`, `ag-ui-langgraph`, `ddgs`, `duckduckgo-search`
  (forbidden by `AGENTS.md` without approval) or record explicit owner approval.

## 11. Non-goals (not V2)

Insurance verification, voice in/out, reschedule/cancel via chat, team events, routing
forms, multi-turn memory, multilingual, MCP exposure, reranker/embedding swap. Each needs
its own spec before it is built.
