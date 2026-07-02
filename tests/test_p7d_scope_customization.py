"""P7D tests for visible scope customization and recompute feedback."""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from event_producer.api import create_app


@pytest.fixture
def client() -> TestClient:
    app = create_app()
    return TestClient(app, headers={"X-Demo-User": "demo"})


@pytest.fixture
def event_snapshot(client: TestClient) -> dict:
    response = client.post(
        "/run",
        json={"brief": "100 pax networking event in Singapore with $20000 budget."},
    )
    assert response.status_code == 200
    return response.json()


class TestScopeCustomization:
    """Test manual scope item CRUD operations through the API surface."""

    def test_add_scope_item_recalculates_budget_and_schedule(
        self, client: TestClient, event_snapshot: dict
    ) -> None:
        event_id = event_snapshot["event_id"]
        previous_headroom = Decimal(event_snapshot["budget_summary"]["headroom"])

        response = client.post(
            f"/event/{event_id}/scope-items",
            json={
                "name": "Welcome signage",
                "description": "Branded welcome banners",
                "category": "decor",
                "tier": "should",
                "estimated_cost": "500",
                "qty": "2",
                "selected": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert any(item["name"] == "Welcome signage" for item in data["scope_items"])
        assert Decimal(data["budget_summary"]["headroom"]) != previous_headroom
        assert data["recompute_notice"]["message"].startswith("Budget recalculated.")
        assert data["recompute_notice"]["schedule_status"] in {"recomputed", "warning"}

    def test_edit_scope_item_quantity_and_cost_recalculates_budget(
        self, client: TestClient, event_snapshot: dict
    ) -> None:
        event_id = event_snapshot["event_id"]
        initial_headroom = Decimal(event_snapshot["budget_summary"]["headroom"])

        response = client.patch(
            f"/event/{event_id}/scope-items/0",
            json={"qty": "100", "estimated_cost": "75"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["scope_items"][0]["qty"] == "100"
        assert data["scope_items"][0]["estimated_cost"] == "75"
        assert Decimal(data["budget_summary"]["headroom"]) != initial_headroom
        assert "Headroom changed" in data["recompute_notice"]["message"]

    def test_delete_toggle_and_retier_return_recompute_notice(
        self, client: TestClient, event_snapshot: dict
    ) -> None:
        event_id = event_snapshot["event_id"]

        toggle = client.post(f"/event/{event_id}/scope-items/0/toggle")
        assert toggle.status_code == 200
        assert "Budget recalculated." in toggle.json()["recompute_notice"]["message"]

        retier = client.post(
            f"/event/{event_id}/scope-items/0/retier",
            json={"tier": "wow"},
        )
        assert retier.status_code == 200
        assert retier.json()["scope_items"][0]["tier"] == "wow"
        assert "Budget recalculated." in retier.json()["recompute_notice"]["message"]

        delete = client.delete(f"/event/{event_id}/scope-items/0")
        assert delete.status_code == 200
        assert "Budget recalculated." in delete.json()["recompute_notice"]["message"]

    def test_deselect_all_scope_items_budgets_zero_items(
        self,
        client: TestClient,
        event_snapshot: dict,
    ) -> None:
        """Explicit selected=false for every item means zero included spend."""
        event_id = event_snapshot["event_id"]
        current = event_snapshot
        for idx, item in enumerate(event_snapshot["scope_items"]):
            if item["selected"]:
                response = client.post(f"/event/{event_id}/scope-items/{idx}/toggle")
                assert response.status_code == 200
                current = response.json()

        budget = current["budget_summary"]
        assert budget["lines"] == []
        assert Decimal(budget["included_totals"]) == Decimal("0.00")
        assert Decimal(budget["headroom"]) == Decimal(budget["spendable"])
        assert "Risk register and agent trace still reflect the last full pipeline run" in (
            current["recompute_notice"]["message"]
        )

    def test_repeated_category_scope_items_recompute_schedule(
        self,
        client: TestClient,
        event_snapshot: dict,
    ) -> None:
        """Repeated generic categories must not create duplicate schedule IDs."""
        event_id = event_snapshot["event_id"]

        first = client.post(
            f"/event/{event_id}/scope-items",
            json={
                "name": "Sponsor Lounge Host",
                "description": "Local host for sponsor lounge",
                "category": "other",
                "tier": "could",
                "estimated_cost": "400",
                "qty": "1",
                "selected": True,
            },
        )
        assert first.status_code == 200

        second = client.post(
            f"/event/{event_id}/scope-items",
            json={
                "name": "VIP Gift Prep",
                "description": "Pack VIP gift bags",
                "category": "other",
                "tier": "could",
                "estimated_cost": "250",
                "qty": "1",
                "selected": True,
            },
        )
        assert second.status_code == 200

        third = client.post(
            f"/event/{event_id}/scope-items",
            json={
                "name": "Dessert Station",
                "description": "Additional dessert catering station",
                "category": "catering",
                "tier": "should",
                "estimated_cost": "900",
                "qty": "1",
                "selected": True,
            },
        )
        assert third.status_code == 200
        data = third.json()
        assert data["schedule_result"] is not None
        task_ids = [task["id"] for task in data["schedule_result"]["ordered_tasks"]]
        assert len(task_ids) == len(set(task_ids))

    def test_proposal_apply_preserves_event_basis_and_recomputes(
        self, client: TestClient, event_snapshot: dict
    ) -> None:
        event_id = event_snapshot["event_id"]
        attendee_basis = event_snapshot["event_spec"]["attendees"]
        budget_cap = Decimal(event_snapshot["budget_summary"]["budget_cap"])
        contingency_pct = Decimal(event_snapshot["budget_summary"]["contingency_pct"])

        chat = client.post(
            f"/event/{event_id}/chat",
            json={"message": "Make this feel more premium"},
        )
        assert chat.status_code == 200
        proposals = chat.json()["proposals"]
        assert proposals

        applied = client.post(f"/event/{event_id}/proposals/{proposals[0]['id']}/apply")

        assert applied.status_code == 200
        data = applied.json()
        assert Decimal(data["budget_summary"]["budget_cap"]) == budget_cap
        assert Decimal(data["budget_summary"]["contingency_pct"]) == contingency_pct
        assert data["recompute_notice"]["message"].startswith("Budget recalculated.")

        get_event = client.get(f"/event/{event_id}")
        assert get_event.status_code == 200
        assert get_event.json()["event_spec"]["attendees"] == attendee_basis
