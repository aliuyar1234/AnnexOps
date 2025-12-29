"""Integration tests for the Prometheus metrics endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_metrics_endpoint_returns_prometheus_metrics(client: AsyncClient):
    # Touch at least one endpoint so counters/histograms have samples.
    health = await client.get("/api/health")
    assert health.status_code == 200

    response = await client.get("/api/metrics")
    assert response.status_code == 200
    body = response.text

    assert "annexops_http_requests_total" in body
    assert "annexops_http_request_duration_seconds" in body

