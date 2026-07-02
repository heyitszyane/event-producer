"""Documented fallback defaults used by the deterministic demo pipeline."""

from __future__ import annotations

from typing import Final, TypedDict


class EventConstraintDefaults(TypedDict):
    attendees: int
    budget_cap: str
    contingency_pct: str
    venue_type: str
    fallback_date_offset_days: int


DEFAULT_EVENT_CONSTRAINTS: Final[EventConstraintDefaults] = {
    "attendees": 50,
    "budget_cap": "20000",
    "contingency_pct": "15",
    "venue_type": "indoor",
    "fallback_date_offset_days": 45,
}
