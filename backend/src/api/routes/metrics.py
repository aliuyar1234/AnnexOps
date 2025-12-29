"""Prometheus metrics endpoint."""

from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, Header, HTTPException, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from src.core.config import get_settings

router = APIRouter()


@router.get(
    "/metrics",
    include_in_schema=False,
    summary="Prometheus metrics",
)
async def metrics_endpoint(
    authorization: str | None = Header(default=None),
    x_metrics_token: str | None = Header(default=None, alias="X-Metrics-Token"),
) -> Response:
    settings = get_settings()
    if settings.environment == "production":
        expected = os.getenv("METRICS_TOKEN")
        if not expected:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        bearer_token: str | None = None
        if authorization:
            parts = authorization.split()
            if len(parts) == 2 and parts[0].lower() == "bearer":
                bearer_token = parts[1]

        token = bearer_token or x_metrics_token
        if not token or not hmac.compare_digest(token, expected):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
