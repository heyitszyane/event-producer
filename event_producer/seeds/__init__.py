"""Committed demo casefiles so a fresh clone has reference events.

Casefiles live under ``.local_state`` (gitignored), so a clean checkout has
no data to explore. These seed specs are checked into the repo and
materialized on demand via ``ensure_demo_casefiles`` (exposed by the
``POST /casefiles/seed`` endpoint and the "Seed Demo" button). Seeding is
idempotent: an existing seed is left untouched so user edits survive.
One narrow exception is the recorded Singapore seed title migration: the prior
committed title is upgraded in place only when the local seed still has that
exact old title.

The two seeds intentionally cover different currencies and a different mix of
constraints:

- ``seed-la-product-launch`` — a USD brand product launch in Los Angeles with
  a comfortable brief that matches its basics (a clean happy-path demo).
- ``seed-sg-networking`` — an SGD founder networking night in Singapore whose
  brief includes a realistic 50-80 attendee planning tension against the saved
  100-pax target, so the requirement-provenance and advisory-warning surfaces
  have something real to show.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, TypedDict

from event_producer.models.schemas import EventBasics

if TYPE_CHECKING:
    from event_producer.main import EventProducerApp


class SeedSpec(TypedDict):
    event_id: str
    basics: EventBasics
    brief: str


SINGAPORE_SEED_ID = "seed-sg-networking"
LEGACY_SINGAPORE_TITLE = "AI Founder Networking Night"


SEED_CASEFILES: list[SeedSpec] = [
    {
        "event_id": "seed-la-product-launch",
        "basics": EventBasics(
            working_title="Aurora Wearables LA Launch",
            country="United States",
            city="Los Angeles",
            currency="USD",
            budget_cap=Decimal("40000"),
            contingency_pct=Decimal("12"),
            start_date="2026-09-24",
            end_date="2026-09-24",
            expected_turnout=120,
            event_type="product_launch",
        ),
        "brief": (
            "Evening press and creator launch for Aurora, a new wearable, in Los "
            "Angeles. Around 120 guests: tech press, retail partners, and lifestyle "
            "creators. Budget is about USD 40,000. We need a design-forward venue, a "
            "short keynote with live product reveal, a few hands-on demo stations, "
            "light catering and a bar, and strong photo and video moments for social. "
            "Doors 6:30pm, keynote 7:15pm. It should feel premium and brand-ready, not "
            "corporate. Date 24 Sep 2026. Media check-in and a press kit table are "
            "important."
        ),
    },
    {
        "event_id": SINGAPORE_SEED_ID,
        "basics": EventBasics(
            working_title="Singapore AI Founder Networking Night",
            country="Singapore",
            city="Singapore",
            currency="SGD",
            budget_cap=Decimal("10000"),
            contingency_pct=Decimal("10"),
            start_date="2026-08-14",
            end_date="2026-08-14",
            expected_turnout=100,
            event_type="networking",
        ),
        "brief": (
            "We need something for AI founders / builders in Singapore. Maybe 80 people? "
            "Actually could be 50 if budget is tight but ideally enough density. Evening "
            "event, not too formal, want it to feel premium but not like a hotel ballroom "
            "conference.\n"
            "Budget is around $10,000 SGD all-in if possible. Need venue, some drinks, "
            "maybe light canapes, basic AV for a few 5-min demos. No full dinner. Good "
            "photos would be useful. It should feel like a curated invite-only founder "
            "salon.\n"
            "Date: Friday 14 Aug 2026. Maybe CBD or somewhere central. Please avoid "
            "anything that looks like a generic corporate seminar."
        ),
    },
]


def _sync_existing_singapore_seed(
    producer: EventProducerApp,
    spec: SeedSpec,
) -> None:
    """Upgrade the stable recording seed to the current committed brief."""
    store = producer.casefile_store
    casefile = store.get_casefile(SINGAPORE_SEED_ID)
    if casefile.basics != spec["basics"]:
        store.update_basics(SINGAPORE_SEED_ID, spec["basics"])
    if casefile.brief != spec["brief"]:
        store.update_brief(SINGAPORE_SEED_ID, spec["brief"])
    refreshed = store.get_casefile(SINGAPORE_SEED_ID)
    if refreshed.basics == spec["basics"] and refreshed.brief == spec["brief"]:
        if "run-snapshot" not in refreshed.artifacts:
            producer.run_casefile(SINGAPORE_SEED_ID)
        else:
            try:
                snapshot = store.read_artifact(SINGAPORE_SEED_ID, "run-snapshot")
            except FileNotFoundError:
                snapshot = None
            event_title = (
                snapshot.get("event_spec", {}).get("name")
                if isinstance(snapshot, dict)
                else None
            )
            if event_title != spec["basics"].working_title:
                producer.run_casefile(SINGAPORE_SEED_ID)


def ensure_demo_casefiles(producer: EventProducerApp) -> list[str]:
    """Create and run the seed casefiles if they are not already present.

    Returns the list of seed event ids (existing or newly created), in the
    order they should be offered to the user. Idempotent: an already-seeded
    casefile is left as-is so any edits the user made survive re-seeding.
    """
    store = producer.casefile_store
    existing = {summary.event_id for summary in store.list_casefiles()}
    seeded_ids: list[str] = []

    for spec in SEED_CASEFILES:
        event_id = spec["event_id"]
        seeded_ids.append(event_id)
        if event_id in existing:
            if event_id == SINGAPORE_SEED_ID:
                _sync_existing_singapore_seed(producer, spec)
            continue
        store.create_casefile(spec["basics"], spec["brief"], event_id=event_id)
        try:
            # Populate scope, budget, schedule, and vendor draft so the seed is
            # immediately explorable. The pipeline is deterministic (rule-based),
            # so this needs no live model.
            producer.run_casefile(event_id)
        except Exception:  # pragma: no cover - seed stays usable as a draft
            # A failed first pass must not break seeding; the casefile still
            # exists and can be regenerated from the Brief Intake page.
            pass

    return seeded_ids
