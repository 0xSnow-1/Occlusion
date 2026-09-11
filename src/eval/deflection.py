"""Scoreboard math (SPEC_V2 §8): counts only, no text.

Run records are tiny dicts: {"outcome": "handled"|"booked"|"callback",
"latency_s": float}. Cost assumes ~$0.01/query (latency & cost baseline
2026-09-10 in SHARED_CONTEXT.md) at 500 queries/day.
"""

from __future__ import annotations

import logging
import math

logger = logging.getLogger(__name__)

COST_PER_QUERY_USD = 0.01
QUERIES_PER_DAY = 500


def _percentile(sorted_vals: list[float], pct: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    rank = math.ceil(pct / 100 * len(sorted_vals)) - 1
    return sorted_vals[max(0, min(rank, len(sorted_vals) - 1))]


def summarize_runs(runs: list[dict]) -> dict:
    """Summarize run records into handled/booked/callback + latency + cost."""
    handled = sum(1 for r in runs if r.get("outcome") == "handled")
    booked = sum(1 for r in runs if r.get("outcome") == "booked")
    callback = sum(1 for r in runs if r.get("outcome") == "callback")
    lat = sorted(float(r.get("latency_s", 0.0)) for r in runs)
    summary = {
        "total": len(runs),
        "handled": handled,
        "booked": booked,
        "callback": callback,
        "p50_latency_s": round(_percentile(lat, 50), 2),
        "p95_latency_s": round(_percentile(lat, 95), 2),
        "cost_per_day_usd": round(QUERIES_PER_DAY * COST_PER_QUERY_USD, 2),
    }
    logger.info(
        "Scoreboard: total=%d handled=%d booked=%d callback=%d",
        summary["total"], handled, booked, callback,
    )
    return summary


__all__ = ["COST_PER_QUERY_USD", "QUERIES_PER_DAY", "summarize_runs"]
