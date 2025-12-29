"""Prometheus metrics helpers."""

from __future__ import annotations

from prometheus_client import Counter, Histogram

HTTP_REQUESTS_TOTAL = Counter(
    "annexops_http_requests_total",
    "Total number of HTTP requests.",
    ["method", "route", "status"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "annexops_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ["method", "route", "status"],
    buckets=(
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.5,
        5.0,
        10.0,
    ),
)


def observe_http_request(
    *,
    method: str,
    route: str,
    status_code: int,
    duration_ms: float,
) -> None:
    status = str(status_code)
    HTTP_REQUESTS_TOTAL.labels(method=method, route=route, status=status).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(
        method=method, route=route, status=status
    ).observe(duration_ms / 1000.0)

