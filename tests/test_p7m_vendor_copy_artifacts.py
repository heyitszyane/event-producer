"""P7M regression tests for editable vendor-copy artifacts."""

from __future__ import annotations

import json
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


def _run_vendor_copy(client: TestClient, event_id: str, instruction: str = "Draft a short venue inquiry.") -> dict[str, Any]:
    response = client.post(
        f"/casefiles/{event_id}/agents/vendor_copy/run",
        json={"instruction": instruction},
    )
    assert response.status_code == 200
    return response.json()


def _timeline_entries(casefile_root: Path, event_id: str) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in (casefile_root / event_id / "timeline.jsonl").read_text(encoding="utf-8").splitlines()
    ]


def test_vendor_copy_draft_saves_and_reloads_from_artifact_endpoint(
    client: TestClient,
    casefile_root: Path,
) -> None:
    event_id = _create_confirmed_casefile(client)
    _run_vendor_copy(client, event_id)

    response = client.get(f"/casefiles/{event_id}/artifacts/vendor-copy")

    assert response.status_code == 200
    data = response.json()
    assert data["artifact"]["name"] == "vendor-copy"
    assert data["draft"]["subject"]
    assert data["draft"]["body"]
    assert data["draft"]["source_agent"] == "vendor_copy"
    assert (casefile_root / event_id / "artifacts" / "vendor-copy.json").exists()


def test_vendor_copy_save_persists_edits_and_appends_timeline(
    client: TestClient,
    casefile_root: Path,
) -> None:
    event_id = _create_confirmed_casefile(client)
    _run_vendor_copy(client, event_id)
    draft = client.get(f"/casefiles/{event_id}/artifacts/vendor-copy").json()["draft"]
    draft.update(
        {
            "subject": "Venue inquiry for AI networking night, 10 July",
            "body": "Hi team,\n\nPlease confirm availability, capacity, AV, and minimum spend.",
            "ask_summary": "Check venue availability, minimum spend, AV, and F&B package.",
            "required_vendor_response_fields": ["availability", "capacity", "minimum_spend", "included_av"],
            "risk_notes": ["Review budget assumptions before contacting vendor."],
        }
    )

    saved = client.put(f"/casefiles/{event_id}/artifacts/vendor-copy", json=draft)

    assert saved.status_code == 200
    saved_data = saved.json()
    assert saved_data["draft"]["subject"] == "Venue inquiry for AI networking night, 10 July"
    assert saved_data["draft"]["updated_at"]

    reloaded = client.get(f"/casefiles/{event_id}/artifacts/vendor-copy").json()
    assert reloaded["draft"]["body"].startswith("Hi team")

    casefile = client.get(f"/casefiles/{event_id}").json()
    assert casefile["artifacts"]["vendor-copy"]["updated_at"] == saved_data["artifact"]["updated_at"]

    artifact_payload = json.loads((casefile_root / event_id / "artifacts" / "vendor-copy.json").read_text(encoding="utf-8"))
    assert artifact_payload["output"]["subject"] == "Venue inquiry for AI networking night, 10 July"
    assert artifact_payload["output"]["review_required_before_external_use"] is True

    timeline_types = [entry["type"] for entry in _timeline_entries(casefile_root, event_id)]
    assert "vendor_copy_generated" in timeline_types
    assert "vendor_copy_saved" in timeline_types


def test_vendor_copy_refine_stores_artifact_only_without_approvals(client: TestClient) -> None:
    event_id = _create_confirmed_casefile(client)
    _run_vendor_copy(client, event_id)

    refined = client.post(
        f"/casefiles/{event_id}/agents/vendor_copy/run",
        json={"instruction": "Make shorter", "regenerate": True, "artifact_id": "vendor-copy"},
    )

    assert refined.status_code == 200
    output = refined.json()["output"]["output"]
    assert output["draft_only"] is True
    assert output["review_required_before_external_use"] is True
    assert client.app.state.event_producer.event_store.get_approvals(event_id) == []


def test_vendor_copy_save_response_does_not_claim_outbound_contact(client: TestClient) -> None:
    event_id = _create_confirmed_casefile(client)
    _run_vendor_copy(client, event_id)
    draft = client.get(f"/casefiles/{event_id}/artifacts/vendor-copy").json()["draft"]
    draft["subject"] = "Updated venue inquiry"

    response = client.put(f"/casefiles/{event_id}/artifacts/vendor-copy", json=draft)

    assert response.status_code == 200
    response_text = json.dumps(response.json()).lower()
    assert "sent" not in response_text
    assert "contacted" not in response_text
    assert "outbound_executed" not in response_text
