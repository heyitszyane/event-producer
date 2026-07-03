"""P7J regression tests for file-backed casefiles and state truth."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from event_producer.api import create_app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    """TestClient backed by an isolated casefile storage root."""
    monkeypatch.setenv("EVENT_PRODUCER_CASEFILE_ROOT", str(tmp_path / "events"))
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
    return TestClient(create_app(), headers={"X-Demo-User": "demo"})


def _casefile_payload(expected_turnout: int | None = 100) -> dict:
    return {
        "basics": {
            "working_title": "AI Industry Networking Night",
            "country": "Singapore",
            "city": "Singapore",
            "currency": "SGD",
            "budget_cap": "10000",
            "start_date": "2026-07-10",
            "end_date": "2026-07-10",
            "expected_turnout": expected_turnout,
            "event_type": "networking",
        },
        "brief": "Additional event notes.",
    }


def test_create_casefile_persists_and_reloads_100_pax(
    client: TestClient,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "events"
    monkeypatch.setenv("EVENT_PRODUCER_CASEFILE_ROOT", str(root))

    response = client.post("/casefiles", json=_casefile_payload(100))

    assert response.status_code == 200
    created = response.json()
    event_id = created["event_id"]
    assert created["resolved"]["basics"]["expected_turnout"] == 100
    assert (root / event_id / "casefile.json").exists()

    loaded = client.get(f"/casefiles/{event_id}")
    assert loaded.status_code == 200
    assert loaded.json()["resolved"]["basics"]["expected_turnout"] == 100


def test_brief_conflict_keeps_structured_expected_turnout(client: TestClient) -> None:
    payload = _casefile_payload(100)
    payload["brief"] = "Need a 50 pax AI networking night in Singapore."

    response = client.post("/casefiles", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["resolved"]["basics"]["expected_turnout"] == 100
    notices = data["resolved"]["notices"]
    assert any(
        notice["type"] == "conflict"
        and notice["field"] == "expected_turnout"
        and "50 pax" in notice["message"]
        and "100 pax" in notice["message"]
        for notice in notices
    )


def test_missing_expected_turnout_remains_missing(client: TestClient) -> None:
    payload = _casefile_payload(None)
    payload["brief"] = "Plan an AI networking night in Singapore."

    response = client.post("/casefiles", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["resolved"]["basics"]["expected_turnout"] is None
    assert data["resolved"]["sources"]["expected_turnout"] == "missing"


def test_run_existing_casefile_uses_saved_100_pax(client: TestClient) -> None:
    payload = _casefile_payload(100)
    payload["brief"] = "Need a 50 pax AI founder networking night in Singapore."
    created = client.post("/casefiles", json=payload).json()

    response = client.post("/run", json={"casefile_id": created["event_id"]})

    assert response.status_code == 200
    data = response.json()
    assert data["event_id"] == created["event_id"]
    assert data["event_spec"]["attendees"] == 100
    assert data["constraint_resolution"]["attendees"]["resolved_value"] == 100
    assert data["casefile"]["resolved"]["basics"]["expected_turnout"] == 100
    assert data["resolved_event_state"]["basics"]["expected_turnout"] == 100
    assert any(
        notice["type"] == "conflict"
        for notice in data["resolved_event_state"]["notices"]
    )


def test_local_state_is_gitignored() -> None:
    gitignore = Path(".gitignore").read_text(encoding="utf-8")
    assert ".local_state/" in gitignore


def test_timeline_records_creation_and_basics_update(client: TestClient, tmp_path: Path) -> None:
    created = client.post("/casefiles", json=_casefile_payload(100)).json()
    event_id = created["event_id"]
    updated_payload = _casefile_payload(125)["basics"]

    response = client.patch(f"/casefiles/{event_id}/basics", json=updated_payload)

    assert response.status_code == 200
    timeline = tmp_path / "events" / event_id / "timeline.jsonl"
    entries = timeline.read_text(encoding="utf-8")
    assert "casefile_created" in entries
    assert "event_basics_updated" in entries

