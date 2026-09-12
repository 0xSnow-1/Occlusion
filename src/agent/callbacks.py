"""Callback capture (SPEC_V2 §8): escalation for refusals + failed bookings.

One JSON object per line in `data/callbacks.jsonl` (gitignored):
contact name/phone + question_hash (never raw text) + reason + UTC timestamp.
Staff read it back for the sidebar table + CSV download. No raw PHI in logs.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_PATH = "data/callbacks.jsonl"


def _hash_question(question: str) -> str:
    return hashlib.sha256((question or "").encode("utf-8")).hexdigest()[:16]


def append_callback(
    name: str,
    phone: str,
    question: str,
    reason: str,
    path: str | Path = DEFAULT_PATH,
) -> dict:
    """Append one callback record; returns the record. Logs reason only, never PHI."""
    if not (name or "").strip() or not (phone or "").strip():
        raise ValueError("name and phone are required")
    record = {
        "name": name.strip(),
        "phone": phone.strip(),
        "question_hash": _hash_question(question),
        "reason": reason or "",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    dest = Path(path)
    if dest.parent != Path(".") and str(dest.parent):
        dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    logger.info("Callback captured: reason=%s", record["reason"])
    return record


def read_callbacks(path: str | Path = DEFAULT_PATH) -> list[dict]:
    """Read all callback records; missing file returns []."""
    dest = Path(path)
    if not dest.exists():
        return []
    out: list[dict] = []
    with dest.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


__all__ = ["DEFAULT_PATH", "append_callback", "read_callbacks"]
