"""Request/task context utilities.

Used for propagating a correlation/request ID into logs across API requests and
Celery worker tasks.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from uuid import uuid4

_request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str | None:
    """Get the current request/task correlation ID (if any)."""

    return _request_id_var.get()


def set_request_id(request_id: str | None) -> Token[str | None]:
    """Set the current request/task correlation ID and return the reset token."""

    return _request_id_var.set(request_id)


def reset_request_id(token: Token[str | None]) -> None:
    """Reset the correlation ID to the previous value using the token."""

    _request_id_var.reset(token)


def new_request_id() -> str:
    """Generate a new correlation ID."""

    return str(uuid4())


@contextmanager
def request_id_context(request_id: str | None):
    """Context manager that sets the correlation ID for the duration."""

    token = set_request_id(request_id)
    try:
        yield
    finally:
        reset_request_id(token)

