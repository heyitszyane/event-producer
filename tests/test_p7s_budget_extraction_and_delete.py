"""P7S — budget extraction hygiene + casefile deletion.

Two post-P7R fixes surfaced during the pre-recording review:

1. The brief budget regex misread a soft quantifier ("around 60 guests") as a
   budget of 60, producing a bogus "budget of 60" conflict notice. A budget
   amount must now be anchored to an explicit money signal (the word "budget",
   a currency symbol, or a currency code).
2. A casefile can now be deleted from disk via ``DELETE /casefiles/{id}``.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from event_producer.api import create_app
from event_producer.models.schemas import EventBasics
from event_producer.storage.local_casefiles import (
    _extract_budget_cap,
    resolve_event_state,
)


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


# --- 1. Budget extraction hygiene --------------------------------------------


def test_soft_quantifier_before_headcount_is_not_a_budget() -> None:
    # "around 60 guests" must NOT be read as a budget of 60.
    assert _extract_budget_cap("Expecting around 60 guests.") is None


def test_headcount_noun_disqualifies_the_number() -> None:
    assert _extract_budget_cap("budget for 60 guests only") is None


@pytest.mark.parametrize(
    "brief, expected",
    [
        ("Budget is around SGD 10,000.", Decimal("10000")),
        ("Budget is around 20k.", Decimal("20000")),
        ("Product launch. Budget $40k.", Decimal("40000")),
        ("We can spend USD 25,000 for the night.", Decimal("25000")),
        ("Budget: 40000 for the gala.", Decimal("40000")),
        ("Around 120 guests. Budget is 1.5m.", Decimal("1500000")),
    ],
)
def test_anchored_budget_amounts_extract_cleanly(
    brief: str, expected: Decimal
) -> None:
    assert _extract_budget_cap(brief) == expected


def test_seed_style_brief_conflicts_on_pax_not_budget() -> None:
    """The SG seed brief says 'around 60 guests' + 'Budget is around SGD 10,000'.

    With the saved casefile at 80 pax / 10,000 budget the only conflict must be
    on the headcount; the budget must reconcile (no phantom 'budget of 60').
    """
    basics = EventBasics(
        working_title="AI Founder Networking Night",
        country="Singapore",
        city="Singapore",
        currency="SGD",
        budget_cap=Decimal("10000"),
        contingency_pct=Decimal("10"),
        start_date="2026-08-14",
        end_date="2026-08-14",
        expected_turnout=80,
        event_type="networking",
    )
    brief = (
        "AI founder networking night in Singapore. Expecting around 60 guests: "
        "founders, investors, and AI builders. Budget is around SGD 10,000."
    )
    state = resolve_event_state(basics, brief)
    conflict_fields = {n.field for n in state.notices if n.type == "conflict"}
    assert "budget_cap" not in conflict_fields
    assert "expected_turnout" in conflict_fields


def test_saved_budget_is_authoritative_even_when_brief_differs() -> None:
    """Option A: the structured Budget Cap field is fill-only truth. Even a brief
    that plainly states a *different* budget must NOT raise a conflict notice —
    free-text money is too brittle to contradict an explicit field. (Pax, which
    is noun-anchored and reliable, still cross-checks — asserted above.)"""
    basics = EventBasics(
        working_title="Gala",
        country="Singapore",
        city="Singapore",
        currency="SGD",
        budget_cap=Decimal("10000"),
        expected_turnout=80,
        event_type="gala",
    )
    brief = "Fundraising gala. Budget is around SGD 25,000."
    state = resolve_event_state(basics, brief)
    assert state.basics.budget_cap == Decimal("10000")
    assert not any(
        n.field == "budget_cap" and n.type == "conflict" for n in state.notices
    )


def test_blank_budget_is_still_filled_from_brief() -> None:
    """Fill-only still fills: a blank Budget Cap is populated from the brief."""
    basics = EventBasics(
        working_title="Gala",
        country="Singapore",
        city="Singapore",
        currency="SGD",
        budget_cap=None,
        expected_turnout=80,
        event_type="gala",
    )
    state = resolve_event_state(basics, "Budget is about SGD 30,000.")
    assert state.basics.budget_cap == Decimal("30000")
    assert state.sources.get("budget_cap") == "brief_extracted"


# --- 2. Casefile deletion -----------------------------------------------------


def _create(client: TestClient) -> str:
    payload = {
        "basics": {
            "working_title": "Deletable Event",
            "country": "Singapore",
            "city": "Singapore",
            "currency": "SGD",
            "budget_cap": "10000",
            "start_date": "2026-07-10",
            "end_date": "2026-07-10",
            "expected_turnout": 80,
            "event_type": "networking",
        },
        "brief": "Notes.",
    }
    return client.post("/casefiles", json=payload).json()["event_id"]


def test_delete_casefile_removes_it(client: TestClient) -> None:
    event_id = _create(client)
    assert client.get(f"/casefiles/{event_id}").status_code == 200

    deleted = client.delete(f"/casefiles/{event_id}")
    assert deleted.status_code == 200
    assert deleted.json() == {"event_id": event_id, "deleted": True}

    assert client.get(f"/casefiles/{event_id}").status_code == 404
    listed = {row["event_id"] for row in client.get("/casefiles").json()}
    assert event_id not in listed


def test_delete_missing_casefile_returns_404(client: TestClient) -> None:
    assert client.delete("/casefiles/does-not-exist").status_code == 404


def test_deleted_seed_can_be_reseeded(client: TestClient) -> None:
    seeded = client.post("/casefiles/seed").json()["seeded_ids"]
    victim = seeded[0]
    assert client.delete(f"/casefiles/{victim}").status_code == 200
    assert client.get(f"/casefiles/{victim}").status_code == 404

    reseeded = client.post("/casefiles/seed").json()["seeded_ids"]
    assert victim in reseeded
    assert client.get(f"/casefiles/{victim}").status_code == 200
