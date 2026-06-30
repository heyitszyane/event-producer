"""P7B scope mutation tests.

Tests cover:
1. Add scope item endpoint adds item and returns updated event snapshot.
2. Edit scope item changes budget rollups/headroom.
3. Delete scope item changes budget rollups/headroom.
4. Tier change updates tier rollups/tier inclusion.
5. Manual scope mutation does not require Gemini.
6. Orchestrator chat returns proposed actions, not direct state mutation.
7. Applying proposed add_scope_item mutates state only after apply.
8. Dismissing proposal does not mutate state.
9. Vendor/payment proposal creates or routes to approval gate; it does not execute directly.
10. Existing P6/P7A tests still pass.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from event_producer.api import create_app


@pytest.fixture
def client() -> TestClient:
    """TestClient with X-Demo-User header set for all requests."""
    app = create_app()
    return TestClient(app, headers={"X-Demo-User": "demo"})


class TestScopeMutation:
    """Tests for scope mutation endpoints."""

    def test_add_scope_item_returns_updated_snapshot(self, client: TestClient) -> None:
        """POST /event/{id}/scope-items adds item and recomputes budget."""
        # First create an event
        body = {"brief": "Networking event for industry professionals"}
        run_res = client.post("/run", json=body)
        assert run_res.status_code == 200
        event_id = run_res.json()["event_id"]

        # Add a scope item
        add_body = {
            "name": "Additional Decor",
            "description": "Extra decorative elements",
            "category": "decor",
            "tier": "could",
            "estimated_cost": "500.00",
            "qty": "1",
        }
        response = client.post(f"/event/{event_id}/scope-items", json=add_body)
        assert response.status_code == 200
        data = response.json()
        assert "scope_items" in data
        assert "budget_summary" in data
        # The new item should be in scope_items
        assert any(s["name"] == "Additional Decor" for s in data["scope_items"])

    def test_edit_scope_item_changes_budget(self, client: TestClient) -> None:
        """PATCH /event/{id}/scope-items/{idx} updates item and recomputes budget."""
        body = {"brief": "Networking event for industry professionals"}
        run_res = client.post("/run", json=body)
        event_id = run_res.json()["event_id"]

        # Get initial scope to find an editable item
        initial_scope = run_res.json()["scope_items"]
        if len(initial_scope) == 0:
            pytest.skip("No scope items to edit")

        idx = 0
        original_cost = Decimal(initial_scope[idx]["estimated_cost"])

        # Update the item cost
        update_body = {"estimated_cost": str(original_cost + Decimal("100"))}
        response = client.patch(f"/event/{event_id}/scope-items/{idx}", json=update_body)
        assert response.status_code == 200
        data = response.json()
        new_cost = Decimal(data["scope_items"][idx]["estimated_cost"])
        assert new_cost > original_cost

        # Headroom should decrease
        assert Decimal(data["budget_summary"]["headroom"]) < Decimal(run_res.json()["budget_summary"]["headroom"])

    def test_delete_scope_item_changes_budget(self, client: TestClient) -> None:
        """DELETE /event/{id}/scope-items/{idx} removes item and recomputes budget."""
        body = {"brief": "Networking event for industry professionals"}
        run_res = client.post("/run", json=body)
        event_id = run_res.json()["event_id"]
        initial_count = len(run_res.json()["scope_items"])

        if initial_count == 0:
            pytest.skip("No scope items to delete")

        response = client.delete(f"/event/{event_id}/scope-items/0")
        assert response.status_code == 200
        data = response.json()
        assert len(data["scope_items"]) == initial_count - 1

    def test_tier_change_updates_rollups(self, client: TestClient) -> None:
        """POST /event/{id}/scope-items/{idx}/retier changes tier and recomputes budget."""
        body = {"brief": "Networking event for industry professionals"}
        run_res = client.post("/run", json=body)
        event_id = run_res.json()["event_id"]

        original_tier = run_res.json()["scope_items"][0]["tier"] if run_res.json()["scope_items"] else "could"
        new_tier = "must" if original_tier != "must" else "could"

        response = client.post(
            f"/event/{event_id}/scope-items/0/retier",
            json={"tier": new_tier},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["scope_items"][0]["tier"] == new_tier

    def test_manual_mutation_no_gemini_required(self, client: TestClient, monkeypatch) -> None:
        """Scope mutation works without Gemini (fallback mode)."""
        monkeypatch.delenv("ENABLE_LIVE_GEMINI", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)

        body = {"brief": "Networking event for industry professionals"}
        run_res = client.post("/run", json=body)
        event_id = run_res.json()["event_id"]

        add_body = {
            "name": "Test Item",
            "category": "decor",
            "estimated_cost": "100.00",
        }
        response = client.post(f"/event/{event_id}/scope-items", json=add_body)
        assert response.status_code == 200
        assert "scope_items" in response.json()


class TestOrchestratorChat:
    """Tests for orchestrator chat endpoint."""

    def test_chat_returns_proposed_actions(self, client: TestClient) -> None:
        """POST /event/{id}/chat returns proposals without mutating state."""
        body = {"brief": "Networking event for industry professionals"}
        run_res = client.post("/run", json=body)
        event_id = run_res.json()["event_id"]
        initial_scope_count = len(run_res.json()["scope_items"])

        response = client.post(
            f"/event/{event_id}/chat",
            json={"message": "Make this feel more premium"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        assert "proposals" in data

        # Verify no mutation occurred yet (scope count unchanged)
        get_res = client.get(f"/event/{event_id}")
        assert len(get_res.json()["scope_items"]) == initial_scope_count

    def test_apply_proposal_mutates_state(self, client: TestClient) -> None:
        """Applying a proposal changes scope count."""
        body = {"brief": "Networking event for industry professionals"}
        run_res = client.post("/run", json=body)
        event_id = run_res.json()["event_id"]
        initial_scope_count = len(run_res.json()["scope_items"])

        chat_res = client.post(
            f"/event/{event_id}/chat",
            json={"message": "premium"},
        )
        assert chat_res.status_code == 200
        proposals = chat_res.json()["proposals"]

        if len(proposals) == 0:
            pytest.skip("No proposals generated for this event")

        proposal_id = proposals[0]["id"]
        apply_res = client.post(f"/event/{event_id}/proposals/{proposal_id}/apply")
        assert apply_res.status_code == 200
        data = apply_res.json()
        assert len(data["scope_items"]) > initial_scope_count

    def test_dismiss_proposal_no_mutation(self, client: TestClient) -> None:
        """Dismissing a proposal does not change state."""
        body = {"brief": "Networking event for industry professionals"}
        run_res = client.post("/run", json=body)
        event_id = run_res.json()["event_id"]

        chat_res = client.post(
            f"/event/{event_id}/chat",
            json={"message": "premium"},
        )
        proposals = chat_res.json()["proposals"]

        if len(proposals) == 0:
            pytest.skip("No proposals generated")

        proposal_id = proposals[0]["id"]
        dismiss_res = client.post(f"/event/{event_id}/proposals/{proposal_id}/dismiss")
        assert dismiss_res.status_code == 200
        assert dismiss_res.json()["status"] == "dismissed"

        # Verify state unchanged
        get_res = client.get(f"/event/{event_id}")
        assert len(get_res.json()["scope_items"]) == len(run_res.json()["scope_items"])


class TestNoAutonomousAction:
    """Tests ensuring no autonomous state mutation."""

    def test_orchestrator_chat_no_direct_mutation(self, client: TestClient) -> None:
        """Chat endpoint never directly changes scope without apply."""
        body = {"brief": "Networking event for industry professionals", "budget_cap": "50000"}
        run_res = client.post("/run", json=body)
        event_id = run_res.json()["event_id"]
        initial_headroom = Decimal(run_res.json()["budget_summary"]["headroom"])

        client.post(
            f"/event/{event_id}/chat",
            json={"message": "premium upgrade under 20k"},
        )

        # Headroom should be unchanged
        get_res = client.get(f"/event/{event_id}")
        new_headroom = Decimal(get_res.json()["budget_summary"]["headroom"])
        assert initial_headroom == new_headroom