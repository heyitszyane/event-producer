"""P7H.2 tests for the live-backed orchestrator agent."""

from __future__ import annotations

from copy import deepcopy

from fastapi.testclient import TestClient

from event_producer.agents.orchestrator import OrchestratorAgent
from event_producer.api import create_app
from event_producer.main import EventProducerApp
from event_producer.models.schemas import OrchestratorAgentResult
from event_producer.providers.agent_model import AgentModelResult, LiveModelProviderError
from event_producer.providers.model_env import ModelEnv


class _FakeLiveOrchestratorProvider:
    def generate_structured(self, **kwargs):
        result = OrchestratorAgentResult(
            reply="I can premium-up the guest experience while keeping the change human-applied.",
            proposals=[
                {
                    "id": "",
                    "type": "add_scope_item",
                    "title": "Host-led welcome moment",
                    "rationale": "Adds a premium-feeling moment without changing the core schedule.",
                    "payload": {
                        "name": "Host-led welcome moment",
                        "description": "Brief guided welcome and guest orientation.",
                        "category": "program",
                        "tier": "should",
                        "estimated_cost": "750",
                        "currency": "USD",
                        "qty": "1",
                    },
                    "requires_confirmation": False,
                    "requires_approval_gate": False,
                    "model_mode": "rule_based_fallback",
                    "created_at": "",
                }
            ],
            rationale_summary="Use a bounded add, not a full replan.",
            risk_notes=["Keep Budget Engine as source of truth."],
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


class _FakeApprovalGateProvider:
    def generate_structured(self, **kwargs):
        result = OrchestratorAgentResult(
            reply="This should go through the approval wall.",
            proposals=[
                {
                    "id": "prop_vendor",
                    "type": "create_approval",
                    "title": "Approve vendor outreach",
                    "rationale": "Vendor-facing outreach must be approved before sending.",
                    "payload": {
                        "action": "send_vendor_message",
                        "notes": "Send RFP email to venue vendor.",
                    },
                    "requires_confirmation": True,
                    "requires_approval_gate": False,
                    "model_mode": "rule_based_fallback",
                    "created_at": "",
                }
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


class _FakeFallbackProvider:
    def generate_structured(self, **_kwargs):
        return AgentModelResult(
            parsed=None,
            raw_text=None,
            model_mode="rule_based_fallback",
            model_name="rule-based-fallback",
            fallback_reason="provider unavailable in non-strict mode",
            error="provider unavailable in non-strict mode",
        )


class _FakeStrictFailureProvider:
    def generate_structured(self, **kwargs):
        raise LiveModelProviderError(
            "OpenRouter call failed for Orchestrator: HTTP 401 unauthorized",
            provider="openrouter",
            effective_mode="openai_compatible_live",
            model_name="google/gemini-2.5-flash",
            agent_name=kwargs["agent_name"],
            prompt_version=kwargs["prompt_version"],
            http_status=401,
            fallback_reason="provider_call_failed",
        )


def _run_event(client: TestClient) -> dict:
    response = client.post(
        "/run",
        json={"brief": "Networking event for 60 pax with $20000 budget."},
    )
    assert response.status_code == 200
    return response.json()


def _context_from_run(run: dict) -> dict:
    return {
        "event_id": run["event_id"],
        "event_spec": run["event_spec"],
        "scope_items": run["scope_items"],
        "budget_summary": run["budget_summary"],
        "schedule_result": run["schedule_result"],
        "approvals": run["approvals"],
        "risk_flags": run["risk_flags"],
    }


def test_orchestrator_with_fake_live_provider_returns_live_mode() -> None:
    app = EventProducerApp()
    run = app.run_event(brief="Networking event for 60 pax with $20000 budget.")
    agent = OrchestratorAgent(
        event_store=app.event_store,
        provider=_FakeLiveOrchestratorProvider(),
    )

    result = agent.run("Make this feel more premium but stay under budget.", _context_from_run(run))

    assert result.model_mode == "openai_compatible_live"
    assert result.fallback_reason is None
    assert result.proposals
    assert result.proposals[0].model_mode == "openai_compatible_live"
    assert result.proposals[0].id
    assert result.proposals[0].requires_confirmation is True


def test_orchestrator_run_never_mutates_event_state() -> None:
    app = EventProducerApp()
    run = app.run_event(brief="Networking event for 60 pax with $20000 budget.")
    before_scope = deepcopy(app.event_store.get_scope(run["event_id"]))
    before_budget = app.event_store.get_budget(run["event_id"])
    agent = OrchestratorAgent(
        event_store=app.event_store,
        provider=_FakeLiveOrchestratorProvider(),
    )

    agent.run("Add a premium moment.", _context_from_run(run))

    assert app.event_store.get_scope(run["event_id"]) == before_scope
    assert app.event_store.get_budget(run["event_id"]) == before_budget


def test_chat_stores_live_provider_proposal_and_apply_is_explicit() -> None:
    app = create_app()
    producer = app.state.event_producer
    producer._orchestrator = OrchestratorAgent(
        event_store=producer.event_store,
        provider=_FakeLiveOrchestratorProvider(),
    )
    client = TestClient(app, headers={"X-Demo-User": "demo"})
    run = _run_event(client)
    initial_count = len(run["scope_items"])

    chat = client.post(
        f"/event/{run['event_id']}/chat",
        json={"message": "Make this feel more premium but stay under budget."},
    )
    assert chat.status_code == 200
    data = chat.json()
    assert data["model_mode"] == "openai_compatible_live"
    assert data["proposals"][0]["model_mode"] == "openai_compatible_live"

    unchanged = client.get(f"/event/{run['event_id']}").json()
    assert len(unchanged["scope_items"]) == initial_count

    applied = client.post(f"/event/{run['event_id']}/proposals/{data['proposals'][0]['id']}/apply")
    assert applied.status_code == 200
    assert len(applied.json()["scope_items"]) == initial_count + 1


def test_approval_gated_proposal_cannot_apply_through_generic_apply() -> None:
    app = create_app()
    producer = app.state.event_producer
    producer._orchestrator = OrchestratorAgent(
        event_store=producer.event_store,
        provider=_FakeApprovalGateProvider(),
    )
    client = TestClient(app, headers={"X-Demo-User": "demo"})
    run = _run_event(client)

    chat = client.post(
        f"/event/{run['event_id']}/chat",
        json={"message": "Send a venue RFP."},
    )

    proposal = chat.json()["proposals"][0]
    assert proposal["requires_approval_gate"] is True
    apply_response = client.post(f"/event/{run['event_id']}/proposals/{proposal['id']}/apply")
    assert apply_response.status_code == 422


def test_orchestrator_fallback_visible_when_provider_unavailable() -> None:
    app = EventProducerApp()
    run = app.run_event(brief="Networking event for 60 pax with $20000 budget.")
    agent = OrchestratorAgent(
        event_store=app.event_store,
        provider=_FakeFallbackProvider(),
    )

    result = agent.run("Make this feel more premium.", _context_from_run(run))

    assert result.model_mode == "rule_based_fallback"
    assert result.fallback_reason == "provider unavailable in non-strict mode"


def test_strict_live_provider_failure_returns_chat_api_error() -> None:
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
    producer._orchestrator = OrchestratorAgent(
        event_store=producer.event_store,
        provider=_FakeStrictFailureProvider(),
    )
    client = TestClient(app, headers={"X-Demo-User": "demo"})
    run = _run_event(client)

    response = client.post(
        f"/event/{run['event_id']}/chat",
        json={"message": "Make this feel more premium."},
    )

    assert response.status_code == 502
    data = response.json()
    assert data["error"]["code"] == "LIVE_MODEL_PROVIDER_FAILED"
    assert data["error"]["agent_name"] == "orchestrator"
    assert "test-key" not in str(data)
