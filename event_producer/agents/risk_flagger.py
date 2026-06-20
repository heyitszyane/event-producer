"""Risk/Gap Flagger agent — inspects full event state and produces RiskFlag[].

This is a single agent with no reason/formatter split. It reads the
complete event state (budget, schedule, vendors, scope) and produces
a list of risks or gaps that need human attention.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from event_producer.security.injection_flag import is_flagged as has_injection_flags

if TYPE_CHECKING:
    from event_producer.providers.event_store import EventStore


# Required vendor categories for a complete event
_REQUIRED_VENDOR_CATEGORIES = ["venue", "catering", "av"]


class RiskFlaggerAgent:
    """Inspects full event state and produces a list of risk flags.

    This agent has no reason/formatter split. It reads the entire event
    state from the event store and produces a deterministic list of
    RiskFlag dicts covering budget, schedule, vendor, security,
    coverage, and compliance risks.
    """

    def __init__(self, event_store: EventStore) -> None:
        """Initialize the risk flagger agent.

        Args:
            event_store: Abstract event store interface for reading
                full event state.
        """
        self._event_store = event_store

    def run(self, state: dict) -> list[dict]:
        """Inspect event state and produce risk flags.

        Args:
            state: The full event state dict containing:
                - event_spec: dict
                - budget_summary: dict
                - schedule_result: dict or None
                - conflict_report: dict or None
                - vendors: list of dicts
                - vendor_messages: list of dicts

        Returns:
            A list of RiskFlag dicts identified from the state.
        """
        flags: list[dict] = []

        budget_summary: dict = state.get("budget_summary", {})
        conflict_report: dict | None = state.get("conflict_report")
        vendors: list[dict] = state.get("vendors", [])
        vendor_messages: list[dict] = state.get("vendor_messages", [])

        flags.extend(self._check_budget(budget_summary))
        flags.extend(self._check_schedule(conflict_report))
        flags.extend(self._check_vendor_coverage(vendors))
        flags.extend(self._check_injections(vendor_messages))

        return flags

    def _check_budget(self, budget_summary: dict) -> list[dict]:
        """Check budget for overrun and low headroom risks."""
        flags: list[dict] = []

        if not budget_summary:
            return flags

        # Check 1: Budget overrun
        if budget_summary.get("over_budget", False):
            flags.append(self._make_flag(
                category="budget",
                severity="critical",
                message="Budget overrun: included totals exceed spendable",
            ))

        # Check 2: Low headroom (< 10% of spendable)
        headroom = budget_summary.get("headroom", 0)
        spendable = budget_summary.get("spendable", 0)
        if spendable and headroom is not None:
            try:
                headroom_val = float(headroom)
                spendable_val = float(spendable)
                if spendable_val > 0 and (headroom_val / spendable_val) < 0.10:
                    flags.append(self._make_flag(
                        category="budget",
                        severity="warning",
                        message="Low headroom",
                    ))
            except (TypeError, ValueError, ZeroDivisionError):
                pass

        return flags

    def _check_schedule(self, conflict_report: dict | None) -> list[dict]:
        """Check schedule for conflicts, cycles, and lead time violations."""
        flags: list[dict] = []

        if conflict_report is None:
            return flags

        # Check 3: Schedule conflict (any conflict report present)
        has_any_conflicts = (
            conflict_report.get("lead_time_conflicts")
            or conflict_report.get("anchor_conflicts")
            or conflict_report.get("cycle")
        )
        if has_any_conflicts:
            flags.append(self._make_flag(
                category="schedule",
                severity="critical",
                message="Schedule conflicts detected",
            ))

        # Check 4: Cycle detected
        cycle = conflict_report.get("cycle", [])
        if cycle:
            flags.append(self._make_flag(
                category="schedule",
                severity="critical",
                message="Dependency cycle detected",
                related_items=list(cycle),
            ))

        # Check 7: Lead time violations
        lead_time_conflicts = conflict_report.get("lead_time_conflicts", [])
        if lead_time_conflicts:
            related = [
                c.get("task_id", "")
                for c in lead_time_conflicts
                if c.get("task_id")
            ]
            flags.append(self._make_flag(
                category="schedule",
                severity="warning",
                message="Lead time violations detected",
                related_items=related,
            ))

        return flags

    def _check_vendor_coverage(self, vendors: list[dict]) -> list[dict]:
        """Check that all required vendor categories are covered."""
        flags: list[dict] = []

        if not vendors:
            # No vendors at all means all required categories are missing
            for category in _REQUIRED_VENDOR_CATEGORIES:
                flags.append(self._make_flag(
                    category="vendor",
                    severity="warning",
                    message=f"No vendor for category {category}",
                ))
            return flags

        covered_categories = {v.get("category", "").lower() for v in vendors}
        for category in _REQUIRED_VENDOR_CATEGORIES:
            if category not in covered_categories:
                flags.append(self._make_flag(
                    category="vendor",
                    severity="warning",
                    message=f"No vendor for category {category}",
                ))

        return flags

    def _check_injections(self, vendor_messages: list[dict]) -> list[dict]:
        """Check vendor messages for injection attempts."""
        flags: list[dict] = []

        for msg in vendor_messages:
            body = msg.get("body", "")
            if body:
                from event_producer.security.injection_flag import check
                injection_flags = check(body)
                if has_injection_flags(injection_flags):
                    flags.append(self._make_flag(
                        category="security",
                        severity="critical",
                        message="Potential injection in vendor message",
                    ))
                    # Flag once — one security risk is enough to alert
                    break

        return flags

    @staticmethod
    def _make_flag(
        category: str,
        severity: str,
        message: str,
        related_items: list[str] | None = None,
    ) -> dict:
        """Create a RiskFlag dict."""
        return {
            "id": str(uuid.uuid4()),
            "category": category,
            "severity": severity,
            "message": message,
            "related_items": related_items or [],
            "resolved": False,
        }
