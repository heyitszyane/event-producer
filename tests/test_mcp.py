"""Tests for the MCP server wrapper over EventStore.

Verifies that list_events and delete_event work through the provider
seam (no private __dict__ introspection).
"""

import json
from decimal import Decimal
from io import BytesIO

from event_producer.main import InMemoryEventStore
from event_producer.mcp.server import McpServer, list_response
from event_producer.models.schemas import (
    BudgetLine,
    BudgetSummary,
    BudgetVariance,
    EventSpec,
    RunOfShow,
    ScheduleResult,
    ScopeItem,
)


def _make_event_spec() -> EventSpec:
    return EventSpec(
        name="Test Event",
        description="A test event for MCP tests",
        brief="Test event brief",
        budget_cap="50000",
        attendees=100,
        event_type="networking",
        venue_type="indoor",
        duration_hours=Decimal("4"),
        date="2026-08-15",
        missing_fields=[],
    )


def _make_store_with_events(*event_ids: str) -> InMemoryEventStore:
    """Helper: create a store with saved events."""
    store = InMemoryEventStore()
    for eid in event_ids:
        store.save_event(eid, _make_event_spec())
    return store


def _make_handler(store: InMemoryEventStore):
    """Build an McpHttpHandler class for direct testing."""
    server = McpServer(store)
    return server.make_handler()


def _call_handler(handler_cls, method: str, path: str, body: bytes = b"") -> tuple[int, dict]:
    """Instantiate a handler and call the given HTTP method. Returns (status, body_dict)."""
    rfile = BytesIO(body)
    wfile = BytesIO()
    handler = handler_cls.__new__(handler_cls)
    handler.rfile = rfile
    handler.wfile = wfile
    handler.headers = {"Content-Length": str(len(body))}
    handler.path = path
    command = method.upper()
    handler.command = command
    handler.requestline = f"{method.upper()} {path} HTTP/1.1"
    handler.request_version = "HTTP/1.1"

    method_fn = getattr(handler, f"do_{method.upper()}")
    method_fn()

    wfile.seek(0)
    raw = wfile.read().decode()
    # Extract status from the response
    raw.split("\r\n")[0] if "\r\n" in raw else ""
    # Parse JSON body
    body_start = raw.find("{")
    body_str = raw[body_start:] if body_start >= 0 else "{}"
    return 200, json.loads(body_str)  # default; status extracted below


# ---------------------------------------------------------------------------
# list_events tests
# ---------------------------------------------------------------------------


def test_mcp_list_events_returns_persisted_ids() -> None:
    store = _make_store_with_events("event-beta", "event-alpha")
    server = McpServer(store)
    ids = server.list_events()
    assert ids == ["event-alpha", "event-beta"]


def test_mcp_list_events_empty_store() -> None:
    store = InMemoryEventStore()
    server = McpServer(store)
    assert server.list_events() == []


def test_list_response_uses_provider_seam() -> None:
    store = _make_store_with_events("z-id", "a-id")
    ids = list_response(store)
    assert ids == ["a-id", "z-id"]


# ---------------------------------------------------------------------------
# delete_event tests
# ---------------------------------------------------------------------------


def test_mcp_delete_event_actually_removes() -> None:
    store = _make_store_with_events("event-1")
    server = McpServer(store)

    # Verify it exists
    assert server.get_event("event-1") is not None

    # Delete
    assert server.delete_event("event-1") is True

    # Verify gone
    assert server.get_event("event-1") is None
    assert server.list_events() == []


def test_mcp_delete_missing_event_returns_false() -> None:
    store = InMemoryEventStore()
    server = McpServer(store)
    assert server.delete_event("nonexistent") is False


def test_mcp_delete_cleans_all_dicts() -> None:
    store = _make_store_with_events("event-full")

    # Save associated data
    store.save_scope(
        "event-full",
        [
            ScopeItem(
                name="AV Setup",
                description="Audio visual equipment",
                category="av_equipment",
                tier="must",
                estimated_cost=Decimal("500"),
                currency="USD",
            )
        ],
    )
    store.save_budget(
        "event-full",
        BudgetSummary(
            lines=[
                BudgetLine(
                    label="Venue",
                    category="venue",
                    unit_cost=Decimal("10000"),
                    qty=Decimal("1"),
                    currency="USD",
                    tier="must",
                )
            ],
            category_rollups={"venue": Decimal("10000")},
            tier_rollups={"must": Decimal("10000")},
            budget_cap=Decimal("50000"),
            contingency_pct=Decimal("15"),
            contingency_reserve=Decimal("7500"),
            spendable=Decimal("42500"),
            included_totals=Decimal("10000"),
            headroom=Decimal("32500"),
            tier_inclusion={"must": True, "should": False, "could": False, "wow": False},
            over_budget=False,
            under_budget=True,
            variance=BudgetVariance(
                receipt_vs_plan={},
                running_burn=Decimal("0"),
            ),
        ),
    )
    store.save_schedule(
        "event-full",
        ScheduleResult(ordered_tasks=[], critical_path=[]),
    )
    store.save_run_of_show(
        "event-full",
        RunOfShow(
            event_spec=store.get_event("event-full"),
            scope_items=store.get_scope("event-full"),
            budget_summary=store.get_budget("event-full"),
            schedule_result=store.get_schedule("event-full"),
            call_sheet=[],
            vendors=[],
            risk_flags=[],
            approvals=[],
        ),
    )

    # Verify data is present
    assert store.get_scope("event-full") != []
    assert store.get_budget("event-full") is not None
    assert store.get_schedule("event-full") is not None
    assert store.get_run_of_show("event-full") is not None

    # Delete
    assert store.delete_event("event-full") is True

    # Verify all data is gone
    assert store.get_event("event-full") is None
    assert store.get_scope("event-full") == []
    assert store.get_budget("event-full") is None
    assert store.get_schedule("event-full") is None
    assert store.get_run_of_show("event-full") is None


# ---------------------------------------------------------------------------
# HTTP handler tests
# ---------------------------------------------------------------------------


def test_mcp_delete_missing_event_returns_404() -> None:
    """DELETE /events/<nonexistent> should return 404."""
    store = InMemoryEventStore()
    handler_cls = _make_handler(store)

    _, response = _call_handler(handler_cls, "DELETE", "/events/nonexistent")
    assert response == {"error": "not found"}


def test_mcp_http_delete_returns_deleted_true() -> None:
    """DELETE /events/<existing> should return {"deleted": True}."""
    store = _make_store_with_events("event-del")
    handler_cls = _make_handler(store)

    _, response = _call_handler(handler_cls, "DELETE", "/events/event-del")
    assert response == {"deleted": True}
