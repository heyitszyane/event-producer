"""P7R — Scope counts every selected item; Auto-fit uses the engine to trim.

The Scope page no longer silently drops whole discretionary tiers. Every
selected item counts toward the budget (headroom can go negative), and
Include/Exclude is the only gate. The Budget Engine's greedy tier-gating is
preserved as an explicit, user-triggered "Auto-fit to budget" action.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from event_producer.api import create_app


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app, headers={"X-Demo-User": "demo"})


def _event_id(client: TestClient) -> tuple[str, Decimal]:
    run = client.post("/run", json={"brief": "Networking event"}).json()
    return run["event_id"], Decimal(run["budget_summary"]["budget_cap"])


def test_selected_discretionary_item_counts(client: TestClient) -> None:
    """A 'could'-tier item well over the cap still counts (no silent gating)."""
    event_id, cap = _event_id(client)
    add = {
        "name": "Overrun Item",
        "description": "Deliberately unaffordable",
        "category": "other",
        "tier": "could",
        "estimated_cost": str(cap * 5),
        "qty": "1",
    }
    res = client.post(f"/event/{event_id}/scope-items", json=add).json()

    item = next(s for s in res["scope_items"] if s["name"] == "Overrun Item")
    assert item["selected"] is True
    # The whole 'could' tier is counted rather than gated out.
    assert res["budget_summary"]["tier_inclusion"]["could"] is True
    assert res["budget_summary"]["over_budget"] is True

    # Excluding it (Include/Exclude is the only gate) improves headroom.
    idx = res["scope_items"].index(item)
    toggled = client.post(f"/event/{event_id}/scope-items/{idx}/toggle").json()
    assert Decimal(toggled["budget_summary"]["headroom"]) > Decimal(
        res["budget_summary"]["headroom"]
    )


def test_auto_fit_drops_unaffordable_tier(client: TestClient) -> None:
    """Auto-fit deselects a whole tier that cannot fit the spendable pool."""
    event_id, cap = _event_id(client)
    add = {
        "name": "Mega Stage",
        "description": "Unaffordable stretch item",
        "category": "av",
        "tier": "wow",
        "estimated_cost": str(cap * 10),
        "qty": "1",
    }
    over = client.post(f"/event/{event_id}/scope-items", json=add).json()
    assert over["budget_summary"]["over_budget"] is True
    assert Decimal(over["budget_summary"]["headroom"]) < Decimal("0")

    fitted = client.post(f"/event/{event_id}/scope-items/auto-fit").json()
    mega = next(s for s in fitted["scope_items"] if s["name"] == "Mega Stage")
    # The wow tier cannot fit, so Auto-fit excludes it (never deletes it).
    assert mega["selected"] is False
    assert Decimal(fitted["budget_summary"]["headroom"]) > Decimal(
        over["budget_summary"]["headroom"]
    )
