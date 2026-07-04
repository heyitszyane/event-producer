"""Tests for P7H.1 provider diagnostics and strict live mode."""

from __future__ import annotations

from fastapi.testclient import TestClient
from pydantic import BaseModel

from event_producer.api import create_app
from event_producer.providers.agent_model import AgentModelResult, LiveModelProviderError


def _clear_model_env(monkeypatch) -> None:
    for key in (
        "ENABLE_LIVE_MODEL",
        "ENABLE_LIVE_GEMINI",
        "STRICT_LIVE_MODEL",
        "MODEL_PROVIDER",
        "OPENROUTER_API_KEY",
        "OPENROUTER_MODEL",
        "MODEL_REQUEST_TIMEOUT_SECONDS",
    ):
        monkeypatch.delenv(key, raising=False)


class _FakeSuccessProvider:
    def generate_structured(self, **kwargs):
        schema: type[BaseModel] = kwargs["schema"]
        parsed = schema(ok=True, message="provider reachable")
        return AgentModelResult(
            parsed=parsed,
            raw_text='{"ok": true, "message": "provider reachable"}',
            model_mode="openai_compatible_live",
            model_name="google/gemini-2.5-flash",
            provider="openrouter",
            effective_mode="openai_compatible_live",
            agent_name=kwargs["agent_name"],
            prompt_version=kwargs["prompt_version"],
            ok=True,
            latency_ms=42,
            http_status=200,
            response_shape_keys=["message", "ok"],
            response_preview='{"ok": true, "message": "provider reachable"}',
        )


class _FakeDegradedProvider:
    def generate_structured(self, **kwargs):
        return AgentModelResult(
            parsed=None,
            raw_text=None,
            model_mode="openai_compatible_live",
            model_name="google/gemini-2.5-flash",
            provider="openrouter",
            effective_mode="openai_compatible_live",
            agent_name=kwargs["agent_name"],
            prompt_version=kwargs["prompt_version"],
            ok=False,
            latency_ms=5,
            http_status=503,
            fallback_reason="provider temporary failure",
            error="provider temporary failure",
        )


class _FakeStrictFailureProvider:
    def generate_structured(self, **kwargs):
        raise LiveModelProviderError(
            "OpenRouter call failed for Brief Intake Agent: HTTP 401 unauthorized",
            provider="openrouter",
            effective_mode="openai_compatible_live",
            model_name="google/gemini-2.5-flash",
            agent_name=kwargs["agent_name"],
            prompt_version=kwargs["prompt_version"],
            http_status=401,
            fallback_reason="provider_call_failed",
        )


def test_runtime_model_test_returns_not_ok_when_no_provider_configured(monkeypatch) -> None:
    _clear_model_env(monkeypatch)
    app = create_app()
    client = TestClient(app, headers={"X-Demo-User": "demo"})

    response = client.post("/runtime/model/test", json={})

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is False
    assert data["effective_mode"] == "rule_based_fallback"
    assert data["has_api_key"] is False
    assert data["fallback_reason"]
    assert "API_KEY" not in str(data)


def test_runtime_model_test_can_return_success_without_network(monkeypatch) -> None:
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("ENABLE_LIVE_MODEL", "true")
    monkeypatch.setenv("MODEL_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret-openrouter")
    app = create_app()
    app.state.event_producer._agent_model = _FakeSuccessProvider()
    client = TestClient(app, headers={"X-Demo-User": "demo"})

    response = client.post("/runtime/model/test", json={})

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["provider"] == "openrouter"
    assert data["effective_mode"] == "openai_compatible_live"
    assert data["http_status"] == 200
    assert data["response_shape_keys"] == ["message", "ok"]
    assert "secret-openrouter" not in str(data)


def test_strict_live_provider_failure_returns_502_from_run(monkeypatch) -> None:
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("ENABLE_LIVE_MODEL", "true")
    monkeypatch.setenv("STRICT_LIVE_MODEL", "true")
    monkeypatch.setenv("MODEL_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret-openrouter")
    app = create_app()
    app.state.event_producer._agent_model = _FakeStrictFailureProvider()
    app.state.event_producer._brief_intake_reason._provider = app.state.event_producer._agent_model
    client = TestClient(app, headers={"X-Demo-User": "demo"})

    response = client.post("/run", json={"brief": "Need a networking event for 50 pax."})

    assert response.status_code == 502
    data = response.json()
    assert data["error"]["code"] == "LIVE_MODEL_PROVIDER_FAILED"
    assert data["error"]["provider"] == "openrouter"
    assert data["error"]["agent_name"] == "brief_intake"
    assert "secret-openrouter" not in str(data)


def test_non_strict_live_provider_failure_allows_degraded_run(monkeypatch) -> None:
    _clear_model_env(monkeypatch)
    monkeypatch.setenv("ENABLE_LIVE_MODEL", "true")
    monkeypatch.setenv("STRICT_LIVE_MODEL", "false")
    monkeypatch.setenv("MODEL_PROVIDER", "openrouter")
    monkeypatch.setenv("OPENROUTER_API_KEY", "secret-openrouter")
    app = create_app()
    app.state.event_producer._agent_model = _FakeDegradedProvider()
    # Patch every reason agent that captured a provider reference at
    # construction time; otherwise this test makes real network calls.
    app.state.event_producer._brief_intake_reason._provider = app.state.event_producer._agent_model
    app.state.event_producer._creative_reason._provider = app.state.event_producer._agent_model
    app.state.event_producer._scope_strategy_reason._provider = app.state.event_producer._agent_model
    app.state.event_producer._vendor_reason._provider = app.state.event_producer._agent_model
    app.state.event_producer._orchestrator._provider = app.state.event_producer._agent_model
    client = TestClient(app, headers={"X-Demo-User": "demo"})

    response = client.post("/run", json={"brief": "Need a networking event for 50 pax."})

    assert response.status_code == 200
    data = response.json()
    assert data["agent_trace"][0]["fallback_reason"] == "provider temporary failure"
    assert data["model_mode_summary"]["brief_intake"] == "openai_compatible_live"
    assert "secret-openrouter" not in str(data)
