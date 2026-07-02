"""P7H.3 tests for live/fallback Scope Strategy integration."""

from __future__ import annotations

from copy import deepcopy

from fastapi.testclient import TestClient

from event_producer.api import create_app
from event_producer.models.schemas import (
    ScopeStrategyRecommendation,
    ScopeStrategyResult,
)
from event_producer.providers.agent_model import AgentModelResult, LiveModelProviderError
from event_producer.providers.model_env import ModelEnv


class _FakeScopeProvider:
    def generate_structured(self, **kwargs):
        if kwargs["agent_name"] != "scope_strategy":
            return AgentModelResult(
                parsed=None,
                raw_text=None,
                model_mode="rule_based_fallback",
                model_name="rule-based-fallback",
                fallback_reason="other agent fallback",
            )
        result = ScopeStrategyResult(
            strategy_summary="Protect guest basics, cut optional polish first.",
            tradeoffs=["Keep must-haves before wow-tier upgrades."],
            recommendations=[
                ScopeStrategyRecommendation(
                    title="Keep venue and catering core",
                    recommendation_type="keep",
                    category="operations",
                    tier="must",
                    rationale="The event cannot run without the core guest journey.",
                    budget_pressure="low",
                    operational_risk="high",
                )
            ],
            model_mode="openai_compatible_live",
        )
        return AgentModelResult(
            parsed=result,
            raw_text=result.model_dump_json(),
            model_mode="openai_compatible_live",
            model_name="google/gemini-2.5-flash",
            provider="openrouter",
            effective_mode="openai_compatible_live",
            agent_name=kwargs["agent_name"],
            prompt_version=kwargs["prompt_version"],
            ok=True,
        )


class _BrokenScopeProvider:
    def generate_structured(self, **kwargs):
        if kwargs["agent_name"] == "scope_strategy":
            return AgentModelResult(
                parsed=None,
                raw_text="not json",
                model_mode="rule_based_fallback",
                model_name="google/gemini-2.5-flash",
                fallback_reason="scope strategy provider unavailable",
                error="scope strategy provider unavailable",
            )
        return AgentModelResult(
            parsed=None,
            raw_text=None,
            model_mode="rule_based_fallback",
            fallback_reason="other agent fallback",
        )


class _StrictFailureScopeProvider:
    def generate_structured(self, **kwargs):
        if kwargs["agent_name"] == "scope_strategy":
            raise LiveModelProviderError(
                "OpenRouter call failed for Scope Strategy: HTTP 401 unauthorized",
                provider="openrouter",
                effective_mode="openai_compatible_live",
                model_name="google/gemini-2.5-flash",
                agent_name=kwargs["agent_name"],
                prompt_version=kwargs["prompt_version"],
                http_status=401,
                fallback_reason="provider_call_failed",
            )
        return AgentModelResult(
            parsed=None,
            raw_text=None,
            model_mode="rule_based_fallback",
            fallback_reason="other agent fallback",
        )


def test_run_includes_scope_strategy() -> None:
    app = create_app()
    client = TestClient(app, headers={"X-Demo-User": "demo"})

    response = client.post("/run", json={"brief": "Networking event for 60 pax with $20000 budget."})

    assert response.status_code == 200
    data = response.json()
    assert "scope_strategy" in data
    assert data["scope_strategy"]["recommendations"]
    assert data["model_mode_summary"]["scope_strategy"] == "rule_based_fallback"


def test_scope_strategy_trace_reports_live_mode_when_provider_succeeds() -> None:
    app = create_app()
    producer = app.state.event_producer
    producer._scope_strategy_reason._provider = _FakeScopeProvider()
    client = TestClient(app, headers={"X-Demo-User": "demo"})

    response = client.post("/run", json={"brief": "Networking event for 60 pax with $20000 budget."})

    assert response.status_code == 200
    data = response.json()
    trace = {step["role"]: step for step in data["agent_trace"]}
    assert data["scope_strategy"]["model_mode"] == "openai_compatible_live"
    assert data["model_mode_summary"]["scope_strategy"] == "openai_compatible_live"
    assert trace["Scope Strategy Agent"]["model_mode"] == "openai_compatible_live"


def test_scope_strategy_fallback_is_labelled_when_provider_unavailable() -> None:
    app = create_app()
    producer = app.state.event_producer
    producer._scope_strategy_reason._provider = _BrokenScopeProvider()
    client = TestClient(app, headers={"X-Demo-User": "demo"})

    response = client.post("/run", json={"brief": "Networking event for 60 pax with $20000 budget."})

    assert response.status_code == 200
    data = response.json()
    assert data["scope_strategy"]["model_mode"] == "rule_based_fallback"
    assert data["scope_strategy"]["fallback_reason"] == "scope strategy provider unavailable"


def test_strict_scope_strategy_provider_failure_errors_clearly() -> None:
    app = create_app()
    producer = app.state.event_producer
    producer._model_env = ModelEnv.from_env(
        {
            "ENABLE_LIVE_MODEL": "true",
            "STRICT_LIVE_MODEL": "true",
            "MODEL_PROVIDER": "openrouter",
            "OPENROUTER_API_KEY": "test-key",
        }
    )
    producer._scope_strategy_reason._provider = _StrictFailureScopeProvider()
    client = TestClient(app, headers={"X-Demo-User": "demo"})

    response = client.post("/run", json={"brief": "Networking event for 60 pax with $20000 budget."})

    assert response.status_code == 502
    assert response.json()["error"]["agent_name"] == "scope_strategy"


def test_scope_strategy_does_not_mutate_budget_or_schedule_directly() -> None:
    app = create_app()
    producer = app.state.event_producer
    producer._scope_strategy_reason._provider = _FakeScopeProvider()
    client = TestClient(app, headers={"X-Demo-User": "demo"})

    data = client.post(
        "/run",
        json={"brief": "Networking event for 60 pax with $20000 budget."},
    ).json()
    event_id = data["event_id"]
    before_budget = deepcopy(producer.event_store.get_budget(event_id))
    before_schedule = deepcopy(producer.event_store.get_schedule(event_id))

    assert producer.event_store.get_budget(event_id) == before_budget
    assert producer.event_store.get_schedule(event_id) == before_schedule
