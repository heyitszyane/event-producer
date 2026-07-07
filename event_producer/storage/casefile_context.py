"""Request-scoped casefile storage context."""

from __future__ import annotations

from contextvars import ContextVar

DEFAULT_DEMO_USER = "demo-user"

_current_demo_user: ContextVar[str] = ContextVar(
    "event_producer_demo_user",
    default=DEFAULT_DEMO_USER,
)


def get_demo_user() -> str:
    """Return the current demo user / owner id for request-scoped stores."""
    return _current_demo_user.get()


def set_demo_user(user: str):
    """Set the current demo user context and return a reset token."""
    cleaned = (user or "").strip() or DEFAULT_DEMO_USER
    return _current_demo_user.set(cleaned)


def reset_demo_user(token) -> None:
    """Reset the current demo user context."""
    _current_demo_user.reset(token)

