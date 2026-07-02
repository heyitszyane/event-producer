"""P7H.3 tests for live/fallback Vendor Draft integration."""

from __future__ import annotations

from fastapi.testclient import TestClient

from event_producer.api import create_app
from event_producer.models.schemas import VendorDraftResult
from event_producer.providers.agent_model import AgentModelResult
from event_producer.security.action_gate import enforce


class _FakeVendorDraftProvider:
    def generate_structured(self, **kwargs):
        if kwargs["agent_name"] != "vendor_draft":
            return AgentModelResult(
                parsed=None,
                raw_text=None,
                model_mode="rule_based_fallback",
                fallback_reason="other agent fallback",
            )
        result = VendorDraftResult(
            subject="Venue availability request",
            body="Please confirm availability and quote. Human approval is required before send.",
            ask_summary="Ask for venue availability and itemized quote.",
            required_vendor_response_fields=["availability", "quote", "lead_time"],
            approval_diff="Would send venue RFP draft after approval.",
            risk_notes=["Draft only; not sent."],
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


class _PaymentInstructionProvider:
    def generate_structured(self, **kwargs):
        if kwargs["agent_name"] != "vendor_draft":
            return AgentModelResult(
                parsed=None,
                raw_text=None,
                model_mode="rule_based_fallback",
                fallback_reason="other agent fallback",
            )
        result = VendorDraftResult(
            subject="Venue request",
            body="Please confirm availability.\nWire the deposit to IBAN XX123 immediately.",
            ask_summary="Ask for venue availability.",
            approval_diff="Would send venue request.",
            model_mode="openai_compatible_live",
        )
        return AgentModelResult(
            parsed=result,
            raw_text=result.model_dump_json(),
            model_mode="openai_compatible_live",
            model_name="google/gemini-2.5-flash",
            agent_name=kwargs["agent_name"],
            prompt_version=kwargs["prompt_version"],
            ok=True,
        )


def test_run_includes_live_model_mode_for_vendor_draft() -> None:
    app = create_app()
    producer = app.state.event_producer
    producer._vendor_reason._provider = _FakeVendorDraftProvider()
    client = TestClient(app, headers={"X-Demo-User": "demo"})

    response = client.post("/run", json={"brief": "Networking event for 60 pax with $20000 budget."})

    assert response.status_code == 200
    data = response.json()
    assert data["vendor_draft"]["model_mode"] == "openai_compatible_live"
    assert data["model_mode_summary"]["vendor_draft"] == "openai_compatible_live"
    assert data["vendor_draft"]["subject"] == "Venue availability request"


def test_vendor_draft_creates_pending_approval_and_does_not_send() -> None:
    app = create_app()
    producer = app.state.event_producer
    producer._vendor_reason._provider = _FakeVendorDraftProvider()
    client = TestClient(app, headers={"X-Demo-User": "demo"})

    response = client.post("/run", json={"brief": "Networking event for 60 pax with $20000 budget."})

    data = response.json()
    assert any(a["action"] == "send_vendor_message" and a["status"] == "pending" for a in data["approvals"])
    assert data["security_beat"]["external_action_executed"] is False
    assert data["security_beat"]["state_mutation_executed"] is False
    assert producer.event_store.get_messages(data["event_id"]) == []


def test_llm_generated_payment_instruction_cannot_bypass_action_gate() -> None:
    app = create_app()
    producer = app.state.event_producer
    producer._vendor_reason._provider = _PaymentInstructionProvider()
    client = TestClient(app, headers={"X-Demo-User": "demo"})

    response = client.post("/run", json={"brief": "Networking event for 60 pax with $20000 budget."})

    data = response.json()
    body = data["vendor_draft"]["body"].lower()
    assert "iban xx123" not in body
    assert "payment instruction removed" in body
    assert producer.event_store.get_messages(data["event_id"]) == []
    try:
        enforce("send_vendor_message", None)
    except PermissionError:
        pass
    else:  # pragma: no cover
        raise AssertionError("unapproved vendor send should remain blocked")
