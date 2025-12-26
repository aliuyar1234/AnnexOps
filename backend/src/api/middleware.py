"""Middleware for rate limiting and request logging."""
from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple
from collections import defaultdict
import time
import logging
import json
from fastapi import Request, Response, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from src.core.config import get_settings
from src.core.security import decode_token

# Configure structured logging
logger = logging.getLogger(__name__)
settings = get_settings()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware for auth endpoints.

    Rate limits:
    - Login endpoint: 10 attempts per minute per IP
    - Invitation endpoint: 5 per hour per user
    - Password reset: 3 per hour per email (not yet implemented)
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        # Storage: {(endpoint, identifier): [(timestamp, count)]}
        self._requests: Dict[Tuple[str, str], list] = defaultdict(list)

    def _clean_old_requests(self, endpoint: str, identifier: str, window: timedelta) -> None:
        """Remove requests outside the time window."""
        cutoff = datetime.now(timezone.utc) - window
        key = (endpoint, identifier)
        self._requests[key] = [
            (ts, count) for ts, count in self._requests[key]
            if ts > cutoff
        ]

    def _get_request_count(self, endpoint: str, identifier: str, window: timedelta) -> int:
        """Get number of requests in the time window."""
        self._clean_old_requests(endpoint, identifier, window)
        key = (endpoint, identifier)
        return sum(count for _, count in self._requests[key])

    def _add_request(self, endpoint: str, identifier: str) -> None:
        """Record a new request."""
        key = (endpoint, identifier)
        now = datetime.now(timezone.utc)
        self._requests[key].append((now, 1))

    async def dispatch(self, request: Request, call_next):
        """Apply rate limiting based on endpoint."""
        if settings.environment != "production":
            return await call_next(request)

        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"

        # Login endpoint: 10 per minute per IP
        if path == "/api/auth/login":
            count = self._get_request_count("login", client_ip, timedelta(minutes=1))
            if count >= 10:
                raise HTTPException(
                    status_code=429,
                    detail="Too many login attempts. Please try again later."
                )
            self._add_request("login", client_ip)

        # Invitation endpoint: 5 per hour per user
        # Note: Prefer user_id from JWT (fallback to IP)
        elif path == "/api/auth/invite":
            identifier = client_ip
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                payload = decode_token(auth_header.removeprefix("Bearer ").strip())
                if payload and payload.get("sub"):
                    identifier = str(payload["sub"])

            count = self._get_request_count("invite", identifier, timedelta(hours=1))
            if count >= 5:
                raise HTTPException(
                    status_code=429,
                    detail="Too many invitation requests. Please try again later."
                )
            self._add_request("invite", identifier)

        response = await call_next(request)
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Request logging middleware with structured logging.

    Logs:
    - Method, path, status code, duration
    - IP address for security
    - Structured JSON format
    """

    async def dispatch(self, request: Request, call_next):
        """Log request details."""
        start_time = time.time()
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Log as structured JSON
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "method": method,
            "path": path,
            "status_code": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "client_ip": client_ip,
        }

        # Log at appropriate level
        if response.status_code >= 500:
            logger.error(json.dumps(log_data))
        elif response.status_code >= 400:
            logger.warning(json.dumps(log_data))
        else:
            logger.info(json.dumps(log_data))

        return response
