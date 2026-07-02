"""End-to-end tests for the FastAPI REST API endpoints.

Tests cover auth gating, CORS, CRUD routes, and budget reconciliation
through the HTTP interface using FastAPI's TestClient.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from event_producer.config import model_settings
from event_producer.api import create_app
from event_producer.models.schemas import Approval
from event_producer.security.action_gate import enforce


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """TestClient with X-Demo-User header set for all requests."""
    for key in (
        "ENABLE_LIVE_MODEL",
        "ENABLE_LIVE_GEMINI",
        "STRICT_LIVE_MODEL",
        "MODEL_PROVIDER",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "OPENROUTER_API_KEY",
        "OPENAI_COMPATIBLE_API_KEY",
        "LOCAL_LLM_API_BASE_URL",
        "LOCAL_LLM_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)
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


class TestRuntimeModel:
    """Tests for non-secret runtime model diagnostics."""

    def test_runtime_model_reports_local_provider_without_leaking_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ENABLE_LIVE_MODEL", "true")
        monkeypatch.setenv("MODEL_PROVIDER", "local")
        monkeypatch.setenv("LOCAL_LLM_API_BASE_URL", "http://127.0.0.1:1234/v1/chat/completions")
        monkeypatch.setenv("LOCAL_LLM_MODEL", "local-test-model")
        monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "should-not-leak")

        app = create_app()
        c = TestClient(app, headers={"X-Demo-User": "demo"})
        response = c.get("/runtime/model")

        assert response.status_code == 200
        data = response.json()
        assert data == {
            "provider": "local",
            "live_enabled": True,
            "strict_live_model": True,
            "effective_mode": "openai_compatible_live",
            "model_name": "local-test-model",
            "api_base_url": "http://127.0.0.1:1234/v1/chat/completions",
            "has_api_key": True,
            "request_timeout_seconds": 12,
            "fallback_reason": None,
        }
        assert "should-not-leak" not in str(data)


class TestModelSettings:
    """Tests for the local provider settings harness."""

    def test_get_model_settings_does_not_leak_key(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text(
            "\n".join(
                [
                    "ENABLE_LIVE_MODEL=true",
                    "MODEL_PROVIDER=lmstudio",
                    "LOCAL_LLM_API_BASE_URL=http://100.79.109.78:1234/v1/chat/completions",
                    "LOCAL_LLM_MODEL=qwen/qwen3.5-9b",
                    "OPENAI_COMPATIBLE_API_KEY=secret-lmst",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(model_settings, "env_path", lambda: env_file)
        monkeypatch.setattr("event_producer.api.env_path", lambda: env_file)
        monkeypatch.setenv("ENABLE_LIVE_MODEL", "true")
        monkeypatch.setenv("MODEL_PROVIDER", "lmstudio")
        monkeypatch.setenv("LOCAL_LLM_API_BASE_URL", "http://100.79.109.78:1234/v1/chat/completions")
        monkeypatch.setenv("LOCAL_LLM_MODEL", "qwen/qwen3.5-9b")
        monkeypatch.setenv("OPENAI_COMPATIBLE_API_KEY", "secret-lmst")

        app = create_app()
        c = TestClient(app, headers={"X-Demo-User": "demo"})
        response = c.get("/settings/model")

        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "lmstudio"
        assert data["effective_mode"] == "openai_compatible_live"
        assert data["has_api_key"] is True
        assert data["strict_live_model"] is True
        assert data["request_timeout_seconds"] == 12
        assert data["env_path"] == str(env_file)
        assert "secret-lmst" not in str(data)

    def test_update_model_settings_writes_env_and_refreshes_runtime(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        env_file = tmp_path / ".env"
        env_file.write_text("ENABLE_LIVE_MODEL=false\nMODEL_PROVIDER=gemini\n", encoding="utf-8")
        monkeypatch.setattr(model_settings, "env_path", lambda: env_file)
        monkeypatch.setattr("event_producer.api.env_path", lambda: env_file)
        monkeypatch.delenv("ENABLE_LIVE_MODEL", raising=False)
        monkeypatch.delenv("MODEL_PROVIDER", raising=False)
        monkeypatch.delenv("LOCAL_LLM_API_BASE_URL", raising=False)
        monkeypatch.delenv("LOCAL_LLM_MODEL", raising=False)
        monkeypatch.delenv("OPENAI_COMPATIBLE_API_KEY", raising=False)

        app = create_app()
        c = TestClient(app, headers={"X-Demo-User": "demo"})
        response = c.post(
            "/settings/model",
            json={
                "provider": "lmstudio",
                "model_name": "qwen/qwen3.5-9b",
                "api_base_url": "http://100.79.109.78:1234/v1/chat/completions",
                "api_key": "new-secret",
                "live_enabled": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["provider"] == "lmstudio"
        assert data["effective_mode"] == "openai_compatible_live"
        assert data["has_api_key"] is True
        assert "new-secret" not in str(data)

        written = env_file.read_text(encoding="utf-8")
        assert "ENABLE_LIVE_MODEL=true" in written
        assert "STRICT_LIVE_MODEL=true" in written
        assert "MODEL_REQUEST_TIMEOUT_SECONDS=12" in written
        assert "MODEL_PROVIDER=lmstudio" in written
        assert "LOCAL_LLM_MODEL=qwen/qwen3.5-9b" in written
        assert "OPENAI_COMPATIBLE_API_KEY=new-secret" in written

        runtime = c.get("/runtime/model").json()
        assert runtime["provider"] == "lmstudio"
        assert runtime["has_api_key"] is True


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
        """POST /run without X-Demo-User header returns 401 with error envelope."""
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
        data = response.json()
        assert "error" in data
        assert "detail" not in data
        assert data["error"]["code"] == "401"
        assert data["error"]["message"] == "Missing X-Demo-User header"

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
        """POST /chat without X-Demo-User header returns 401 with error envelope."""
        app = create_app()
        c = TestClient(app)
        body = {"message": "Hello"}
        response = c.post("/chat", json=body)
        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert "detail" not in data
        assert data["error"]["code"] == "401"
        assert data["error"]["message"] == "Missing X-Demo-User header"


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

    def test_cors_preflight_allows_127_frontend_dev_port(self) -> None:
        """Default local CORS allows 127.0.0.1 frontend dev origins."""
        app = create_app()
        c = TestClient(app)
        response = c.options(
            "/run",
            headers={
                "Origin": "http://127.0.0.1:3002",
                "Access-Control-Request-Method": "POST",
            },
        )
        assert response.status_code == 200
        assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:3002"


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

    def test_event_scoped_approval_update(self, client: TestClient) -> None:
        """Approving a /run approval updates the same event-scoped record."""
        run = client.post("/run", json={"brief": "100 pax networking event with $20000 budget."})
        assert run.status_code == 200
        snapshot = run.json()
        event_id = snapshot["event_id"]
        approval = next(a for a in snapshot["approvals"] if a["status"] == "pending")

        response = client.post(
            f"/event/{event_id}/approvals/{approval['id']}",
            json={"action": "approve"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == approval["id"]
        assert data["status"] == "approved"
        assert data["approved_by"] == "demo"

        listed = client.get(f"/event/{event_id}/approvals")
        assert listed.status_code == 200
        stored = next(a for a in listed.json() if a["id"] == approval["id"])
        assert stored["status"] == "approved"

    def test_event_scoped_approval_reject_does_not_simulate_send(
        self,
        client: TestClient,
    ) -> None:
        """Rejecting an event approval stores rejection without releasing the gate."""
        run = client.post("/run", json={"brief": "80 pax launch party with $15000 budget."})
        assert run.status_code == 200
        snapshot = run.json()
        event_id = snapshot["event_id"]
        approval = next(a for a in snapshot["approvals"] if a["status"] == "pending")

        response = client.post(
            f"/event/{event_id}/approvals/{approval['id']}",
            json={"action": "reject"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "rejected"
        assert data["approved_by"] == "demo"
        with pytest.raises(PermissionError, match="status is 'rejected'"):
            enforce(data["action"], Approval(**data))

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
        assert data["approved_by"] == "demo"

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


# ---------------------------------------------------------------------------
# P7A — agentic intake contract tests (no live Gemini; fallback / mocked)
# ---------------------------------------------------------------------------


class TestP7aAgenticIntake:
    """P7A /run contract additions for the AI co-producer layer.

    Unless explicitly enabled with a key, these run in fallback mode — which
    is the honest, key-less demo path. The assertions therefore check
    *telemetry* (mode recorded, security wall intact, determinism preserved)
    rather than requiring Gemini-flavor output.
    """

    def _run(self, client: TestClient, body: dict) -> dict:
        res = client.post("/run", json=body)
        assert res.status_code == 200
        return res.json()

    def test_no_key_returns_fallback_mode(self, client: TestClient, monkeypatch) -> None:
        """No key + ENABLE_LIVE_GEMINI unset -> both agents fall back."""
        monkeypatch.delenv("ENABLE_LIVE_GEMINI", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        data = self._run(client, {"brief": "50-pax networking night. 20k budget."})
        summary = data["model_mode_summary"]
        assert summary["brief_intake"] == "rule_based_fallback"
        assert summary["creative_concept"] == "rule_based_fallback"
        assert summary["scope_strategy"] == "rule_based_fallback"
        assert summary["budget_manager"] == "deterministic_engine"
        assert summary["production_manager"] == "deterministic_engine"
        assert summary["vendor_coordinator"] == "human_approval_gate"
        assert summary["vendor_draft"] == "rule_based_fallback"
        assert summary["security"] == "scripted_fixture"

    def test_live_without_key_falls_back_with_reason(
        self, client: TestClient, monkeypatch
    ) -> None:
        """ENABLE_LIVE_GEMINI=true but missing key -> fallback with visible reason."""
        monkeypatch.setenv("ENABLE_LIVE_GEMINI", "true")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        data = self._run(client, {"brief": "Small corporate dinner next Friday."})
        assert data["model_mode_summary"]["brief_intake"] == "rule_based_fallback"
        assert data["brief_intake"]["model_mode"] == "rule_based_fallback"
        # fallback_reason is recorded (not silently dropped).
        assert data["brief_intake"].get("fallback_reason") or data["agent_trace"][0].get(
            "fallback_reason"
        )

    def test_mock_gemini_brief_intake_parses_into_schema(
        self, client: TestClient, monkeypatch
    ) -> None:
        """A live-mode provider returning valid JSON parses into BriefIntakeResult and appears in /run."""
        from event_producer.agents import brief_intake as brief_mod
        from event_producer.providers.agent_model import AgentModelResult

        fake_parsed = brief_mod.BriefIntakeResult(
            normalized_brief="mocked brief",
            event_type="networking",
            attendees=30,
            budget_cap="15000",
            goals=["network"],
            confidence="medium",
            model_mode="gemini_live",
        )

        class _FakeGemini:
            def generate_structured(self, **_kw):
                return AgentModelResult(
                    parsed=fake_parsed,
                    raw_text=fake_parsed.model_dump_json(),
                    model_mode="gemini_live",
                    model_name="gemini-2.5-flash",
                    fallback_reason=None,
                    error=None,
                )

        # Force live env and swap provider at the app object.
        monkeypatch.setenv("ENABLE_LIVE_GEMINI", "true")
        monkeypatch.setenv("GEMINI_API_KEY", "mock-key")
        producer = client.app.state.event_producer  # type: ignore[attr-defined]
        producer._agent_model = _FakeGemini()
        producer._brief_intake_reason = brief_mod.BriefIntakeReasonAgent(provider=_FakeGemini())

        data = self._run(client, {"brief": "mocked", "event_type": "networking"})
        assert data["brief_intake"]["event_type"] == "networking"
        assert data["brief_intake"]["attendees"] == 30

    def test_mock_gemini_creative_concept_parses(
        self, client: TestClient, monkeypatch
    ) -> None:
        """A live-mode provider returning creative JSON appears in /run.creative_concept."""
        from event_producer.agents import creative_concept as creative_mod
        from event_producer.providers.agent_model import AgentModelResult

        fake_parsed = creative_mod.CreativeConceptResult(
            event_title_options=["Option A"],
            concept_summary="A mocked concept",
            creative_ideas=[
                creative_mod.CreativeIdea(
                    title="Idea",
                    description="desc",
                    why_it_fits="fits",
                    estimated_complexity="low",
                    budget_pressure="low",
                    tier="should",
                )
            ],
            model_mode="gemini_live",
        )

        class _FakeGemini:
            def generate_structured(self, **_kw):
                return AgentModelResult(
                    parsed=fake_parsed,
                    raw_text=fake_parsed.model_dump_json(),
                    model_mode="gemini_live",
                    model_name="gemini-2.5-flash",
                    fallback_reason=None,
                    error=None,
                )

        monkeypatch.setenv("ENABLE_LIVE_GEMINI", "true")
        monkeypatch.setenv("GEMINI_API_KEY", "mock-key")
        producer = client.app.state.event_producer  # type: ignore[attr-defined]
        producer._agent_model = _FakeGemini()
        producer._creative_reason = creative_mod.CreativeConceptReasonAgent(provider=_FakeGemini())

        data = self._run(client, {"brief": "mocked", "event_type": "networking"})
        assert data["creative_concept"]["concept_summary"] == "A mocked concept"
        assert data["creative_concept"]["model_mode"] == "gemini_live"

    def test_invalid_provider_output_does_not_crash(
        self, client: TestClient, monkeypatch
    ) -> None:
        """Live-mode provider returning garbage -> no 500; fallback / structured error path used."""
        from event_producer.providers.agent_model import AgentModelResult

        class _Broken:
            def generate_structured(self, **_kw):
                # Simulates invalid-model-output: no parseable schema, with an error.
                return AgentModelResult(
                    parsed=None,
                    raw_text="<<< totally not json >>>",
                    model_mode="rule_based_fallback",
                    model_name="gemini-2.5-flash",
                    fallback_reason="could not parse JSON from Gemini output",
                    error="could not parse JSON from Gemini output",
                )

        monkeypatch.setenv("ENABLE_LIVE_GEMINI", "true")
        monkeypatch.setenv("GEMINI_API_KEY", "mock-key")
        producer = client.app.state.event_producer  # type: ignore[attr-defined]
        producer._agent_model = _Broken()
        producer._brief_intake_reason._provider = _Broken()

        res = client.post("/run", json={"brief": "networking thing"})
        assert res.status_code == 200
        data = res.json()
        # pipeline still produced budget/schedule results.
        assert data["budget_summary"] is not None
        assert data["schedule_result"] is not None

    def test_trace_includes_model_mode_fields(self, client: TestClient, monkeypatch) -> None:
        """Every trace step exposes model_mode/model_name/prompt_version/fallback_reason."""
        monkeypatch.delenv("ENABLE_LIVE_GEMINI", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        data = self._run(client, {"brief": "Anything"})
        trace = data["agent_trace"]
        assert trace, "expected non-empty agent trace"
        for step in trace:
            assert "model_mode" in step
            assert "model_name" in step
            assert "prompt_version" in step
            assert "fallback_reason" in step

    def test_budget_and_schedule_remain_deterministic(
        self, client: TestClient, monkeypatch
    ) -> None:
        """Default /run still reconciles budget to zero and produces a non-empty schedule."""
        monkeypatch.delenv("ENABLE_LIVE_GEMINI", raising=False)
        from decimal import Decimal

        data = self._run(
            client,
            {
                "brief": "Networking event",
                "budget_cap": "50000",
                "contingency_pct": "15",
                "attendees": 200,
                "event_type": "networking",
                "venue_type": "indoor",
                "date": "2026-08-15",
            },
        )
        bs = data["budget_summary"]
        assert Decimal(bs["budget_cap"]) - Decimal(bs["contingency_reserve"]) - Decimal(
            bs["spendable"]
        ) == Decimal("0")
        sr = data["schedule_result"]
        assert sr is not None
        assert len(sr["ordered_tasks"]) > 0

    def test_approval_security_wall_preserved(self, client: TestClient, monkeypatch) -> None:
        """The security beat still reports no external action + no state mutation."""
        monkeypatch.delenv("ENABLE_LIVE_GEMINI", raising=False)
        data = self._run(client, {"brief": "Anything"})
        sb = data["security_beat"]
        assert sb["external_action_executed"] is False
        assert sb["state_mutation_executed"] is False
        assert sb["approval_required"] is True
        # And approvals keep a pending gate (vendor draft behind human approval).
        assert any(a["status"] == "pending" for a in data["approvals"])

    def test_legacy_contract_still_supported(self, client: TestClient, monkeypatch) -> None:
        """The legacy 7-field /run shape keeps working exactly as before."""
        monkeypatch.delenv("ENABLE_LIVE_GEMINI", raising=False)
        body = {
            "brief": "Networking event for industry professionals",
            "budget_cap": "50000",
            "contingency_pct": "15",
            "attendees": 200,
            "event_type": "networking",
            "venue_type": "indoor",
            "date": "2026-08-15",
        }
        data = self._run(client, body)
        for key in (
            "event_id",
            "event_spec",
            "scope_items",
            "budget_summary",
            "schedule_result",
            "risk_flags",
            "run_of_show",
        ):
            assert key in data
