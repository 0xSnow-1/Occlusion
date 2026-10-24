"""Offline tests for the Ragas gate's failure logic."""

from __future__ import annotations

from src.eval.ragas.run_ragas import baseline_regressions, threshold_failures


def test_threshold_failures_lists_only_failed_metrics():
    verdict = {
        "faithfulness": {"pass": True},
        "response_relevancy": {"pass": True},
        "context_precision": {"pass": False},
    }

    assert threshold_failures(verdict) == ["context_precision"]


def test_threshold_failures_is_empty_when_all_pass():
    verdict = {
        "faithfulness": {"pass": True},
        "response_relevancy": {"pass": True},
        "context_precision": {"pass": True},
    }

    assert threshold_failures(verdict) == []


def test_baseline_regressions_detects_a_drop_beyond_tolerance():
    means = {"faithfulness": 0.80, "response_relevancy": 0.90}
    baseline = {"faithfulness": 0.93, "response_relevancy": 0.91}

    assert baseline_regressions(means, baseline, tolerance=0.02) == ["faithfulness"]


def test_baseline_regressions_ignores_small_noise_and_missing_values():
    means = {"faithfulness": 0.92, "response_relevancy": None}
    baseline = {"faithfulness": 0.93, "response_relevancy": 0.90}

    assert baseline_regressions(means, baseline, tolerance=0.02) == []
