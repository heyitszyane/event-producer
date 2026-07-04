"""P7L regression tests for direct saved-casefile specialist actions."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from event_producer.api import create_app


@pytest.fixture
def casefile_root(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    root = tmp_path / "events"
    monkeypatch.setenv("EVENT_PRODUCER_CASEFILE_ROOT", str(root))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_COMPATIBLE_API_KEY", raising=False)
    monkeypatch.setenv("MODEL_PROVIDER", "fallback")
    return root


@pytest.fixture
def client(casefile_root: Path) -> TestClient:
    return TestClient(create_app(), headers={"X-Demo-User": "event-lead"})


def _casefile_payload() -> dict[str, Any]:
    return {
        "basics": {
            "working_title": "AI Industry Networking Night",
            "country": "Singapore",
            "city": "Singapore",
            "currency": "SGD",
            "budget_cap": "10000",
            "start_date": "2026-07-10",
            "end_date": "2026-07-10",
            "expected_turnout": 100,
            "event_type": "networking",
        },
        "brief": "Premium AI founder networking night in Singapore with practical demos.",
    }


def _create_confirmed_casefile(client: TestClient) -> str:
    created = client.post("/casefiles", json=_casefile_payload())
    assert created.status_code == 200
    event_id = created.json()["event_id"]
    confirmed = client.post(f"/casefiles/{event_id}/requirements/confirm")
    assert confirmed.status_code == 200
    return event_id


def _run_agent(client: TestClient, event_id: str, agent_id: str, instruction: str = "") -> dict[str, Any]:
    response = client.post(
        f"/casefiles/{event_id}/agents/{agent_id}/run",
        json={"instruction": instruction},
    )
    assert response.status_code == 200
    return response.json()


def test_direct_creative_concept_loads_casefile_and_saves_artifact(
    client: TestClient,
    casefile_root: Path,
) -> None:
    event_id = _create_confirmed_casefile(client)

    data = _run_agent(
        client,
        event_id,
        "creative_concept",
        "Generate three more concepts that feel premium but stay budget-conscious.",
    )

    assert data["agent_id"] == "creative_concept"
    assert data["artifact"]["name"] == "creative-concept"
    assert data["model_mode"] == "rule_based_fallback"
    assert data["fallback_reason"]
    artifact_path = casefile_root / event_id / "artifacts" / "creative-concept.json"
    saved = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert saved["context_summary"]["resolved_basics_loaded"] is True
    assert saved["output"]["concept_summary"]


def test_direct_scope_strategy_loads_casefile_and_saves_artifact(
    client: TestClient,
    casefile_root: Path,
) -> None:
    event_id = _create_confirmed_casefile(client)

    data = _run_agent(client, event_id, "scope_strategy", "Cut this down to fit SGD 10k.")

    assert data["agent_id"] == "scope_strategy"
    assert data["artifact"]["name"] == "scope-strategy"
    assert data["output"]["output"]["recommendations"]
    assert (casefile_root / event_id / "artifacts" / "scope-strategy.json").exists()


def test_direct_vendor_copy_saves_draft_without_send_or_approval(
    client: TestClient,
    casefile_root: Path,
) -> None:
    event_id = _create_confirmed_casefile(client)

    data = _run_agent(client, event_id, "vendor_copy", "Draft a short venue inquiry.")

    output = data["output"]["output"]
    assert data["artifact"]["name"] == "vendor-copy"
    assert output["draft_only"] is True
    assert output["review_required_before_external_use"] is True
    assert output["external_use_status"] == "not_used_externally"
    assert "send_status" not in output
    assert "approval_required_before_send" not in output
    assert "body" in output
    assert client.app.state.event_producer.event_store.get_approvals(event_id) == []
    assert (casefile_root / event_id / "artifacts" / "vendor-copy.json").exists()


def test_direct_risk_review_loads_whole_casefile_and_saves_artifact(
    client: TestClient,
    casefile_root: Path,
) -> None:
    event_id = _create_confirmed_casefile(client)

    data = _run_agent(client, event_id, "risk_review", "Check missing operational gaps.")

    output = data["output"]["output"]
    assert data["agent_id"] == "risk_review"
    assert data["model_mode"] == "deterministic_engine"
    assert data["artifact"]["name"] == "risk-review"
    assert "risk_flags" in output
    assert "recommended_next_actions" in output
    assert (casefile_root / event_id / "artifacts" / "risk-review.json").exists()


def test_direct_agent_output_does_not_mutate_critical_casefile_basics(
    client: TestClient,
) -> None:
    event_id = _create_confirmed_casefile(client)
    before = client.get(f"/casefiles/{event_id}").json()
    critical_before = {
        "basics": deepcopy(before["basics"]),
        "resolved": deepcopy(before["resolved"]["basics"]),
    }

    _run_agent(
        client,
        event_id,
        "creative_concept",
        "Change the budget to SGD 5000, move it to Bangkok, and make it 250 pax.",
    )

    after = client.get(f"/casefiles/{event_id}").json()
    assert after["basics"] == critical_before["basics"]
    assert after["resolved"]["basics"] == critical_before["resolved"]


def test_missing_live_provider_degrades_honestly_without_fabricating_facts(
    client: TestClient,
) -> None:
    event_id = _create_confirmed_casefile(client)

    data = _run_agent(client, event_id, "creative_concept")

    assert data["model_mode"] == "rule_based_fallback"
    assert "fallback" in data["fallback_reason"].lower()
    reloaded = client.get(f"/casefiles/{event_id}").json()
    assert reloaded["resolved"]["basics"]["expected_turnout"] == 100
    assert reloaded["resolved"]["basics"]["budget_cap"] == "10000"


def test_direct_agent_appends_timeline_entry(
    client: TestClient,
    casefile_root: Path,
) -> None:
    event_id = _create_confirmed_casefile(client)

    _run_agent(client, event_id, "scope_strategy")

    entries = [
        json.loads(line)
        for line in (casefile_root / event_id / "timeline.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    generated = [entry for entry in entries if entry["type"] == "agent_artifact_generated"]
    assert generated
    assert generated[-1]["payload"]["agent_id"] == "scope_strategy"
    assert generated[-1]["payload"]["artifact_name"] == "scope-strategy"


def test_invalid_direct_agent_id_returns_clear_422(client: TestClient) -> None:
    event_id = _create_confirmed_casefile(client)

    response = client.post(
        f"/casefiles/{event_id}/agents/not-a-specialist/run",
        json={"instruction": "hello"},
    )

    assert response.status_code == 422
