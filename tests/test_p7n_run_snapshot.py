"""P7N regression tests — run-snapshot persistence and runtime rehydration.

The in-memory event store loses runtime state on backend restart. P7N persists
a ``run-snapshot`` casefile artifact after every pipeline run so:

1. The frontend can restore the last run after a page reload.
2. The backend can rehydrate scope/budget/schedule/approvals for saved
   casefiles after a restart (scope edits keep working).
3. Scope edits write back to the snapshot, so reloads show the edited state.
"""

from __future__ import annotations

from decimal import Decimal
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


def _casefile_payload() -> dict:
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
        "brief": "A 100 pax AI networking night with light F&B and basic AV.",
    }


def _run_casefile(client: TestClient) -> str:
    created = client.post("/casefiles", json=_casefile_payload())
    assert created.status_code == 200
    event_id = created.json()["event_id"]
    run = client.post("/run", json={"casefile_id": event_id})
    assert run.status_code == 200
    return event_id


def test_run_persists_run_snapshot_artifact(client: TestClient) -> None:
    event_id = _run_casefile(client)

    casefile = client.get(f"/casefiles/{event_id}").json()
    assert "run-snapshot" in casefile["artifacts"]

    snapshot = client.get(f"/casefiles/{event_id}/run-snapshot")
    assert snapshot.status_code == 200
    body = snapshot.json()
    assert body["event_id"] == event_id
    assert body["scope_items"]
    assert body["budget_summary"]["budget_cap"]
    assert body["casefile"]["event_id"] == event_id
    # Casefile-derived keys are attached at read time.
    assert body["requirements"] is not None


def test_run_snapshot_404_before_first_run(client: TestClient) -> None:
    created = client.post("/casefiles", json=_casefile_payload())
    event_id = created.json()["event_id"]
    response = client.get(f"/casefiles/{event_id}/run-snapshot")
    assert response.status_code == 404


def test_scope_mutation_survives_backend_restart(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A fresh app (restart) rehydrates the event runtime from the snapshot."""
    event_id = _run_casefile(client)

    fresh_client = TestClient(create_app(), headers={"X-Demo-User": "demo"})
    toggled = fresh_client.post(f"/event/{event_id}/scope-items/0/toggle")
    assert toggled.status_code == 200
    body = toggled.json()
    assert body["scope_items"][0]["selected"] is False
    assert "Budget recalculated." in body["recompute_notice"]["message"]


def test_scope_edit_writes_back_to_snapshot(client: TestClient) -> None:
    """Reloading after a scope edit must show the edited state."""
    event_id = _run_casefile(client)

    before = client.get(f"/casefiles/{event_id}/run-snapshot").json()
    first_selected = before["scope_items"][0]["selected"]

    toggled = client.post(f"/event/{event_id}/scope-items/0/toggle")
    assert toggled.status_code == 200

    after = client.get(f"/casefiles/{event_id}/run-snapshot").json()
    assert after["scope_items"][0]["selected"] is (not first_selected)
    assert Decimal(after["budget_summary"]["included_totals"]) == Decimal(
        str(toggled.json()["budget_summary"]["included_totals"])
    )


def test_generic_artifact_endpoint_reads_saved_payloads(client: TestClient) -> None:
    event_id = _run_casefile(client)

    ok = client.get(f"/casefiles/{event_id}/artifacts/creative-concept")
    assert ok.status_code == 200
    assert ok.json()["name"] == "creative-concept"
    assert ok.json()["payload"]

    unknown = client.get(f"/casefiles/{event_id}/artifacts/not-a-real-artifact")
    assert unknown.status_code == 404

    missing = client.get(f"/casefiles/{event_id}/artifacts/risk-review")
    assert missing.status_code == 404


def test_vendor_copy_artifact_route_keeps_draft_shape(client: TestClient) -> None:
    """The generic artifact route must not shadow the vendor-copy draft route."""
    event_id = _run_casefile(client)
    response = client.get(f"/casefiles/{event_id}/artifacts/vendor-copy")
    assert response.status_code == 200
    body = response.json()
    assert "draft" in body
    assert "subject" in body["draft"]


def test_storage_info_endpoint_reports_local_root(client: TestClient, tmp_path: Path) -> None:
    _run_casefile(client)
    response = client.get("/settings/storage")
    assert response.status_code == 200
    body = response.json()
    assert body["storage_kind"] == "local_json"
    assert str(tmp_path / "events") in body["root"]
    assert body["casefile_count"] >= 1
