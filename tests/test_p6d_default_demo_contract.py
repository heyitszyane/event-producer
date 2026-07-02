"""Tests for the P6D default demo contract.

Verifies that the locked default /run input produces a complete, non-empty,
agentically explainable event-production state.

Default input:
  brief: "1 day AI networking event"
  budget_cap: "10000"
  contingency_pct: "10"
  attendees: 50
  event_type: "corporate"
  venue_type: "indoor"
  date: "2026-06-30"
"""

from __future__ import annotations

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


@pytest.fixture
def default_run_response(client: TestClient) -> dict:
    """Run the default P6D input and return the JSON response."""
    body = {
        "brief": "1 day AI networking event",
        "budget_cap": "10000",
        "contingency_pct": "10",
        "attendees": 50,
        "event_type": "corporate",
        "venue_type": "indoor",
        "date": "2026-06-30",
    }
    response = client.post("/run", json=body)
    assert response.status_code == 200
    return response.json()


# ---------------------------------------------------------------------------
# P6D Contract Tests
# ---------------------------------------------------------------------------


class TestP6dDefaultDemoContract:
    """Tests for the P6D default demo contract."""

    def test_default_run_returns_200(self, default_run_response: dict) -> None:
        """Locked default /run returns 200."""
        assert default_run_response is not None

    # -- Scope Items --

    def test_scope_items_non_empty(self, default_run_response: dict) -> None:
        """scope_items is non-empty."""
        items = default_run_response.get("scope_items", [])
        assert len(items) > 0

    def test_scope_items_at_least_5(self, default_run_response: dict) -> None:
        """scope_items has at least 5 items."""
        items = default_run_response.get("scope_items", [])
        assert len(items) >= 5

    def test_scope_items_at_least_3_must(self, default_run_response: dict) -> None:
        """At least 3 must-tier items."""
        items = default_run_response.get("scope_items", [])
        must_items = [i for i in items if i.get("tier") == "must"]
        assert len(must_items) >= 3

    def test_scope_items_at_least_1_should(self, default_run_response: dict) -> None:
        """At least 1 should-tier item."""
        items = default_run_response.get("scope_items", [])
        should_items = [i for i in items if i.get("tier") == "should"]
        assert len(should_items) >= 1

    def test_scope_items_at_least_1_could_or_wow(self, default_run_response: dict) -> None:
        """At least 1 could or wow tier item."""
        items = default_run_response.get("scope_items", [])
        could_wow = [i for i in items if i.get("tier") in ("could", "wow")]
        assert len(could_wow) >= 1

    # -- Budget Summary --

    def test_budget_lines_non_empty(self, default_run_response: dict) -> None:
        """budget_summary.lines is non-empty."""
        bs = default_run_response.get("budget_summary", {})
        lines = bs.get("lines", [])
        assert len(lines) > 0

    def test_budget_category_rollups_non_empty(self, default_run_response: dict) -> None:
        """budget_summary.category_rollups is non-empty."""
        bs = default_run_response.get("budget_summary", {})
        rollups = bs.get("category_rollups", {})
        assert len(rollups) > 0

    def test_budget_tier_rollups_non_empty(self, default_run_response: dict) -> None:
        """budget_summary.tier_rollups is non-empty."""
        bs = default_run_response.get("budget_summary", {})
        rollups = bs.get("tier_rollups", {})
        assert len(rollups) > 0

    def test_budget_contingency_coherent(self, default_run_response: dict) -> None:
        """contingency_reserve is coherent with 10%."""
        from decimal import Decimal
        bs = default_run_response.get("budget_summary", {})
        cap = Decimal(bs.get("budget_cap", "0"))
        contingency = Decimal(bs.get("contingency_reserve", "0"))
        expected = (cap * Decimal("10") / Decimal("100")).quantize(Decimal("0.01"))
        assert contingency == expected

    # -- Schedule --

    def test_ordered_tasks_at_least_6(self, default_run_response: dict) -> None:
        """schedule_result.ordered_tasks has at least 6 tasks."""
        sr = default_run_response.get("schedule_result")
        assert sr is not None
        tasks = sr.get("ordered_tasks", [])
        assert len(tasks) >= 6

    def test_critical_path_non_empty(self, default_run_response: dict) -> None:
        """schedule_result.critical_path is non-empty."""
        sr = default_run_response.get("schedule_result")
        assert sr is not None
        cp = sr.get("critical_path", [])
        assert len(cp) > 0

    # -- Agent Trace --

    def test_agent_trace_exists(self, default_run_response: dict) -> None:
        """agent_trace exists in response."""
        trace = default_run_response.get("agent_trace", [])
        assert len(trace) > 0

    def test_agent_trace_has_8_roles(self, default_run_response: dict) -> None:
        """P7H.3: agent_trace has 8 role steps after adding Scope Strategy."""
        trace = default_run_response.get("agent_trace", [])
        assert len(trace) == 8

    def test_agent_trace_required_roles(self, default_run_response: dict) -> None:
        """P7H.3: agent_trace contains all required role names."""
        trace = default_run_response.get("agent_trace", [])
        roles = {step["role"] for step in trace}
        assert "Brief Intake Agent" in roles
        assert "Creative Concept Agent" in roles
        assert "Scope Strategy Agent" in roles
        assert "Brief/Scope Agent" in roles
        assert "Budget Manager" in roles
        assert "Production Manager" in roles
        assert "Vendor Draft Agent" in roles
        assert "Risk/Gap Flagger" in roles

    def test_agent_trace_budget_engine_label(self, default_run_response: dict) -> None:
        """Budget Manager trace step names Budget Engine as deterministic core."""
        trace = default_run_response.get("agent_trace", [])
        budget_step = next(s for s in trace if s["role"] == "Budget Manager")
        assert budget_step["deterministic_core"] == "Budget Engine"

    def test_agent_trace_cpm_scheduler_label(self, default_run_response: dict) -> None:
        """Production Manager trace step names CPM Scheduler as deterministic core."""
        trace = default_run_response.get("agent_trace", [])
        prod_step = next(s for s in trace if s["role"] == "Production Manager")
        assert prod_step["deterministic_core"] == "CPM Scheduler"

    def test_agent_trace_vendor_approval_required(self, default_run_response: dict) -> None:
        """Vendor Draft trace step has approval_required=True and pending_approval status."""
        trace = default_run_response.get("agent_trace", [])
        vendor_step = next(s for s in trace if s["role"] == "Vendor Draft Agent")
        assert vendor_step["approval_required"] is True
        assert vendor_step["status"] == "pending_approval"

    # -- Approvals --

    def test_approvals_exist(self, default_run_response: dict) -> None:
        """approvals exists in response."""
        approvals = default_run_response.get("approvals", [])
        assert len(approvals) > 0

    def test_approval_pending_send_vendor_message(self, default_run_response: dict) -> None:
        """At least one approval is pending with action send_vendor_message."""
        approvals = default_run_response.get("approvals", [])
        pending_sends = [
            a for a in approvals
            if a.get("action") == "send_vendor_message" and a.get("status") == "pending"
        ]
        assert len(pending_sends) >= 1

    def test_no_vendor_action_auto_executed(self, default_run_response: dict) -> None:
        """No approval is auto-executed; all are pending."""
        approvals = default_run_response.get("approvals", [])
        for a in approvals:
            assert a.get("status") == "pending"

    # -- Chat Log --

    def test_chat_log_exists(self, default_run_response: dict) -> None:
        """chat_log exists in response."""
        chat = default_run_response.get("chat_log", [])
        assert len(chat) > 0

    def test_chat_log_at_least_5_messages(self, default_run_response: dict) -> None:
        """chat_log has at least 5 messages."""
        chat = default_run_response.get("chat_log", [])
        assert len(chat) >= 5

    # -- Risk Flags --

    def test_risk_flags_at_least_2(self, default_run_response: dict) -> None:
        """risk_flags has at least 2 meaningful risks/gaps."""
        flags = default_run_response.get("risk_flags", [])
        assert len(flags) >= 2

    # -- Security Beat --

    def test_security_beat_no_longer_deferred(self, default_run_response: dict) -> None:
        """security_beat is no longer deferred — P6F replaced it with scripted demo."""
        sb = default_run_response.get("security_beat", {})
        assert sb.get("status") != "deferred_to_p6f"
        assert sb.get("status") == "scripted_demo_ready"

    # -- Existing event types still work --

    def test_networking_still_works(self, client: TestClient) -> None:
        """Existing networking event type still produces non-empty scope."""
        body = {
            "brief": "Networking event",
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
        assert len(data["scope_items"]) > 0

    def test_brief_only_payload_succeeds(self, client: TestClient) -> None:
        """P7A: a brief-only payload succeeds (constraint fields are optional, with safe fallback)."""
        # The constraint fields are now optional — a prompt is the primary product
        # input. The backend resolves missing fields with safe fallbacks + model
        # extraction and surfaces the gaps in brief_intake.missing_questions.
        body = {
            "brief": (
                "Need a 50-pax AI founder networking night in Singapore in two months. "
                "Budget around 20k. Premium but not flashy, light F&B, no full conference."
            ),
        }
        response = client.post("/run", json=body)
        assert response.status_code == 200
        data = response.json()
        assert data["brief_intake"]["event_type"] == "networking"
        # model_mode is recorded (fallback in test env) + security wall preserved
        assert "creative_concept" in data
        assert "model_mode_summary" in data
        assert data["security_beat"]["external_action_executed"] is False

    def test_invalid_payload_returns_error(self, client: TestClient) -> None:
        """P7A: an empty/missing brief is still rejected with a clear 422.

        ``brief`` remains the one required field; a payload that omits it is a
        genuine schema violation and is not silently filled.
        """
        body: dict = {}
        response = client.post("/run", json=body)
        # Empty/missing brief -> FastAPI/Pydantic 422.
        assert response.status_code == 422
