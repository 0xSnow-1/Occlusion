"""SPEC_V2 §8 — scoreboard math tests (pure counts, no text)."""

from src.eval.deflection import summarize_runs


def _run(outcome, latency):
    return {"outcome": outcome, "latency_s": latency}


def test_counts_by_outcome():
    s = summarize_runs([_run("handled", 1.0), _run("booked", 2.0), _run("callback", 3.0)])
    assert (s["handled"], s["booked"], s["callback"], s["total"]) == (1, 1, 1, 3)


def test_latency_p50_p95():
    runs = [_run("handled", float(i)) for i in range(1, 21)]
    s = summarize_runs(runs)
    assert s["p50_latency_s"] == 10.0
    assert s["p95_latency_s"] == 19.0


def test_empty_runs_zeroed():
    s = summarize_runs([])
    assert s["total"] == 0
    assert s["p50_latency_s"] == 0.0
    assert s["cost_per_day_usd"] == 5.0
