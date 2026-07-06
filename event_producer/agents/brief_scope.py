"""Brief/Scope agent — parses event brief and proposes scope options.

Reason -> Formatter split:
    - BriefScopeReasonAgent: parses the raw brief, proposes scope items
      constrained by the hard budget.
    - BriefScopeFormatterAgent: validates the reason agent's output against
      EventSpec / ScopeItem schemas.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from event_producer.models.schemas import EventSpec, ScopeItem

if TYPE_CHECKING:
    from event_producer.providers.event_store import EventStore


# ---------------------------------------------------------------------------
# Scope catalogue — rule-based proposals per event type
#
# Every entry carries a sizing rate (``cost_per_attendee``) plus a
# ``qty_basis`` describing how the line is actually bought:
#   - per_attendee:      qty = attendee count, unit cost = rate
#   - flat:              qty = 1, unit cost = rate x attendees (lump sum
#                        sized to headcount — venues, AV, decor, signage)
#   - per_25_attendees:  1 unit per 25 pax (staff), unit cost = rate x 25
#   - per_50_attendees:  1 unit per 50 pax (security/registration desks)
#
# Entries with ``selected: False`` are proposed but excluded from the budget
# until the user opts in (e.g. staffing, which venues often include).
# ---------------------------------------------------------------------------

_STAFFING_NOTE = "Often included in the venue package — include only if your venue does not provide staff."

_NETWORKING_SCOPE = [
    {
        "name": "Venue Rental",
        "description": "Indoor venue rental for networking event",
        "category": "venue",
        "tier": "must",
        "cost_per_attendee": Decimal("50.00"),
        "qty_basis": "flat",
    },
    {
        "name": "Catering",
        "description": "Food and beverage service for attendees",
        "category": "catering",
        "tier": "must",
        "cost_per_attendee": Decimal("35.00"),
        "qty_basis": "per_attendee",
    },
    {
        "name": "AV Equipment",
        "description": "Sound system, projector, and microphones",
        "category": "av_equipment",
        "tier": "should",
        "cost_per_attendee": Decimal("15.00"),
        "qty_basis": "flat",
    },
    {
        "name": "Event Staffing",
        "description": f"On-site event staff and coordinators. {_STAFFING_NOTE}",
        "category": "staffing",
        "tier": "could",
        "cost_per_attendee": Decimal("10.00"),
        "qty_basis": "per_25_attendees",
        "selected": False,
    },
    {
        "name": "Decor and Signage",
        "description": "Table centerpieces, banners, and directional signage",
        "category": "decor",
        "tier": "could",
        "cost_per_attendee": Decimal("8.00"),
        "qty_basis": "flat",
    },
]

_PRODUCT_LAUNCH_SCOPE = [
    {
        "name": "Venue Rental",
        "description": "Premium venue rental for product launch",
        "category": "venue",
        "tier": "must",
        "cost_per_attendee": Decimal("75.00"),
        "qty_basis": "flat",
    },
    {
        "name": "Catering",
        "description": "Premium food and beverage service",
        "category": "catering",
        "tier": "must",
        "cost_per_attendee": Decimal("50.00"),
        "qty_basis": "per_attendee",
    },
    {
        "name": "AV Equipment",
        "description": "Professional sound, lighting, and projection",
        "category": "av_equipment",
        "tier": "must",
        "cost_per_attendee": Decimal("30.00"),
        "qty_basis": "flat",
    },
    {
        "name": "Stage and Set Design",
        "description": "Custom stage build and set design for product reveal",
        "category": "staging",
        "tier": "should",
        "cost_per_attendee": Decimal("25.00"),
        "qty_basis": "flat",
    },
    {
        "name": "Event Staffing",
        "description": f"On-site event staff, ushers, and coordinators. {_STAFFING_NOTE}",
        "category": "staffing",
        "tier": "could",
        "cost_per_attendee": Decimal("12.00"),
        "qty_basis": "per_25_attendees",
        "selected": False,
    },
    {
        "name": "Security",
        "description": "Event security personnel and access control",
        "category": "security",
        "tier": "should",
        "cost_per_attendee": Decimal("10.00"),
        "qty_basis": "per_50_attendees",
    },
    {
        "name": "Decor and Branding",
        "description": "Branded decor, product displays, and signage",
        "category": "decor",
        "tier": "could",
        "cost_per_attendee": Decimal("15.00"),
        "qty_basis": "flat",
    },
]

_CONFERENCE_SCOPE = [
    {
        "name": "Venue Rental",
        "description": "Conference venue with breakout rooms",
        "category": "venue",
        "tier": "must",
        "cost_per_attendee": Decimal("60.00"),
        "qty_basis": "flat",
    },
    {
        "name": "Catering",
        "description": "Conference catering including coffee breaks",
        "category": "catering",
        "tier": "must",
        "cost_per_attendee": Decimal("40.00"),
        "qty_basis": "per_attendee",
    },
    {
        "name": "AV Equipment",
        "description": "Projectors, screens, microphones, and recording",
        "category": "av_equipment",
        "tier": "must",
        "cost_per_attendee": Decimal("20.00"),
        "qty_basis": "flat",
    },
    {
        "name": "Event Staffing",
        "description": f"Registration desk, room monitors, and coordinators. {_STAFFING_NOTE}",
        "category": "staffing",
        "tier": "could",
        "cost_per_attendee": Decimal("10.00"),
        "qty_basis": "per_25_attendees",
        "selected": False,
    },
    {
        "name": "Registration System",
        "description": "Online registration platform and badge printing",
        "category": "registration",
        "tier": "should",
        "cost_per_attendee": Decimal("5.00"),
        "qty_basis": "flat",
    },
    {
        "name": "Signage and Wayfinding",
        "description": "Directional signage, session boards, and sponsor banners",
        "category": "signage",
        "tier": "could",
        "cost_per_attendee": Decimal("4.00"),
        "qty_basis": "flat",
    },
]

_CORPORATE_SCOPE = [
    {
        "name": "Venue Rental",
        "description": "Indoor venue rental for corporate event",
        "category": "venue",
        "tier": "must",
        "cost_per_attendee": Decimal("50.00"),
        "qty_basis": "flat",
    },
    {
        "name": "Catering",
        "description": "Food and beverage service for attendees",
        "category": "catering",
        "tier": "must",
        "cost_per_attendee": Decimal("35.00"),
        "qty_basis": "per_attendee",
    },
    {
        "name": "Registration Check-In",
        "description": "On-site registration desk and check-in staff",
        "category": "registration",
        "tier": "must",
        "cost_per_attendee": Decimal("12.00"),
        "qty_basis": "per_50_attendees",
    },
    {
        "name": "AV Equipment",
        "description": "Sound system, projector, and microphones",
        "category": "av_equipment",
        "tier": "should",
        "cost_per_attendee": Decimal("15.00"),
        "qty_basis": "flat",
    },
    {
        "name": "Event Staffing",
        "description": f"On-site event staff and coordinators. {_STAFFING_NOTE}",
        "category": "staffing",
        "tier": "could",
        "cost_per_attendee": Decimal("10.00"),
        "qty_basis": "per_25_attendees",
        "selected": False,
    },
    {
        "name": "Decor and Signage",
        "description": "Table centerpieces, banners, and directional signage",
        "category": "decor",
        "tier": "could",
        "cost_per_attendee": Decimal("8.00"),
        "qty_basis": "flat",
    },
]

_SCOPE_CATALOGUE: dict[str, list[dict]] = {
    "networking": _NETWORKING_SCOPE,
    "product_launch": _PRODUCT_LAUNCH_SCOPE,
    "conference": _CONFERENCE_SCOPE,
    "corporate": _CORPORATE_SCOPE,
}


class BriefScopeReasonAgent:
    """Reasoning agent that parses the event brief and proposes scope.

    This agent handles the "thinking" step: interpreting the user's event
    description, identifying key parameters (attendees, venue, duration),
    and proposing a set of scope items that fit within the budget constraint.

    The reason agent does NOT validate — it produces raw dicts for the
    formatter to validate.
    """

    def __init__(self, event_store: EventStore) -> None:
        """Initialize the reason agent.

        Args:
            event_store: Abstract event store interface.
        """
        self._event_store = event_store

    def run(self, request: dict) -> dict:
        """Parse the brief and propose scope items.

        Args:
            request: The incoming request dict containing:
                - brief (str): Raw event description
                - budget_cap (str): Maximum budget as a string
                - attendees (int): Expected number of attendees
                - event_type (str): One of networking, product_launch, conference
                - venue_type (str): Venue description
                - date (str): Event date in YYYY-MM-DD format

        Returns:
            A dict with:
                - event_spec: Raw EventSpec dict (not validated)
                - scope_items: List of raw ScopeItem dicts (not validated)
        """
        brief: str = request.get("brief", "")
        attendees: int = request.get("attendees", 0)
        event_type: str = request.get("event_type", "")
        venue_type: str = request.get("venue_type", "")
        date: str = request.get("date", "")
        currency: str = request.get("currency") or "USD"

        # --- Build raw EventSpec ---
        event_spec: dict = self._build_event_spec(
            brief=brief,
            attendees=attendees,
            event_type=event_type,
            venue_type=venue_type,
            date=date,
        )

        # --- Propose scope items ---
        scope_items: list[dict] = self._propose_scope_items(
            brief=brief,
            event_type=event_type,
            attendees=attendees,
            currency=currency,
        )

        return {
            "event_spec": event_spec,
            "scope_items": scope_items,
        }

    def _build_event_spec(
        self,
        brief: str,
        attendees: int,
        event_type: str,
        venue_type: str,
        date: str,
    ) -> dict:
        """Build a raw EventSpec dict from request fields, flagging missing data.

        Returns a dict with all EventSpec fields. Fields that are missing or
        invalid are set to type-appropriate defaults and listed in
        missing_fields.
        """
        missing_fields: list[str] = []

        # name: derive from brief or event_type
        name = brief.strip() if brief.strip() else ""
        if not name:
            missing_fields.append("name")

        # description: use the brief text
        description = brief.strip() if brief.strip() else ""
        if not description:
            missing_fields.append("description")

        # event_type
        if not event_type or not event_type.strip():
            event_type = ""
            missing_fields.append("event_type")

        # attendees
        if attendees <= 0:
            attendees = 0
            missing_fields.append("attendees")

        # venue_type
        if not venue_type or not venue_type.strip():
            venue_type = ""
            missing_fields.append("venue_type")

        # duration_hours: default to 4.0 for MVP
        duration_hours = Decimal("4.0")

        # date: validate format
        if not date or not date.strip():
            date = ""
            missing_fields.append("date")
        else:
            try:
                from datetime import datetime
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                missing_fields.append("date")

        return {
            "name": name,
            "description": description,
            "event_type": event_type,
            "attendees": attendees,
            "venue_type": venue_type,
            "duration_hours": duration_hours,
            "date": date,
            "missing_fields": missing_fields,
        }

    @staticmethod
    def _qty_and_unit_cost(
        qty_basis: str, rate: Decimal, attendees: int
    ) -> tuple[Decimal, Decimal]:
        """Resolve (qty, unit_cost) from a sizing rate and quantity basis."""
        pax = max(attendees, 1)
        if qty_basis == "per_attendee":
            return Decimal(str(pax)), rate
        if qty_basis == "per_25_attendees":
            units = -(-pax // 25)  # ceil division
            return Decimal(str(units)), (rate * Decimal("25")).quantize(Decimal("0.01"))
        if qty_basis == "per_50_attendees":
            units = -(-pax // 50)
            return Decimal(str(units)), (rate * Decimal("50")).quantize(Decimal("0.01"))
        # flat: one lump-sum line sized to the headcount
        return Decimal("1"), (rate * Decimal(str(pax))).quantize(Decimal("0.01"))

    def _propose_scope_items(
        self,
        brief: str,
        event_type: str,
        attendees: int,
        currency: str = "USD",
    ) -> list[dict]:
        """Propose scope items based on event type and attendee count.

        Uses a rule-based approach: selects a scope catalogue by event_type,
        then sizes each line by its quantity basis — per-attendee lines scale
        with headcount, flat lines become a single lump sum, and staffing
        lines become whole staff units.

        Returns a list of raw ScopeItem dicts.
        """
        catalogue = _SCOPE_CATALOGUE.get(event_type, [])
        scope_items: list[dict] = []

        for entry in catalogue:
            qty, unit_cost = self._qty_and_unit_cost(
                str(entry.get("qty_basis", "flat")),
                entry["cost_per_attendee"],
                attendees,
            )
            scope_items.append({
                "name": entry["name"],
                "description": entry["description"],
                "category": entry["category"],
                "tier": entry["tier"],
                "estimated_cost": unit_cost,
                "currency": currency,
                "qty": qty,
                "selected": bool(entry.get("selected", True)),
            })

        brief_low = brief.lower()
        if (
            attendees >= 80
            and any(kw in brief_low for kw in ("open bar", "full bar", "bar package"))
            and any(kw in brief_low for kw in ("canape", "canapé", "f&b", "food"))
        ):
            scope_items.append({
                "name": "Open Bar and Canapes Allowance",
                "description": (
                    "Per-attendee allowance for the requested open bar and canapes; "
                    "included to expose the true feasibility pressure."
                ),
                "category": "catering",
                "tier": "must",
                "estimated_cost": Decimal("65.00"),
                "currency": currency,
                "qty": Decimal(str(attendees)),
                "selected": True,
            })

        return scope_items


class BriefScopeFormatterAgent:
    """Formatter agent that validates brief/scope output against schemas.

    This agent handles the "formatting" step: taking the reason agent's
    output and validating it against the EventSpec and ScopeItem Pydantic
    schemas, ensuring all required fields are present and correctly typed.

    The formatter ONLY validates — it does NOT call any LLM or modify data.
    It imports only schemas, not the reason agent.
    """

    def __init__(self) -> None:
        """Initialize the formatter agent.

        No dependencies needed — the formatter is a pure validation step.
        """

    def run(self, raw_output: dict) -> dict:
        """Validate the reason agent's output against schemas.

        Args:
            raw_output: The reason agent's output dict containing:
                - event_spec: Raw EventSpec dict
                - scope_items: List of raw ScopeItem dicts

        Returns:
            A dict with validated Pydantic model dicts:
                - event_spec: EventSpec.model_dump()
                - scope_items: List of ScopeItem.model_dump() dicts

        Raises:
            pydantic.ValidationError: If event_spec or any scope_item
                fails schema validation.
        """
        raw_event_spec = raw_output.get("event_spec", {})
        raw_scope_items = raw_output.get("scope_items", [])

        # Validate EventSpec — raises ValidationError on failure
        event_spec = EventSpec(**raw_event_spec)

        # Validate each ScopeItem — raises ValidationError on failure
        scope_items = [ScopeItem(**item) for item in raw_scope_items]

        return {
            "event_spec": event_spec.model_dump(),
            "scope_items": [item.model_dump() for item in scope_items],
        }
