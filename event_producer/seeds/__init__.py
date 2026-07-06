"""Committed demo casefiles so a fresh clone has reference events.

Casefiles live under ``.local_state`` (gitignored), so a clean checkout has
no data to explore. These seed specs are checked into the repo and
materialized on demand via ``ensure_demo_casefiles`` (exposed by the
``POST /casefiles/seed`` endpoint and the "Seed Demo" button). Seeding is
idempotent: an existing seed is left untouched so user edits survive.

The two seeds intentionally cover different currencies and a different mix of
constraints:

- ``seed-la-product-launch`` — a USD brand product launch in Los Angeles with
  a comfortable brief that matches its basics (a clean happy-path demo).
- ``seed-sg-networking`` — an SGD founder networking night in Singapore whose
  brief disagrees with the saved headcount, so the requirement-provenance and
  conflict-detection surfaces have something real to show.
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
        "event_id": "seed-sg-networking",
        "basics": EventBasics(
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
        ),
        "brief": (
            "AI founder networking night in Singapore. Expecting around 60 guests: "
            "founders, investors, and AI builders. Budget is around SGD 10,000. Want it "
            "to feel premium but not flashy: light F&B, a short fireside chat, and a few "
            "structured networking prompts. No full conference setup. Evening event on "
            "14 Aug 2026, roughly 6:30pm to 9:30pm. Good venue acoustics matter for the "
            "fireside segment."
        ),
    },
]


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
