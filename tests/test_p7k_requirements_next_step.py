"""P7K regression tests for requirements confirmation and next-step guidance."""

from __future__ import annotations

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
    return root


@pytest.fixture
def client(casefile_root: Path) -> TestClient:
    return TestClient(create_app(), headers={"X-Demo-User": "event-lead"})


def _casefile_payload(expected_turnout: int | None = 100, brief: str = "Additional event notes.") -> dict[str, Any]:
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
        "brief": brief,
    }


def test_requirements_confirmation_persists_across_reload(
    client: TestClient,
    casefile_root: Path,
) -> None:
    created = client.post("/casefiles", json=_casefile_payload()).json()

    confirmed = client.post(f"/casefiles/{created['event_id']}/requirements/confirm")

    assert confirmed.status_code == 200
    data = confirmed.json()
    assert data["status"] == "requirements_confirmed"
    assert data["requirements"]["confirmed"] is True
    assert data["requirements_confirmed_at"]
    assert data["requirements_confirmed_by"] == "event-lead"

    reloaded_client = TestClient(create_app(), headers={"X-Demo-User": "event-lead"})
    reloaded = reloaded_client.get(f"/casefiles/{created['event_id']}")

    assert reloaded.status_code == 200
    reloaded_data = reloaded.json()
    assert reloaded_data["status"] == "requirements_confirmed"
    assert reloaded_data["requirements"]["confirmed"] is True
    assert (casefile_root / created["event_id"] / "casefile.json").exists()


def test_confirming_requirements_does_not_mutate_casefile_facts_or_artifacts(
    client: TestClient,
) -> None:
    created = client.post("/casefiles", json=_casefile_payload()).json()
    event_id = created["event_id"]
    run = client.post("/run", json={"casefile_id": event_id})
    assert run.status_code == 200

    before = client.get(f"/casefiles/{event_id}").json()
    stable_before = {
        "basics": deepcopy(before["basics"]),
        "resolved": deepcopy(before["resolved"]),
        "artifacts": deepcopy(before["artifacts"]),
        "planning_assumptions": deepcopy(before["planning_assumptions"]),
    }

    confirmed = client.post(f"/casefiles/{event_id}/requirements/confirm")

    assert confirmed.status_code == 200
    after = confirmed.json()
    assert after["status"] == "requirements_confirmed"
    assert after["basics"] == stable_before["basics"]
    assert after["resolved"] == stable_before["resolved"]
    assert after["artifacts"] == stable_before["artifacts"]
    assert after["planning_assumptions"] == stable_before["planning_assumptions"]


def test_editing_basics_after_confirmation_requires_reconfirmation(
    client: TestClient,
) -> None:
    created = client.post("/casefiles", json=_casefile_payload()).json()
    event_id = created["event_id"]
    run = client.post("/run", json={"casefile_id": event_id})
    assert run.status_code == 200
    confirmed = client.post(f"/casefiles/{event_id}/requirements/confirm")
    assert confirmed.status_code == 200

    updated_basics = confirmed.json()["basics"]
    updated_basics["expected_turnout"] = 125
    response = client.patch(f"/casefiles/{event_id}/basics", json=updated_basics)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "generated"
    assert data["requirements_confirmed_at"] is None
    assert data["requirements"]["confirmed"] is False
    assert data["next_step"]["primary"]["id"] == "confirm_requirements"


def test_missing_expected_turnout_prioritizes_complete_basics_next_step(
    client: TestClient,
) -> None:
    created = client.post(
        "/casefiles",
        json=_casefile_payload(None, brief="Plan an AI networking night in Singapore."),
    )

    assert created.status_code == 200
    data = created.json()
    expected_turnout = next(
        field for field in data["requirements"]["fields"]
        if field["key"] == "expected_turnout"
    )
    assert expected_turnout["value"] is None
    assert expected_turnout["status"] == "missing"
    assert data["next_step"]["primary"]["id"] == "complete_event_basics"
    assert data["next_step"]["primary"]["target"] == "brief"


def test_generated_unconfirmed_casefile_prioritizes_confirm_requirements(
    client: TestClient,
) -> None:
    created = client.post("/casefiles", json=_casefile_payload()).json()
    run = client.post("/run", json={"casefile_id": created["event_id"]})

    assert run.status_code == 200
    data = run.json()
    assert data["casefile"]["status"] == "generated"
    assert data["next_step"]["state"] == "generated_unconfirmed"
    assert data["next_step"]["primary"]["id"] == "confirm_requirements"


def test_conflict_notice_remains_visible_after_confirmation(
    client: TestClient,
) -> None:
    created = client.post(
        "/casefiles",
        json=_casefile_payload(
            100,
            brief="Need a 50 pax AI founder networking night in Singapore.",
        ),
    ).json()

    before = client.get(f"/casefiles/{created['event_id']}")
    assert before.status_code == 200
    assert before.json()["next_step"]["primary"]["id"] == "review_requirement_notices"

    confirmed = client.post(f"/casefiles/{created['event_id']}/requirements/confirm")

    assert confirmed.status_code == 200
    data = confirmed.json()
    conflicts = data["requirements"]["conflicts"]
    assert any(
        notice["field"] == "expected_turnout" and "50 pax" in notice["message"]
        for notice in conflicts
    )
    assert any(
        notice["field"] == "expected_turnout" and "100 pax" in notice["message"]
        for notice in data["resolved"]["notices"]
    )
