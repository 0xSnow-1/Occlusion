"""In-process Prometheus metrics for the Occlusion HTTP service."""

from __future__ import annotations

import threading
from collections import Counter

_DURATION_BUCKETS = (0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0)


def _escape_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')


class Metrics:
    """Thread-safe counters and histograms rendered in Prometheus text format."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._requests: Counter[tuple[str, str]] = Counter()
        self._duration_buckets: Counter[tuple[str, float]] = Counter()
        self._duration_sum: Counter[str] = Counter()
        self._duration_count: Counter[str] = Counter()
        self._answers = 0
        self._refusals: Counter[str] = Counter()
        self._ready = 0
        self._points = 0

    def observe_http(self, endpoint: str, status: int, duration_s: float) -> None:
        with self._lock:
            self._requests[(endpoint, str(status))] += 1
            self._duration_sum[endpoint] += duration_s
            self._duration_count[endpoint] += 1
            for bucket in _DURATION_BUCKETS:
                if duration_s <= bucket:
                    self._duration_buckets[(endpoint, bucket)] += 1

    def observe_outcome(self, kind: str, reason: str | None = None) -> None:
        with self._lock:
            if kind == "answer":
                self._answers += 1
            elif kind == "refusal" and reason is not None:
                self._refusals[reason] += 1

    def set_ready(self, ready: bool, points: int) -> None:
        with self._lock:
            self._ready = 1 if ready else 0
            self._points = max(points, 0)

    def render(self) -> str:
        with self._lock:
            return self._render_locked()

    def _render_locked(self) -> str:
        lines = [
            "# HELP occlusion_http_requests_total HTTP requests by endpoint and status.",
            "# TYPE occlusion_http_requests_total counter",
        ]
        for (endpoint, status), count in sorted(self._requests.items()):
            lines.append(
                "occlusion_http_requests_total"
                f'{{endpoint="{_escape_label(endpoint)}",'
                f'status="{_escape_label(status)}"}} {count}'
            )

        lines.extend(
            [
                "# HELP occlusion_http_request_duration_seconds HTTP request duration.",
                "# TYPE occlusion_http_request_duration_seconds histogram",
            ]
        )
        for endpoint in sorted(self._duration_count):
            for bucket in _DURATION_BUCKETS:
                count = self._duration_buckets.get((endpoint, bucket), 0)
                lines.append(
                    "occlusion_http_request_duration_seconds_bucket"
                    f'{{endpoint="{_escape_label(endpoint)}",'
                    f'le="{bucket:g}"}} {count}'
                )
            lines.append(
                "occlusion_http_request_duration_seconds_bucket"
                f'{{endpoint="{_escape_label(endpoint)}",le="+Inf"}} '
                f"{self._duration_count[endpoint]}"
            )
            lines.append(
                "occlusion_http_request_duration_seconds_sum"
                f'{{endpoint="{_escape_label(endpoint)}"}} '
                f"{self._duration_sum[endpoint]:.6f}"
            )
            lines.append(
                "occlusion_http_request_duration_seconds_count"
                f'{{endpoint="{_escape_label(endpoint)}"}} '
                f"{self._duration_count[endpoint]}"
            )

        lines.extend(
            [
                "# HELP occlusion_answers_total Accepted answers.",
                "# TYPE occlusion_answers_total counter",
                f"occlusion_answers_total {self._answers}",
                "# HELP occlusion_refusals_total Refusals by reason.",
                "# TYPE occlusion_refusals_total counter",
            ]
        )
        for reason, count in sorted(self._refusals.items()):
            lines.append(
                "occlusion_refusals_total"
                f'{{reason="{_escape_label(reason)}"}} {count}'
            )

        lines.extend(
            [
                "# HELP occlusion_pipeline_ready Whether the retrieval index is ready.",
                "# TYPE occlusion_pipeline_ready gauge",
                f"occlusion_pipeline_ready {self._ready}",
                "# HELP occlusion_index_points Number of points in the retrieval index.",
                "# TYPE occlusion_index_points gauge",
                f"occlusion_index_points {self._points}",
            ]
        )
        return "\n".join(lines) + "\n"


__all__ = ["Metrics"]
