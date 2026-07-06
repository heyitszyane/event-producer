"""P7R — committed demo casefiles are seeded idempotently and come populated."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from event_producer.api import create_app
from event_producer.seeds import SEED_CASEFILES


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> TestClient:
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
    ):
        monkeypatch.delenv(key, raising=False)
    return TestClient(create_app(), headers={"X-Demo-User": "demo"})


def test_seed_creates_two_demo_casefiles(client: TestClient) -> None:
    res = client.post("/casefiles/seed")
    assert res.status_code == 200
    data = res.json()
    expected_ids = [spec["event_id"] for spec in SEED_CASEFILES]
    assert data["seeded_ids"] == expected_ids
    listed = {c["event_id"] for c in data["casefiles"]}
    assert set(expected_ids).issubset(listed)


def test_seed_casefiles_come_populated(client: TestClient) -> None:
    client.post("/casefiles/seed")
    # The first pass ran during seeding, so a run snapshot with scope + budget
    # exists and is restorable.
    snap = client.get("/casefiles/seed-la-product-launch/run-snapshot")
    assert snap.status_code == 200
    body = snap.json()
    assert body.get("scope_items")
    assert body.get("budget_summary")


def test_seed_is_idempotent(client: TestClient) -> None:
    first = client.post("/casefiles/seed").json()
    second = client.post("/casefiles/seed").json()
    # Re-seeding must not duplicate casefiles.
    assert len(first["casefiles"]) == len(second["casefiles"])
    la = [c for c in second["casefiles"] if c["event_id"] == "seed-la-product-launch"]
    assert len(la) == 1
