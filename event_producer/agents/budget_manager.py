"""Budget Manager agent — reconciles event budgets deterministically.

Reason -> Formatter split:
    - BudgetManagerReasonAgent: calls compute_budget from the Budget Engine
      to reconcile the budget to zero.
    - BudgetManagerFormatterAgent: validates the engine's output against the
      BudgetSummary schema.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from event_producer.engines.budget import compute_budget
from event_producer.models.schemas import BudgetLine, BudgetSummary, ScopeItem

if TYPE_CHECKING:
    from event_producer.providers.event_store import EventStore
    from event_producer.providers.rate_card import FxRateProvider


class BudgetManagerReasonAgent:
    """Reasoning agent that reconciles the event budget.

    Delegates the actual computation to the deterministic Budget Engine
    (compute_budget). The reason agent is responsible for gathering the
    required inputs (lines, budget_cap, contingency_pct, fx_provider)
    and invoking the engine from code — never as an LLM tool.
    """

    def __init__(self, event_store: EventStore, fx_provider: FxRateProvider) -> None:
        """Initialize the budget reason agent.

        Args:
            event_store: Abstract event store interface.
            fx_provider: Abstract FX rate provider for currency normalization.
        """
        self._event_store = event_store
        self._fx_provider = fx_provider

    def run(self, request: dict) -> dict:
        """Reconcile the budget by calling compute_budget.

        Args:
            request: Request dict containing:
                - scope_items: list of ScopeItem dicts
                - budget_cap: Decimal-compatible value (str or Decimal)
                - contingency_pct: Decimal-compatible value (str or Decimal)
                - reporting_currency: str (optional, default "USD")

        Returns:
            A dict with:
                - budget_summary: dict representation of the BudgetSummary
                - explanation: human-readable explanation string
        """
        # Extract parameters from the request
        scope_item_dicts = request.get("scope_items", [])
        budget_cap = Decimal(str(request["budget_cap"]))
        contingency_pct = Decimal(str(request["contingency_pct"]))
        reporting_currency = request.get("reporting_currency", "USD")

        # Convert scope item dicts to BudgetLine objects
        lines: list[BudgetLine] = []
        scope_items = [
            ScopeItem(**item) if isinstance(item, dict) else item
            for item in scope_item_dicts
        ]
        any_explicit_selection = any("selected" in item for item in scope_item_dicts if isinstance(item, dict))
        selected_items = [item for item in scope_items if item.selected]
        budgeted_items = selected_items if any_explicit_selection else scope_items

        for scope_item in budgeted_items:
            lines.append(
                BudgetLine(
                    label=scope_item.name,
                    qty=scope_item.qty,
                    unit_cost=scope_item.estimated_cost,
                    currency=scope_item.currency,
                    category=scope_item.category,
                    tier=scope_item.tier,
                )
            )

        # Call the Budget Engine from code (NOT as an LLM tool)
        summary: BudgetSummary = compute_budget(
            lines=lines,
            budget_cap=budget_cap,
            contingency_pct=contingency_pct,
            fx_provider=self._fx_provider,
            reporting_currency=reporting_currency,
        )

        # Build human-readable explanation
        explanation = self._build_explanation(summary)

        return {
            "budget_summary": summary.model_dump(),
            "explanation": explanation,
        }

    @staticmethod
    def _build_explanation(summary: BudgetSummary) -> str:
        """Build a human-readable explanation of the budget summary.

        Args:
            summary: The computed BudgetSummary.

        Returns:
            A human-readable string explaining the budget.
        """
        lines = [
            f"Budget Cap: ${summary.budget_cap:,.2f}",
            f"Contingency Reserve ({summary.contingency_reserve / summary.budget_cap * 100 if summary.budget_cap else Decimal('0'):.0f}%): "
            f"${summary.contingency_reserve:,.2f}",
            f"Spendable after contingency: ${summary.spendable:,.2f}",
            "",
            "Tier Gating:",
        ]

        for tier_name in ("must", "should", "could", "wow"):
            status = "INCLUDED" if summary.tier_inclusion.get(tier_name, False) else "EXCLUDED"
            tier_total = summary.tier_rollups.get(tier_name, Decimal("0.00"))
            lines.append(f"  {tier_name.upper()}: {status} (${tier_total:,.2f})")

        lines.extend([
            "",
            f"Included Totals: ${summary.included_totals:,.2f}",
            f"Headroom Remaining: ${summary.headroom:,.2f}",
        ])

        if summary.over_budget:
            lines.append("WARNING: Budget is OVER the spendable limit.")
        elif summary.under_budget and summary.headroom > Decimal("0"):
            lines.append("Budget is within the spendable limit.")
        elif summary.under_budget and summary.headroom == Decimal("0"):
            lines.append("Budget is fully allocated with zero headroom.")

        return "\n".join(lines)


class BudgetManagerFormatterAgent:
    """Formatter agent that validates budget output against BudgetSummary.

    Ensures the engine output conforms to the BudgetSummary Pydantic schema.
    This agent does NOT call the engine — it only validates.
    """

    def __init__(self) -> None:
        """Initialize the budget formatter agent.

        No dependencies needed — the formatter only validates schemas.
        """

    def run(self, raw_output: dict) -> dict:
        """Validate the budget engine output against the BudgetSummary schema.

        Args:
            raw_output: The BudgetManagerReasonAgent output dict containing:
                - budget_summary: dict representation of a BudgetSummary
                - explanation: human-readable string

        Returns:
            A dict with:
                - budget_summary: validated BudgetSummary (as dict)
                - explanation: str

        Raises:
            pydantic.ValidationError: If the budget_summary data is invalid.
        """
        budget_summary_dict = raw_output["budget_summary"]

        # Validate against BudgetSummary schema — raises ValidationError on invalid data
        validated = BudgetSummary(**budget_summary_dict)

        return {
            "budget_summary": validated.model_dump(),
            "explanation": str(raw_output["explanation"]),
        }
