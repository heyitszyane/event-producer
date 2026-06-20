"""End-to-end tests for the FastAPI REST API endpoints.

Tests cover auth gating, CORS, CRUD routes, and budget reconciliation
through the HTTP interface using FastAPI's TestClient.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from event_producer.api import create_app


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
        assert response.headers.get("access-control-allow-origin") == "*"


# ---------------------------------------------------------------------------
# GET /event/{event_id}
# ---------------------------------------------------------------------------


class TestGetEvent:
    """Tests for the event retrieval endpoint."""

    def test_get_event_not_found(self, client: TestClient) -> None:
        """GET /event/nonexistent-id returns 404."""
        response = client.get("/event/nonexistent-id")
        assert response.status_code == 404


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
