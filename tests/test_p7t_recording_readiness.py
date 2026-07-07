"""P7T recording-readiness fixes.

These tests cover user-facing demo polish that matters during the capstone
recording: the Singapore seed title, approval persistence after navigation,
and backend startup loading the repo-local .env provider settings.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from event_producer import api
from event_producer.api import create_app
from event_producer.seeds import LEGACY_SINGAPORE_TITLE, SINGAPORE_SEED_ID


_MODEL_ENV_KEYS = (
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
)


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
    monkeypatch.setenv("EVENT_PRODUCER_CASEFILE_ROOT", str(tmp_path / "events"))
    for key in _MODEL_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    return TestClient(create_app(), headers={"X-Demo-User": "demo"})


def test_seed_demo_uses_singapore_ai_founder_title_and_migrates_old_seed(
    client: TestClient,
) -> None:
    seeded = client.post("/casefiles/seed")
    assert seeded.status_code == 200

    sg = client.get(f"/casefiles/{SINGAPORE_SEED_ID}").json()
    assert sg["basics"]["working_title"] == "Singapore AI Founder Networking Night"

    store = client.app.state.event_producer.casefile_store
    old_basics = store.get_casefile(SINGAPORE_SEED_ID).basics.model_copy(
        update={"working_title": LEGACY_SINGAPORE_TITLE}
    )
    store.update_basics(SINGAPORE_SEED_ID, old_basics)

    reseeded = client.post("/casefiles/seed")
    assert reseeded.status_code == 200

    migrated = client.get(f"/casefiles/{SINGAPORE_SEED_ID}").json()
    assert migrated["basics"]["working_title"] == "Singapore AI Founder Networking Night"


def test_event_approval_status_persists_to_run_snapshot(client: TestClient) -> None:
    created = client.post(
        "/casefiles",
        json={
            "basics": {
                "working_title": "Approval Persistence Demo",
                "country": "Singapore",
                "city": "Singapore",
                "currency": "SGD",
                "budget_cap": "10000",
                "expected_turnout": 80,
                "event_type": "networking",
            },
            "brief": "Founder networking night for 80 guests with SGD 10,000 budget.",
        },
    )
    assert created.status_code == 200
    event_id = created.json()["event_id"]

    run = client.post("/run", json={"casefile_id": event_id})
    assert run.status_code == 200
    approval = next(a for a in run.json()["approvals"] if a["status"] == "pending")

    approved = client.post(
        f"/event/{event_id}/approvals/{approval['id']}",
        json={"action": "approve"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    snapshot = client.get(f"/casefiles/{event_id}/run-snapshot")
    assert snapshot.status_code == 200
    body = snapshot.json()
    saved = next(a for a in body["approvals"] if a["id"] == approval["id"])
    nested = next(
        a for a in body["run_of_show"]["approvals"] if a["id"] == approval["id"]
    )
    assert saved["status"] == "approved"
    assert nested["status"] == "approved"


def test_create_app_loads_repo_env_without_settings_resave(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in _MODEL_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("EVENT_PRODUCER_LOAD_DOTENV", "true")
    monkeypatch.setattr(
        api,
        "read_env_file",
        lambda: {
            "ENABLE_LIVE_MODEL": "true",
            "MODEL_PROVIDER": "openrouter",
            "OPENROUTER_API_KEY": "secret-openrouter",
            "OPENROUTER_MODEL": "google/gemini-2.5-flash",
        },
    )

    app = create_app()
    client = TestClient(app, headers={"X-Demo-User": "demo"})

    response = client.get("/runtime/model")
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "openrouter"
    assert data["live_enabled"] is True
    assert data["effective_mode"] == "openai_compatible_live"
    assert data["has_api_key"] is True
    assert "secret-openrouter" not in str(data)
