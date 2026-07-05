"""P7O regression tests for user-configurable contingency %.

Covers the path from the ``EventBasics.contingency_pct`` field through the
casefile store, the ``run_casefile`` override wiring, and the deterministic
Budget Engine's zero-sum invariant. Contingency is optional: when unset it
resolves to the engine default (15%) and never blocks confirmation.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from event_producer.api import create_app


@pytest.fixture
def client() -> TestClient:
    """TestClient with isolated storage + fallback model env (see conftest)."""
    return TestClient(create_app(), headers={"X-Demo-User": "demo"})


def _basics(contingency_pct: str | None = None) -> dict:
    basics: dict = {
        "working_title": "AI Industry Networking Night",
        "country": "Singapore",
        "city": "Singapore",
        "currency": "SGD",
        "budget_cap": "10000",
        "start_date": "2026-07-10",
        "end_date": "2026-07-10",
        "expected_turnout": 100,
        "event_type": "networking",
    }
    if contingency_pct is not None:
        basics["contingency_pct"] = contingency_pct
    return basics


def _create(client: TestClient, contingency_pct: str | None = None) -> str:
    response = client.post(
        "/casefiles",
        json={"basics": _basics(contingency_pct), "brief": "Additional event notes."},
    )
    assert response.status_code == 200, response.text
    return response.json()["event_id"]


def test_user_contingency_pct_flows_into_budget_engine(client: TestClient) -> None:
    event_id = _create(client, contingency_pct="20")

    created = client.get(f"/casefiles/{event_id}").json()
    assert created["resolved"]["basics"]["contingency_pct"] == "20"
    # Optional field with an engine default must never block confirmation.
    assert created["resolved"]["confirmed"] is True
    assert not any(
        notice["field"] == "contingency_pct"
        for notice in created["resolved"]["notices"]
    )
    assert created["resolved"]["sources"].get("contingency_pct") == "user_field"

    run = client.post("/run", json={"casefile_id": event_id})
    assert run.status_code == 200, run.text
    budget = run.json()["budget_summary"]

    assert Decimal(str(budget["contingency_pct"])) == Decimal("20")

    cap = Decimal(str(budget["budget_cap"]))
    reserve = Decimal(str(budget["contingency_reserve"]))
    spendable = Decimal(str(budget["spendable"]))

    # Reserve is exactly 20% of the cap.
    assert reserve == (cap * Decimal("0.20")).quantize(Decimal("0.01"))
    # Deterministic-core zero-sum invariant.
    assert cap - reserve - spendable == Decimal("0")


def test_missing_contingency_pct_defaults_to_15(client: TestClient) -> None:
    event_id = _create(client, contingency_pct=None)

    created = client.get(f"/casefiles/{event_id}").json()
    assert created["resolved"]["basics"]["contingency_pct"] is None
    # No source entry is recorded when the value is unset.
    assert "contingency_pct" not in created["resolved"]["sources"]

    run = client.post("/run", json={"casefile_id": event_id})
    assert run.status_code == 200, run.text
    budget = run.json()["budget_summary"]
    assert Decimal(str(budget["contingency_pct"])) == Decimal("15")

    cap = Decimal(str(budget["budget_cap"]))
    reserve = Decimal(str(budget["contingency_reserve"]))
    spendable = Decimal(str(budget["spendable"]))
    assert reserve == (cap * Decimal("0.15")).quantize(Decimal("0.01"))
    assert cap - reserve - spendable == Decimal("0")


def test_patch_contingency_pct_above_100_is_rejected(client: TestClient) -> None:
    event_id = _create(client)
    response = client.patch(
        f"/casefiles/{event_id}/basics",
        json=_basics(contingency_pct="150"),
    )
    assert response.status_code == 422


def test_patch_negative_contingency_pct_is_rejected(client: TestClient) -> None:
    event_id = _create(client)
    response = client.patch(
        f"/casefiles/{event_id}/basics",
        json=_basics(contingency_pct="-5"),
    )
    assert response.status_code == 422


def test_contingency_pct_persists_across_reload(client: TestClient) -> None:
    event_id = _create(client, contingency_pct="25")

    reloaded = client.get(f"/casefiles/{event_id}")
    assert reloaded.status_code == 200
    assert reloaded.json()["resolved"]["basics"]["contingency_pct"] == "25"
    assert reloaded.json()["basics"]["contingency_pct"] == "25"
