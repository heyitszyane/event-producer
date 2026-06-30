"""Budget Engine — deterministic core for event budget reconciliation.

All arithmetic uses ``Decimal`` — never float. The engine is a pure function:
no I/O, no global state, no randomness, no time dependence.

Zero-sum invariants (by construction):
  1. ``budget_cap - contingency_reserve - spendable == 0``
     Contingency is reserved first; spendable is the remainder.
  2. ``spendable - included_totals - headroom == 0``
     Included totals plus headroom must equal the spendable pool.
"""

from __future__ import annotations

from decimal import Decimal

from event_producer.models.schemas import (
    BudgetLine,
    BudgetSummary,
    BudgetVariance,
    Receipt,
)
from event_producer.providers.rate_card import FxRateProvider

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_TIER_ORDER: tuple[str, ...] = ("must", "should", "could", "wow")

_CENT = Decimal("0.01")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_budget(
    lines: list[BudgetLine],
    budget_cap: Decimal,
    contingency_pct: Decimal,
    fx_provider: FxRateProvider,
    reporting_currency: str = "USD",
    receipts: list[Receipt] | None = None,
) -> BudgetSummary:
    """Reconcile an event budget to zero.

    Contingency is reserved *first* — before any discretionary allocation.
    Remaining spendable funds are then allocated greedily by tier priority
    (must -> should -> could -> wow). Each tier is either fully included or
    fully excluded.

    Args:
        lines: Budget line items, each with qty, unit_cost, currency, tier.
        budget_cap: Total hard budget ceiling. Must be >= 0.
        contingency_pct: Percentage of budget_cap reserved for contingency.
            Must be between 0 and 100 inclusive.
        fx_provider: FX rate provider for currency normalization.
        reporting_currency: Target ISO 4217 currency code (default ``"USD"``).
        receipts: Optional list of vendor receipts for variance tracking.

    Returns:
        ``BudgetSummary`` with rollups, tier gating, and variance.

    Raises:
        ValueError: If ``budget_cap < 0`` or ``contingency_pct`` is outside
            [0, 100] or any line has ``qty <= 0``.
    """
    # -- Input validation ---------------------------------------------------
    if budget_cap < Decimal("0"):
        raise ValueError(
            f"budget_cap must be >= 0, got {budget_cap}"
        )
    if contingency_pct < Decimal("0") or contingency_pct > Decimal("100"):
        raise ValueError(
            f"contingency_pct must be between 0 and 100, got {contingency_pct}"
        )
    for line in lines:
        if line.qty <= Decimal("0"):
            raise ValueError(
                f"qty must be > 0 for line '{line.label}', got {line.qty}"
            )

    # -- Step 1: Contingency reservation (always FIRST) ----------------------
    # Invariant: budget_cap - contingency_reserve - spendable == 0
    if budget_cap == Decimal("0"):
        contingency_reserve = Decimal("0.00")
        spendable = Decimal("0.00")
    else:
        contingency_reserve = (
            budget_cap * contingency_pct / Decimal("100")
        ).quantize(_CENT)
        spendable = (budget_cap - contingency_reserve).quantize(_CENT)

    # -- Step 2: FX normalization -------------------------------------------
    # For each line, convert unit_cost to reporting currency, then compute
    # the normalized total (unit_cost * qty) in reporting currency.
    normalized_lines: list[BudgetLine] = []
    normalized_totals: list[Decimal] = []

    for line in lines:
        rate = fx_provider.get_rate(line.currency, reporting_currency)
        normalized_total = (line.unit_cost * line.qty * rate).quantize(_CENT)
        normalized_unit_cost = (normalized_total / line.qty).quantize(_CENT) if line.qty != Decimal("0") else Decimal("0.00")

        # Build a new BudgetLine with normalized (reporting-currency) costs
        normalized_lines.append(
            BudgetLine(
                label=line.label,
                qty=line.qty,
                unit_cost=normalized_unit_cost,
                currency=reporting_currency,
                category=line.category,
                tier=line.tier,
            )
        )
        normalized_totals.append(normalized_total)

    # -- Step 3: Tier-gating (greedy by tier priority) ----------------------
    # Tier order: must -> should -> could -> wow
    # "must" is ALWAYS included (mandatory spend).  should/could/wow are
    # gated greedily: each tier is either fully included or fully excluded.
    tier_inclusion: dict[str, bool] = {}
    cumulative_included = Decimal("0.00")

    for tier_name in _TIER_ORDER:
        # Sum normalized totals for all lines in this tier
        tier_total = Decimal("0.00")
        for idx, line in enumerate(normalized_lines):
            if line.tier == tier_name:
                tier_total += normalized_totals[idx]
        tier_total = tier_total.quantize(_CENT)

        if tier_name == "must":
            # Mandatory tier: always included, even if it exceeds spendable
            tier_inclusion[tier_name] = True
            cumulative_included += tier_total
        else:
            # Greedy decision: include the entire tier only if it fits
            if cumulative_included + tier_total <= spendable:
                tier_inclusion[tier_name] = True
                cumulative_included += tier_total
            else:
                tier_inclusion[tier_name] = False

    included_totals = cumulative_included.quantize(_CENT)

    # Invariant: spendable - included_totals - headroom == 0
    headroom = (spendable - included_totals).quantize(_CENT)

    # -- Step 4: Rollups (included lines only) ------------------------------
    category_rollups: dict[str, Decimal] = {}
    tier_rollups: dict[str, Decimal] = {}

    for idx, line in enumerate(normalized_lines):
        if tier_inclusion.get(line.tier, False):
            # Category rollup
            if line.category in category_rollups:
                category_rollups[line.category] = (
                    category_rollups[line.category] + normalized_totals[idx]
                ).quantize(_CENT)
            else:
                category_rollups[line.category] = normalized_totals[idx]

            # Tier rollup
            if line.tier in tier_rollups:
                tier_rollups[line.tier] = (
                    tier_rollups[line.tier] + normalized_totals[idx]
                ).quantize(_CENT)
            else:
                tier_rollups[line.tier] = normalized_totals[idx]

    # -- Step 5: Over/under flags -------------------------------------------
    over_budget = included_totals > spendable
    under_budget = included_totals <= spendable and headroom >= Decimal("0")

    # -- Step 6: Receipt-vs-plan variance + running burn --------------------
    variance = _compute_variance(
        lines=normalized_lines,
        normalized_totals=normalized_totals,
        receipts=receipts,
        fx_provider=fx_provider,
        reporting_currency=reporting_currency,
        budget_cap=budget_cap,
    )

    # -- Build summary ------------------------------------------------------
    return BudgetSummary(
        lines=normalized_lines,
        category_rollups=category_rollups,
        tier_rollups=tier_rollups,
        budget_cap=budget_cap,
        contingency_pct=contingency_pct,
        contingency_reserve=contingency_reserve,
        spendable=spendable,
        included_totals=included_totals,
        headroom=headroom,
        tier_inclusion=tier_inclusion,
        over_budget=over_budget,
        under_budget=under_budget,
        variance=variance,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compute_variance(
    lines: list[BudgetLine],
    normalized_totals: list[Decimal],
    receipts: list[Receipt] | None,
    fx_provider: FxRateProvider,
    reporting_currency: str,
    budget_cap: Decimal,
) -> BudgetVariance:
    """Compute receipt-vs-plan variance and running burn.

    If no receipts are provided, returns a ``BudgetVariance`` with all
    defaults (empty dict, all ``Decimal("0.00")``).
    """
    if not receipts:
        return BudgetVariance()

    # Build a lookup: label -> planned normalized total
    planned_by_label: dict[str, Decimal] = {}
    for idx, line in enumerate(lines):
        planned_by_label[line.label] = normalized_totals[idx]

    # First pass: aggregate receipts by label
    actual_by_label: dict[str, Decimal] = {}
    running_burn = Decimal("0.00")

    for receipt in receipts:
        # Normalize receipt amount to reporting currency
        rate = fx_provider.get_rate(receipt.currency, reporting_currency)
        receipt_amount = (receipt.amount * rate).quantize(_CENT)

        running_burn = (running_burn + receipt_amount).quantize(_CENT)

        label = receipt.line_item_label
        actual_by_label[label] = (
            actual_by_label.get(label, Decimal("0.00")) + receipt_amount
        ).quantize(_CENT)

    # Second pass: compute variance per label
    receipt_vs_plan: dict[str, Decimal] = {}
    for label, planned in planned_by_label.items():
        actual = actual_by_label.get(label, Decimal("0.00"))
        receipt_vs_plan[label] = (actual - planned).quantize(_CENT)

    # Include labels that have receipts but no planned line
    for label in actual_by_label:
        if label not in planned_by_label:
            receipt_vs_plan[label] = actual_by_label[label]

    # Projection: current burn IS the projection (simple extrapolation)
    projected_total = running_burn
    projected_over_under = (projected_total - budget_cap).quantize(_CENT)

    # burn_rate is a placeholder (no date data in MVP)
    burn_rate = Decimal("0.00")

    return BudgetVariance(
        receipt_vs_plan=receipt_vs_plan,
        running_burn=running_burn,
        projected_total=projected_total,
        projected_over_under=projected_over_under,
        burn_rate=burn_rate,
    )
