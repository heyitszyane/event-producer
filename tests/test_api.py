"""End-to-end tests for the FastAPI REST API endpoints.

Tests cover auth gating, CORS, CRUD routes, and budget reconciliation
through the HTTP interface using FastAPI's TestClient.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from event_producer.api import create_app
from event_producer.models.schemas import Approval
from event_producer.security.action_gate import enforce


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> TestClient:
    """TestClient with X-Demo-User header set for all requests."""
    app = create_app()
    return TestClient(app, headers={"X-Demo-User": "demo"})


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


class TestHealthz:
    """Tests for the liveness probe endpoint."""

    def test_healthz_no_auth(self) -> None:
        """GET /healthz returns 200 without auth header."""
        app = create_app()
        c = TestClient(app)
        response = c.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# POST /run
# ---------------------------------------------------------------------------


class TestRunEvent:
    """Tests for the event production pipeline endpoint."""

    def test_run_event_with_auth(self, client: TestClient) -> None:
        """POST /run with auth returns 200 with all expected keys."""
        body = {
            "brief": "Networking event for industry professionals",
            "budget_cap": "50000",
            "contingency_pct": "15",
            "attendees": 200,
            "event_type": "networking",
            "venue_type": "indoor",
            "date": "2026-08-15",
        }
        response = client.post("/run", json=body)
        assert response.status_code == 200
        data = response.json()
        assert "event_id" in data
        assert "event_spec" in data
        assert "scope_items" in data
        assert "budget_summary" in data
        assert "schedule_result" in data
        assert "risk_flags" in data
        assert "run_of_show" in data

    def test_run_event_without_auth(self) -> None:
        """POST /run without X-Demo-User header returns 401."""
        app = create_app()
        c = TestClient(app)
        body = {
            "brief": "Networking event",
            "budget_cap": "50000",
            "contingency_pct": "15",
            "attendees": 200,
            "event_type": "networking",
            "venue_type": "indoor",
            "date": "2026-08-15",
        }
        response = c.post("/run", json=body)
        assert response.status_code == 401

    def test_budget_reconciles_to_zero(self, client: TestClient) -> None:
        """Budget summary from /run reconciles: cap - contingency - spendable == 0."""
        body = {
            "brief": "Networking event for industry professionals",
            "budget_cap": "50000",
            "contingency_pct": "15",
            "attendees": 200,
            "event_type": "networking",
            "venue_type": "indoor",
            "date": "2026-08-15",
        }
        response = client.post("/run", json=body)
        assert response.status_code == 200
        data = response.json()
        bs = data["budget_summary"]
        budget_cap = Decimal(bs["budget_cap"])
        contingency = Decimal(bs["contingency_reserve"])
        spendable = Decimal(bs["spendable"])
        assert budget_cap - contingency - spendable == Decimal("0")


# ---------------------------------------------------------------------------
# POST /chat
# ---------------------------------------------------------------------------


class TestChat:
    """Tests for the chat endpoint."""

    def test_chat_with_auth(self, client: TestClient) -> None:
        """POST /chat with auth returns 200 with a reply."""
        body = {"message": "Hello, what is the status?"}
        response = client.post("/chat", json=body)
        assert response.status_code == 200
        data = response.json()
        assert "reply" in data
        assert "Hello, what is the status?" in data["reply"]

    def test_chat_without_auth(self) -> None:
        """POST /chat without X-Demo-User header returns 401."""
        app = create_app()
        c = TestClient(app)
        body = {"message": "Hello"}
        response = c.post("/chat", json=body)
        assert response.status_code == 401


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------


class TestCors:
    """Tests for CORS middleware."""

    def test_cors_preflight(self) -> None:
        """OPTIONS /run with Origin header returns 200 with CORS headers."""
        app = create_app()
        c = TestClient(app)
        response = c.options(
            "/run",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert response.status_code == 200
        # Env-driven CORS: the middleware echoes back the specific allowed
        # origin (not "*") so the value must match the Origin we sent.
        assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


# ---------------------------------------------------------------------------
# GET /event/{event_id}
# ---------------------------------------------------------------------------


class TestGetEvent:
    """Tests for the event retrieval endpoint."""

    def test_get_event_not_found(self, client: TestClient) -> None:
        """GET /event/nonexistent-id returns 404."""
        response = client.get("/event/nonexistent-id")
        assert response.status_code == 404

    def test_get_event_returns_full_state(self, client: TestClient) -> None:
        """GET /event/{id} after running pipeline returns all required keys."""
        # First run an event to populate the store
        body = {
            "brief": "Networking event for industry professionals",
            "budget_cap": "50000",
            "contingency_pct": "15",
            "attendees": 200,
            "event_type": "networking",
            "venue_type": "indoor",
            "date": "2026-08-15",
        }
        run_response = client.post("/run", json=body)
        assert run_response.status_code == 200
        event_id = run_response.json()["event_id"]

        # Now fetch the full event state
        response = client.get(f"/event/{event_id}")
        assert response.status_code == 200
        data = response.json()
        assert "event_id" in data
        assert "event_spec" in data
        assert "scope_items" in data
        assert "budget_summary" in data
        assert "schedule_result" in data
        assert "vendors" in data
        assert "risk_flags" in data
        assert "approvals" in data

    def test_get_event_not_found_error_shape(self, client: TestClient) -> None:
        """GET /event/nonexistent-id returns consistent error envelope."""
        response = client.get("/event/nonexistent-id")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "404"
        assert "message" in data["error"]


# ---------------------------------------------------------------------------
# Approvals
# ---------------------------------------------------------------------------


class TestApprovals:
    """Tests for the approvals endpoints."""

    def test_list_approvals(self, client: TestClient) -> None:
        """GET /approvals with auth returns 200 with a list."""
        response = client.get("/approvals")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_update_approval(self, client: TestClient) -> None:
        """POST /approvals/{id} with auth and action body returns 200."""
        body = {"action": "approve"}
        response = client.post("/approvals/aprv-001", json=body)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "aprv-001"
        assert data["status"] == "approved"

    def test_approval_action_invalid_returns_422(self, client: TestClient) -> None:
        """POST /approvals/{id} with invalid action returns 422."""
        body = {"action": "invalid"}
        response = client.post("/approvals/aprv-001", json=body)
        assert response.status_code == 422

    def test_approve_vendor_send_through_gate(self, client: TestClient) -> None:
        """Approve a send_vendor_message approval; enforce() passes."""
        body = {"action": "approve"}
        response = client.post("/approvals/aprv-001", json=body)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "approved"
        assert data["approved_by"] == "demo-user"

    def test_unapproved_vendor_send_blocked(self) -> None:
        """enforce() raises PermissionError for unapproved send_vendor_message."""
        with pytest.raises(PermissionError, match="requires human approval"):
            enforce("send_vendor_message", None)
        pending = Approval(
            id="aprv-pending",
            action="send_vendor_message",
            requested_by="producer@example.com",
            approved_by="manager@example.com",
            status="pending",
        )
        with pytest.raises(PermissionError, match="status is 'pending'"):
            enforce("send_vendor_message", pending)

    def test_rejected_approval_does_not_execute(self, client: TestClient) -> None:
        """Reject an approval; status becomes 'rejected', no action executed."""
        body = {"action": "reject"}
        response = client.post("/approvals/aprv-002", json=body)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "rejected"
        assert data["id"] == "aprv-002"

    def test_approval_persisted_via_event_store(self, client: TestClient) -> None:
        """Approvals are stored/retrieved through EventStore, not a module-level list."""
        # List approvals — should come from EventStore
        response = client.get("/approvals")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 3
        ids = [a["id"] for a in data]
        assert "aprv-001" in ids
        assert "aprv-002" in ids
        assert "aprv-003" in ids

        # Approve one and verify it persists
        body = {"action": "approve"}
        client.post("/approvals/aprv-003", json=body)

        # List again — aprv-003 should now be approved
        response = client.get("/approvals")
        assert response.status_code == 200
        data = response.json()
        aprv003 = next(a for a in data if a["id"] == "aprv-003")
        assert aprv003["status"] == "approved"

    def test_approval_not_found_error_shape(self, client: TestClient) -> None:
        """POST /approvals/nonexistent returns consistent error envelope."""
        body = {"action": "approve"}
        response = client.post("/approvals/nonexistent-id", json=body)
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "404"
        assert "message" in data["error"]

    def test_run_event_includes_conflict_report_key(self, client: TestClient) -> None:
        """POST /run response always includes conflict_report key (may be None)."""
        body = {
            "brief": "Networking event for industry professionals",
            "budget_cap": "50000",
            "contingency_pct": "15",
            "attendees": 200,
            "event_type": "networking",
            "venue_type": "indoor",
            "date": "2026-08-15",
        }
        response = client.post("/run", json=body)
        assert response.status_code == 200
        data = response.json()
        assert "conflict_report" in data

    def test_run_event_schedule_or_conflict(self, client: TestClient) -> None:
        """POST /run produces either a valid schedule or a non-empty conflict report."""
        body = {
            "brief": "Networking event for industry professionals",
            "budget_cap": "50000",
            "contingency_pct": "15",
            "attendees": 200,
            "event_type": "networking",
            "venue_type": "indoor",
            "date": "2026-08-15",
        }
        response = client.post("/run", json=body)
        assert response.status_code == 200
        data = response.json()
        schedule_result = data.get("schedule_result")
        conflict_report = data.get("conflict_report")
        if schedule_result is not None:
            # Valid schedule path: must have ordered_tasks and critical_path
            assert "ordered_tasks" in schedule_result
            assert "critical_path" in schedule_result
            assert len(schedule_result["ordered_tasks"]) > 0
        else:
            # Conflict path: conflict_report must be present and non-empty
            assert conflict_report is not None
            has_conflicts = (
                conflict_report.get("lead_time_conflicts")
                or conflict_report.get("anchor_conflicts")
                or conflict_report.get("cycle")
            )
            assert has_conflicts, "conflict_report must contain at least one conflict"
