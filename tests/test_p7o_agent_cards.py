"""P7O — agent skill-card registry: contract validation + API surface.

The cards under ``event_producer/agents/cards/`` are runtime-loaded role
contracts. These tests reject cards that drift from the runtime (unknown
artifacts, missing prompt files, dishonest boundary claims) and pin the
registry's honest shape.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from event_producer.agents.cards import (
    ALLOWED_KINDS,
    DIRECT_AGENT_IDS,
    KNOWN_ARTIFACTS,
    load_agent_cards,
)
from event_producer.api import create_app


@pytest.fixture
def client() -> TestClient:
    return TestClient(create_app(), headers={"X-Demo-User": "demo"})


def cards_by_name() -> dict[str, dict]:
    return {card["name"]: card for card in load_agent_cards()}


def test_registry_loads_full_crew() -> None:
    cards = load_agent_cards()
    names = [card["name"] for card in cards]
    assert names == [
        "orchestrator",
        "brief_intake",
        "scope_configurator",
        "creative_concept",
        "scope_strategy",
        "vendor_copy",
        "risk_review",
        "budget_engine",
        "run_sheet_scheduler",
        "approval_gate",
    ], "crew registry drifted — update cards AND this contract test together"


def test_every_card_has_valid_contract_fields() -> None:
    for card in load_agent_cards():
        assert card["kind"] in ALLOWED_KINDS
        assert card["capabilities"], f"{card['name']}: capabilities empty"
        assert card["purpose"].strip(), f"{card['name']}: purpose empty"
        assert card["instructions"].strip(), f"{card['name']}: body empty"
        assert card["ui"]["route"], f"{card['name']}: ui.route missing"
        boundaries = card["boundaries"]
        # This build has no outbound integrations; no card may claim any.
        assert boundaries["external_actions"] == "none", card["name"]
        assert boundaries["mutates_critical_facts"] is False, card["name"]


def test_llm_cards_reference_real_prompt_files() -> None:
    prompts_root = Path("event_producer/agents")
    for card in load_agent_cards():
        if card["kind"] == "llm_agent":
            prompt = card["model_routing"]["prompt"]
            assert (prompts_root / prompt).is_file(), f"{card['name']}: {prompt}"
        else:
            assert card.get("model_routing") is None, (
                f"{card['name']}: non-LLM card must not claim model routing"
            )


def test_artifact_claims_match_casefile_store() -> None:
    claimed = {
        card["output"]["artifact"]
        for card in load_agent_cards()
        if card["output"]["artifact"] is not None
    }
    assert claimed <= KNOWN_ARTIFACTS
    # Direct specialists must each own a saved artifact.
    for card in load_agent_cards():
        if card["runtime"]["direct_agent_id"] is not None:
            assert card["output"]["artifact"] is not None, card["name"]


def test_direct_specialists_match_runtime_ids() -> None:
    direct = {
        card["runtime"]["direct_agent_id"]
        for card in load_agent_cards()
        if card["runtime"]["direct_agent_id"] is not None
    }
    assert direct == set(DIRECT_AGENT_IDS)


def test_boundary_claims_stay_honest() -> None:
    cards = cards_by_name()
    # The orchestrator proposes; it never applies.
    assert cards["orchestrator"]["boundaries"]["proposes_only"] is True
    # Vendor copy is draft-only and gated before external use.
    assert cards["vendor_copy"]["boundaries"]["requires_human_approval_for"]
    # The gate is structural, not an LLM.
    assert cards["approval_gate"]["kind"] == "structural_gate"
    # Money and time truth are deterministic engines, not model output.
    assert cards["budget_engine"]["kind"] == "deterministic_engine"
    assert cards["run_sheet_scheduler"]["kind"] == "deterministic_engine"
    # Risk review is deliberately deterministic (reproducible findings).
    assert cards["risk_review"]["kind"] == "rule_based_agent"


def test_agents_endpoint_serves_registry(client: TestClient) -> None:
    response = client.get("/agents")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["agents"]) == 10
    first = payload["agents"][0]
    assert first["name"] == "orchestrator"
    assert "instructions" in first and "boundaries" in first
