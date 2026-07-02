"""Non-secret provider diagnostic helpers."""

from __future__ import annotations

import time

from pydantic import ValidationError

PREVIEW_LIMIT = 500


def preview(value: str | None, limit: int = PREVIEW_LIMIT) -> str | None:
    if value is None:
        return None
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def latency_ms(started: float) -> int:
    return max(0, int((time.perf_counter() - started) * 1000))


def pydantic_error_summary(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        parts: list[str] = []
        for err in exc.errors()[:4]:
            loc = ".".join(str(x) for x in err.get("loc", ()))
            msg = str(err.get("msg", "validation error"))
            parts.append(f"{loc or '<root>'}: {msg}")
        suffix = "" if len(exc.errors()) <= 4 else f"; +{len(exc.errors()) - 4} more"
        return "; ".join(parts) + suffix
    return preview(str(exc)) or exc.__class__.__name__
