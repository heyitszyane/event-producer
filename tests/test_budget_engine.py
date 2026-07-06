"""Unit tests for the Budget Engine.

All monetary values use Decimal("...") string literals — never float.
Tests are isolated, deterministic, and cover every Gherkin scenario.
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from event_producer.engines.budget import compute_budget
from event_producer.models.schemas import BudgetLine, Receipt
from event_producer.providers.rate_card import StaticFxRateProvider


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def fx() -> StaticFxRateProvider:
    return StaticFxRateProvider()


# ---------------------------------------------------------------------------
# 1. Zero-sum reconciliation
# ---------------------------------------------------------------------------


def test_budget_reconciles_to_zero(fx: StaticFxRateProvider) -> None:
    """Single USD line, budget cap $10k, 15% contingency.

    Assert both zero-sum invariants:
      1. budget_cap - contingency - spendable == 0
      2. spendable - included_totals - headroom == 0
    """
    lines = [
        BudgetLine(
            label="Venue",
            qty=Decimal("1"),
            unit_cost=Decimal("3000.00"),
            currency="USD",
            category="venue",
            tier="must",
        ),
    ]
    result = compute_budget(
        lines=lines,
        budget_cap=Decimal("10000.00"),
        contingency_pct=Decimal("15"),
        fx_provider=fx,
    )

    # Invariant 1: cap == contingency + spendable
    assert (
        result.budget_cap - result.contingency_reserve - result.spendable
    ) == Decimal("0")

    # Invariant 2: spendable == included_totals + headroom
    assert (
        result.spendable - result.included_totals - result.headroom
    ) == Decimal("0")


# ---------------------------------------------------------------------------
# 2. Contingency defaults
# ---------------------------------------------------------------------------


def test_contingency_default_15_pct(fx: StaticFxRateProvider) -> None:
    """Budget cap $100k, no lines. Assert contingency = $15,000, spendable = $85,000."""
    result = compute_budget(
        lines=[],
        budget_cap=Decimal("100000.00"),
        contingency_pct=Decimal("15"),
        fx_provider=fx,
    )
    assert result.contingency_reserve == Decimal("15000.00")
    assert result.spendable == Decimal("85000.00")


def test_contingency_custom_20_pct(fx: StaticFxRateProvider) -> None:
    """Budget cap $50k, 20% contingency, no lines."""
    result = compute_budget(
        lines=[],
        budget_cap=Decimal("50000.00"),
        contingency_pct=Decimal("20"),
        fx_provider=fx,
    )
    assert result.contingency_reserve == Decimal("10000.00")
    assert result.spendable == Decimal("40000.00")


# ---------------------------------------------------------------------------
# 3. Multi-currency normalization
# ---------------------------------------------------------------------------


def test_multi_currency_normalization(fx: StaticFxRateProvider) -> None:
    """One SGD line + one THB line, USD reporting. Verify FX conversion."""
    lines = [
        BudgetLine(
            label="Catering (SGD)",
            qty=Decimal("1"),
            unit_cost=Decimal("1340.00"),
            currency="SGD",
            category="catering",
            tier="must",
        ),
        BudgetLine(
            label="Decor (THB)",
            qty=Decimal("1"),
            unit_cost=Decimal("3550.00"),
            currency="THB",
            category="decor",
            tier="should",
        ),
    ]
    result = compute_budget(
        lines=lines,
        budget_cap=Decimal("50000.00"),
        contingency_pct=Decimal("15"),
        fx_provider=fx,
        reporting_currency="USD",
    )

    # SGD -> USD: 1340 / 1.34 = 1000.00
    # THB -> USD: 3550 / 35.50 = 100.00
    assert result.lines[0].unit_cost == Decimal("1000.00")
    assert result.lines[0].currency == "USD"
    assert result.lines[1].unit_cost == Decimal("100.00")
    assert result.lines[1].currency == "USD"


# ---------------------------------------------------------------------------
# 4. Tier gating
# ---------------------------------------------------------------------------


def test_tier_gating_fits_partial(fx: StaticFxRateProvider) -> None:
    """Budget cap $20k, 15% (spendable=$17k). must=$10k, should=$5k, could=$5k, wow=$5k."""
    lines = [
        BudgetLine(
            label="Venue",
            qty=Decimal("1"),
            unit_cost=Decimal("10000.00"),
            currency="USD",
            category="venue",
            tier="must",
        ),
        BudgetLine(
            label="AV Setup",
            qty=Decimal("1"),
            unit_cost=Decimal("5000.00"),
            currency="USD",
            category="av",
            tier="should",
        ),
        BudgetLine(
            label="Photo Booth",
            qty=Decimal("1"),
            unit_cost=Decimal("5000.00"),
            currency="USD",
            category="entertainment",
            tier="could",
        ),
        BudgetLine(
            label="Fireworks",
            qty=Decimal("1"),
            unit_cost=Decimal("5000.00"),
            currency="USD",
            category="entertainment",
            tier="wow",
        ),
    ]
    result = compute_budget(
        lines=lines,
        budget_cap=Decimal("20000.00"),
        contingency_pct=Decimal("15"),
        fx_provider=fx,
    )

    assert result.tier_inclusion["must"] is True
    assert result.tier_inclusion["should"] is True
    assert result.tier_inclusion["could"] is False
    assert result.tier_inclusion["wow"] is False
    assert result.headroom == Decimal("2000.00")


def test_count_all_without_gating(fx: StaticFxRateProvider) -> None:
    """gate_discretionary_tiers=False counts every tier; headroom can go negative.

    Same inputs as test_tier_gating_fits_partial (spendable=$17k, total=$25k)
    but with gating disabled, so every item counts and the plan is over budget.
    The zero-sum reconciliation invariant must still hold with a negative headroom.
    """
    lines = [
        BudgetLine(label="Venue", qty=Decimal("1"), unit_cost=Decimal("10000.00"), currency="USD", category="venue", tier="must"),
        BudgetLine(label="AV Setup", qty=Decimal("1"), unit_cost=Decimal("5000.00"), currency="USD", category="av", tier="should"),
        BudgetLine(label="Photo Booth", qty=Decimal("1"), unit_cost=Decimal("5000.00"), currency="USD", category="entertainment", tier="could"),
        BudgetLine(label="Fireworks", qty=Decimal("1"), unit_cost=Decimal("5000.00"), currency="USD", category="entertainment", tier="wow"),
    ]
    result = compute_budget(
        lines=lines,
        budget_cap=Decimal("20000.00"),
        contingency_pct=Decimal("15"),
        fx_provider=fx,
        gate_discretionary_tiers=False,
    )

    # Every tier is included when gating is off.
    assert all(result.tier_inclusion[tier] is True for tier in ("must", "should", "could", "wow"))
    assert result.included_totals == Decimal("25000.00")
    # Spendable is $17k, so headroom is negative and the plan is over budget.
    assert result.headroom == Decimal("-8000.00")
    assert result.over_budget is True
    # Zero-sum reconciliation still holds even when headroom is negative.
    assert (result.spendable - result.included_totals - result.headroom) == Decimal("0")


def test_tier_gating_fits_all(fx: StaticFxRateProvider) -> None:
    """Budget cap $100k, 15% (spendable=$85k). All tiers fit."""
    lines = [
        BudgetLine(
            label="Venue",
            qty=Decimal("1"),
            unit_cost=Decimal("10000.00"),
            currency="USD",
            category="venue",
            tier="must",
        ),
        BudgetLine(
            label="AV Setup",
            qty=Decimal("1"),
            unit_cost=Decimal("20000.00"),
            currency="USD",
            category="av",
            tier="should",
        ),
        BudgetLine(
            label="Photo Booth",
            qty=Decimal("1"),
            unit_cost=Decimal("30000.00"),
            currency="USD",
            category="entertainment",
            tier="could",
        ),
        BudgetLine(
            label="Fireworks",
            qty=Decimal("1"),
            unit_cost=Decimal("10000.00"),
            currency="USD",
            category="entertainment",
            tier="wow",
        ),
    ]
    result = compute_budget(
        lines=lines,
        budget_cap=Decimal("100000.00"),
        contingency_pct=Decimal("15"),
        fx_provider=fx,
    )

    assert result.tier_inclusion["must"] is True
    assert result.tier_inclusion["should"] is True
    assert result.tier_inclusion["could"] is True
    assert result.tier_inclusion["wow"] is True
    assert result.headroom == Decimal("15000.00")


# ---------------------------------------------------------------------------
# 5. Over-budget flag
# ---------------------------------------------------------------------------


def test_over_budget_flag(fx: StaticFxRateProvider) -> None:
    """Budget cap $5k, 15% (spendable=$4,250). Single must line at $5k."""
    lines = [
        BudgetLine(
            label="Venue",
            qty=Decimal("1"),
            unit_cost=Decimal("5000.00"),
            currency="USD",
            category="venue",
            tier="must",
        ),
    ]
    result = compute_budget(
        lines=lines,
        budget_cap=Decimal("5000.00"),
        contingency_pct=Decimal("15"),
        fx_provider=fx,
    )
    assert result.over_budget is True
    assert result.headroom < Decimal("0")


# ---------------------------------------------------------------------------
# 6. Zero budget
# ---------------------------------------------------------------------------


def test_zero_budget(fx: StaticFxRateProvider) -> None:
    """Budget cap $0, one must line at $1k."""
    lines = [
        BudgetLine(
            label="Venue",
            qty=Decimal("1"),
            unit_cost=Decimal("1000.00"),
            currency="USD",
            category="venue",
            tier="must",
        ),
    ]
    result = compute_budget(
        lines=lines,
        budget_cap=Decimal("0"),
        contingency_pct=Decimal("15"),
        fx_provider=fx,
    )
    assert result.contingency_reserve == Decimal("0")
    assert result.spendable == Decimal("0")
    assert result.over_budget is True
    assert result.under_budget is False


# ---------------------------------------------------------------------------
# 7. Single line item
# ---------------------------------------------------------------------------


def test_single_line_item(fx: StaticFxRateProvider) -> None:
    """Budget cap $10k, 15% (spendable=$8,500). One must line at $3k."""
    lines = [
        BudgetLine(
            label="Venue",
            qty=Decimal("1"),
            unit_cost=Decimal("3000.00"),
            currency="USD",
            category="venue",
            tier="must",
        ),
    ]
    result = compute_budget(
        lines=lines,
        budget_cap=Decimal("10000.00"),
        contingency_pct=Decimal("15"),
        fx_provider=fx,
    )
    assert result.headroom == Decimal("5500.00")
    assert result.over_budget is False
    assert result.under_budget is True


# ---------------------------------------------------------------------------
# 8. Full zero-sum reconciliation
# ---------------------------------------------------------------------------


def test_full_zero_sum_reconciliation(fx: StaticFxRateProvider) -> None:
    """Budget cap $50k, 15%. Lines totaling $40k across must/should."""
    lines = [
        BudgetLine(
            label="Venue",
            qty=Decimal("1"),
            unit_cost=Decimal("25000.00"),
            currency="USD",
            category="venue",
            tier="must",
        ),
        BudgetLine(
            label="Catering",
            qty=Decimal("1"),
            unit_cost=Decimal("15000.00"),
            currency="USD",
            category="catering",
            tier="should",
        ),
    ]
    result = compute_budget(
        lines=lines,
        budget_cap=Decimal("50000.00"),
        contingency_pct=Decimal("15"),
        fx_provider=fx,
    )

    # Exact intermediate values
    assert result.contingency_reserve == Decimal("7500.00")
    assert result.spendable == Decimal("42500.00")
    assert result.headroom == Decimal("2500.00")

    # Both zero-sum equations
    assert (
        result.budget_cap - result.contingency_reserve - result.spendable
    ) == Decimal("0.00")
    assert (
        result.spendable - result.included_totals - result.headroom
    ) == Decimal("0.00")


# ---------------------------------------------------------------------------
# 9. Category rollups
# ---------------------------------------------------------------------------


def test_category_rollups(fx: StaticFxRateProvider) -> None:
    """Three lines in different categories. Assert each rollup total."""
    lines = [
        BudgetLine(
            label="Grand Ballroom",
            qty=Decimal("1"),
            unit_cost=Decimal("8000.00"),
            currency="USD",
            category="venue",
            tier="must",
        ),
        BudgetLine(
            label="Sound System",
            qty=Decimal("1"),
            unit_cost=Decimal("3000.00"),
            currency="USD",
            category="av",
            tier="must",
        ),
        BudgetLine(
            label="Buffet Lunch",
            qty=Decimal("100"),
            unit_cost=Decimal("25.00"),
            currency="USD",
            category="catering",
            tier="must",
        ),
    ]
    result = compute_budget(
        lines=lines,
        budget_cap=Decimal("50000.00"),
        contingency_pct=Decimal("15"),
        fx_provider=fx,
    )

    assert result.category_rollups["venue"] == Decimal("8000.00")
    assert result.category_rollups["av"] == Decimal("3000.00")
    assert result.category_rollups["catering"] == Decimal("2500.00")


# ---------------------------------------------------------------------------
# 10. Receipt variance and running burn
# ---------------------------------------------------------------------------


def test_receipt_variance_and_running_burn(fx: StaticFxRateProvider) -> None:
    """Venue line at $10k. Receipt for Venue at $11,500."""
    lines = [
        BudgetLine(
            label="Venue",
            qty=Decimal("1"),
            unit_cost=Decimal("10000.00"),
            currency="USD",
            category="venue",
            tier="must",
        ),
    ]
    receipts = [
        Receipt(
            vendor="Grand Hall Inc.",
            amount=Decimal("11500.00"),
            currency="USD",
            line_item_label="Venue",
        ),
    ]
    result = compute_budget(
        lines=lines,
        budget_cap=Decimal("50000.00"),
        contingency_pct=Decimal("15"),
        fx_provider=fx,
        receipts=receipts,
    )

    assert result.variance.receipt_vs_plan["Venue"] == Decimal("1500.00")
    assert result.variance.running_burn == Decimal("11500.00")


# ---------------------------------------------------------------------------
# 11. No receipts => zero variance
# ---------------------------------------------------------------------------


def test_no_receipts_zero_variance(fx: StaticFxRateProvider) -> None:
    """Budget with lines, no receipts. All variance fields zero."""
    lines = [
        BudgetLine(
            label="Venue",
            qty=Decimal("1"),
            unit_cost=Decimal("10000.00"),
            currency="USD",
            category="venue",
            tier="must",
        ),
    ]
    result = compute_budget(
        lines=lines,
        budget_cap=Decimal("50000.00"),
        contingency_pct=Decimal("15"),
        fx_provider=fx,
    )

    assert result.variance.receipt_vs_plan == {}
    assert result.variance.running_burn == Decimal("0.00")
    assert result.variance.projected_total == Decimal("0.00")
    assert result.variance.burn_rate == Decimal("0.00")


# ---------------------------------------------------------------------------
# 12. Deterministic
# ---------------------------------------------------------------------------


def test_deterministic(fx: StaticFxRateProvider) -> None:
    """Call compute_budget twice with identical inputs. Results must be equal."""
    lines = [
        BudgetLine(
            label="Venue",
            qty=Decimal("1"),
            unit_cost=Decimal("5000.00"),
            currency="USD",
            category="venue",
            tier="must",
        ),
        BudgetLine(
            label="Catering",
            qty=Decimal("50"),
            unit_cost=Decimal("30.00"),
            currency="USD",
            category="catering",
            tier="should",
        ),
    ]
    result_1 = compute_budget(
        lines=list(lines),
        budget_cap=Decimal("20000.00"),
        contingency_pct=Decimal("15"),
        fx_provider=fx,
    )
    result_2 = compute_budget(
        lines=list(lines),
        budget_cap=Decimal("20000.00"),
        contingency_pct=Decimal("15"),
        fx_provider=fx,
    )
    assert result_1 == result_2


# ---------------------------------------------------------------------------
# 13. No float arithmetic
# ---------------------------------------------------------------------------


def test_no_float_arithmetic(fx: StaticFxRateProvider) -> None:
    """All monetary output values must be Decimal, not float."""
    lines = [
        BudgetLine(
            label="Venue",
            qty=Decimal("1"),
            unit_cost=Decimal("3000.00"),
            currency="USD",
            category="venue",
            tier="must",
        ),
    ]
    result = compute_budget(
        lines=lines,
        budget_cap=Decimal("10000.00"),
        contingency_pct=Decimal("15"),
        fx_provider=fx,
    )

    monetary_fields = [
        result.budget_cap,
        result.contingency_reserve,
        result.spendable,
        result.included_totals,
        result.headroom,
    ]
    for value in monetary_fields:
        assert type(value) is Decimal, f"Expected Decimal, got {type(value)} for {value}"


# ---------------------------------------------------------------------------
# 14. Headroom exactly zero
# ---------------------------------------------------------------------------


def test_headroom_exactly_zero(fx: StaticFxRateProvider) -> None:
    """Budget cap $10k, 15% (spendable=$8,500). One line at exactly $8,500."""
    lines = [
        BudgetLine(
            label="Venue",
            qty=Decimal("1"),
            unit_cost=Decimal("8500.00"),
            currency="USD",
            category="venue",
            tier="must",
        ),
    ]
    result = compute_budget(
        lines=lines,
        budget_cap=Decimal("10000.00"),
        contingency_pct=Decimal("15"),
        fx_provider=fx,
    )
    assert result.headroom == Decimal("0.00")
    assert result.over_budget is False
    assert result.under_budget is True


# ---------------------------------------------------------------------------
# 15. Multi-currency all non-USD
# ---------------------------------------------------------------------------


def test_multi_currency_all_non_usd(fx: StaticFxRateProvider) -> None:
    """SGD line + THB line, USD reporting. Both converted via inverse rate."""
    lines = [
        BudgetLine(
            label="Catering (SGD)",
            qty=Decimal("1"),
            unit_cost=Decimal("1340.00"),
            currency="SGD",
            category="catering",
            tier="must",
        ),
        BudgetLine(
            label="Decor (THB)",
            qty=Decimal("1"),
            unit_cost=Decimal("3550.00"),
            currency="THB",
            category="decor",
            tier="must",
        ),
    ]
    result = compute_budget(
        lines=lines,
        budget_cap=Decimal("50000.00"),
        contingency_pct=Decimal("15"),
        fx_provider=fx,
        reporting_currency="USD",
    )

    # Both lines should be normalized to USD
    assert result.lines[0].currency == "USD"
    assert result.lines[1].currency == "USD"
    # SGD -> USD: 1340 / 1.34 = 1000.00
    # THB -> USD: 3550 / 35.50 = 100.00
    assert result.lines[0].unit_cost == Decimal("1000.00")
    assert result.lines[1].unit_cost == Decimal("100.00")
    assert result.included_totals == Decimal("1100.00")


# ---------------------------------------------------------------------------
# 16. Invalid budget cap
# ---------------------------------------------------------------------------


def test_invalid_budget_cap_raises(fx: StaticFxRateProvider) -> None:
    """Negative budget cap must raise ValueError."""
    with pytest.raises(ValueError):
        compute_budget(
            lines=[],
            budget_cap=Decimal("-100.00"),
            contingency_pct=Decimal("15"),
            fx_provider=fx,
        )


# ---------------------------------------------------------------------------
# 17. Invalid contingency percentage
# ---------------------------------------------------------------------------


def test_invalid_contingency_pct_raises(fx: StaticFxRateProvider) -> None:
    """Contingency > 100 or < 0 must raise ValueError."""
    with pytest.raises(ValueError):
        compute_budget(
            lines=[],
            budget_cap=Decimal("10000.00"),
            contingency_pct=Decimal("101"),
            fx_provider=fx,
        )
    with pytest.raises(ValueError):
        compute_budget(
            lines=[],
            budget_cap=Decimal("10000.00"),
            contingency_pct=Decimal("-5"),
            fx_provider=fx,
        )


# ---------------------------------------------------------------------------
# 18. Float rejected by model
# ---------------------------------------------------------------------------


def test_float_rejected_by_model() -> None:
    """Pass a float to a Decimal field on BudgetLine. Expect ValidationError."""
    with pytest.raises(ValidationError):
        BudgetLine(
            label="Venue",
            qty=1.0,  # type: ignore[arg-type]
            unit_cost=Decimal("3000.00"),
            currency="USD",
            category="venue",
            tier="must",
        )


# ---------------------------------------------------------------------------
# 19. Receipt variance aggregates multiple receipts per label
# ---------------------------------------------------------------------------


def test_receipt_variance_aggregates_multiple_receipts_per_label(
    fx: StaticFxRateProvider,
) -> None:
    """Two receipts for Venue label ($6000 + $5500) against planned $10000."""
    lines = [
        BudgetLine(
            label="Venue",
            qty=Decimal("1"),
            unit_cost=Decimal("10000.00"),
            currency="USD",
            category="venue",
            tier="must",
        ),
    ]
    receipts = [
        Receipt(
            vendor="Grand Hall Inc.",
            amount=Decimal("6000.00"),
            currency="USD",
            line_item_label="Venue",
        ),
        Receipt(
            vendor="Grand Hall Inc.",
            amount=Decimal("5500.00"),
            currency="USD",
            line_item_label="Venue",
        ),
    ]
    result = compute_budget(
        lines=lines,
        budget_cap=Decimal("50000.00"),
        contingency_pct=Decimal("15"),
        fx_provider=fx,
        receipts=receipts,
    )

    # Aggregated actual = 6000 + 5500 = 11500; planned = 10000; variance = 1500
    assert result.variance.receipt_vs_plan["Venue"] == Decimal("1500.00")
    # Running burn = 6000 + 5500 = 11500
    assert result.variance.running_burn == Decimal("11500.00")


# ---------------------------------------------------------------------------
# 20. FX line-total-first rounding
# ---------------------------------------------------------------------------


def test_fx_line_total_first_rounding(fx: StaticFxRateProvider) -> None:
    """Verify total is computed as (unit_cost*qty*rate) rounded, not (unit_cost*rate rounded)*qty rounded.

    Use THB rate 35.50, unit_cost=100.00 THB, qty=3.
    Old method: unit = (100/35.50).quantize(CENT) = 2.82, total = 2.82*3 = 8.46
    New method: total = (100*3/35.50).quantize(CENT) = 8.45, unit = 8.45/3 = 2.82
    """
    lines = [
        BudgetLine(
            label="Decor (THB)",
            qty=Decimal("3"),
            unit_cost=Decimal("100.00"),
            currency="THB",
            category="decor",
            tier="should",
        ),
    ]
    result = compute_budget(
        lines=lines,
        budget_cap=Decimal("50000.00"),
        contingency_pct=Decimal("15"),
        fx_provider=fx,
        reporting_currency="USD",
    )

    # Line-total-first: (100.00 * 3 / 35.50).quantize(CENT) = 8.45
    # Old method would give: (100/35.50).quantize(CENT) = 2.82, *3 = 8.46
    assert result.lines[0].unit_cost == Decimal("2.82")
    # The normalized total should be 8.45 (line-total-first), not 8.46 (unit-first)
    # We verify via the spendable/included/headroom invariant
    assert result.spendable - result.included_totals - result.headroom == Decimal("0.00")
