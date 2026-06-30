"""P7D tests for constraint override semantics.

These tests verify that:
1. Brief extraction is primary (not silently overridden by defaults)
2. Manual constraints are blank by default
3. Manual override source is tracked correctly
"""

import pytest
from decimal import Decimal

from event_producer.main import EventProducerApp
from event_producer.models.schemas import BriefIntakeSourceMap


class TestConstraintOverrideSemantics:
    """Verify brief is primary and manual overrides are explicit."""

    def test_brief_attendees_used_when_no_manual_override(self):
        """Given a brief says 'Expected turnout 100 pax' and attendees is absent,
        Then the EventSpec attendees is the extracted value, not a default.
        """
        app = EventProducerApp()
        result = app.run_event(
            brief="1 night AI industry networking event with 100 pax expected turnout, $10000 budget.",
            # Note: no attendees parameter passed (manual override)
        )

        # The brief_intake should have extracted 100 attendees
        intake = result.get("brief_intake", {})
        assert intake.get("attendees") == 100

        # The source_map should show brief_extracted for attendees
        source_map = BriefIntakeSourceMap(**intake.get("source_map", {}))
        assert source_map.attendees == "brief_extracted"

    def test_manual_override_takes_precedence(self):
        """Given a brief says 100 pax but user explicitly overrides to 50,
        Then the normalized value uses 50 and source is manual_override.
        """
        app = EventProducerApp()
        result = app.run_event(
            brief="Event with 100 attendees expected.",
            attendees=50,  # Explicit manual override
        )

        intake = result.get("brief_intake", {})
        source_map = BriefIntakeSourceMap(**intake.get("source_map", {}))

        # Source should be manual_override, not brief_extracted
        assert source_map.attendees == "manual_override"

    def test_manual_budget_cap_overrides_brief(self):
        """Given a brief mentions budget but user provides explicit cap,
        Then manual override takes precedence.
        """
        app = EventProducerApp()
        result = app.run_event(
            brief="Event with $5000 budget mentioned.",
            budget_cap="15000",  # User override
        )

        intake = result.get("brief_intake", {})
        source_map = BriefIntakeSourceMap(**intake.get("source_map", {}))

        assert source_map.budget_cap == "manual_override"

    def test_fallback_default_marked_correctly(self):
        """Given a brief with no budget info,
        When no manual override is provided,
        Then source shows fallback_default for the engine-required value.
        """
        app = EventProducerApp()
        result = app.run_event(
            brief="Just an event with no budget mentioned.",
            # No budget_cap provided
        )

        intake = result.get("brief_intake", {})
        source_map = BriefIntakeSourceMap(**intake.get("source_map", {}))

        # budget_cap should be fallback since brief didn't mention it
        assert source_map.budget_cap == "fallback_default"


class TestBudgetRealismWarnings:
    """P7D tests for budget realism heuristics."""

    def test_singapore_open_bar_warning(self):
        """Given Singapore, open bar, 100 pax, budget <= 10000,
        Then a budget realism warning is emitted.
        """
        app = EventProducerApp()
        result = app.run_event(
            brief="Event in Singapore with 100 pax and open bar, $10000 budget.",
        )

        intake = result.get("brief_intake", {})
        warnings = intake.get("market_realism_warnings", [])

        # Should have warning about Singapore open bar scenario
        assert any("Singapore" in w and "open bar" in w.lower() for w in warnings)

    def test_no_warning_for_realistic_budget(self):
        """Given a lower-risk scenario,
        Then no severe open-bar warning is emitted.
        """
        app = EventProducerApp()
        result = app.run_event(
            brief="Small 30-pax networking event with light catering.",
        )

        intake = result.get("brief_intake", {})
        warnings = intake.get("market_realism_warnings", [])

        # Should not have Singapore open-bar warning
        assert not any("Singapore" in w and "open bar" in w.lower() for w in warnings)


class TestProvenanceDisplay:
    """P7D tests for requirement provenance in UI-ready responses."""

    def test_source_map_included_in_response(self):
        """The brief intake response includes source_map for provenance display."""
        app = EventProducerApp()
        result = app.run_event(
            brief="Networking event in Singapore, 100 pax, $10000 budget.",
        )

        intake = result.get("brief_intake", {})
        assert "source_map" in intake

        source_map = intake["source_map"]
        assert "attendees" in source_map
        assert "budget_cap" in source_map
        assert "date" in source_map