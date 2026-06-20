@budget-engine
Feature: Budget Engine
  The Budget Engine reconciles event budgets to zero, normalizes multi-currency
  line items, gates spend by tier, and tracks variance against receipts.
  All monetary values use Decimal — never float.

  Scenario: Budget reconciles to zero (single currency, single line)
    Given a budget cap of Decimal('10000.00') and contingency rate Decimal('15')
    And a single line item "Venue" at Decimal('5000.00') USD, must tier
    When the engine computes the budget summary
    Then budget_cap - contingency_reserve - spendable equals Decimal('0.00')
    And spendable - included_totals - headroom equals Decimal('0.00')

  Scenario: Contingency always reserved at 15% default
    Given a budget cap of Decimal('100000.00') and default contingency
    And no line items
    When the engine computes
    Then contingency_reserve equals Decimal('15000.00')
    And spendable equals Decimal('85000.00')

  Scenario: Multi-currency normalization (SGD + THB, USD reporting)
    Given a budget cap of Decimal('50000.00') USD, contingency 15%
    And a line "Venue" at Decimal('10000.00') SGD, must tier
    And a line "Catering" at Decimal('500000.00') THB, should tier
    When the engine computes with USD reporting currency
    Then all lines are normalized to USD using the seeded FX rates
    And category_rollups contains "Venue" and "Catering" keys with USD-normalized totals

  Scenario: Tier-gating: must/should fit, could/wow excluded
    Given a budget cap of Decimal('20000.00') USD, contingency 15%
    And must-tier lines totaling Decimal('10000.00')
    And should-tier lines totaling Decimal('5000.00')
    And could-tier lines totaling Decimal('5000.00')
    And wow-tier lines totaling Decimal('5000.00')
    When the engine computes
    Then tier_inclusion["must"] is True
    And tier_inclusion["should"] is True
    And tier_inclusion["could"] is False
    And tier_inclusion["wow"] is False
    And headroom equals Decimal('2000.00')

  Scenario: Over-budget flag
    Given a budget cap of Decimal('5000.00') USD, contingency 15%
    And a single line "Venue" at Decimal('5000.00') USD, must tier
    When the engine computes
    Then over_budget is True
    And headroom is negative

  Scenario: Zero budget edge case
    Given a budget cap of Decimal('0.00') USD, contingency 15%
    And a single line "Venue" at Decimal('1000.00') USD, must tier
    When the engine computes
    Then contingency_reserve equals Decimal('0.00')
    And spendable equals Decimal('0.00')
    And over_budget is True
    And under_budget is False

  Scenario: Single line item budget
    Given a budget cap of Decimal('10000.00') USD, contingency 15%
    And a single line "Venue" at Decimal('3000.00') USD, must tier
    When the engine computes
    Then headroom equals Decimal('5500.00')
    And over_budget is False
    And under_budget is True

  Scenario: Multi-currency with all non-USD lines (cross-rate via USD pivot)
    Given a budget cap of Decimal('50000.00') USD, contingency 15%
    And a line "Venue" at Decimal('10000.00') SGD, must tier
    And a line "Catering" at Decimal('200000.00') THB, should tier
    When the engine computes with USD reporting currency
    Then the SGD line is converted via inverse rate (1/USD_SGD)
    And the THB line is converted via inverse rate (1/USD_THB)
    And totals are in USD

  Scenario: Contingency at 20% (non-default)
    Given a budget cap of Decimal('50000.00') and contingency rate Decimal('20')
    And no line items
    When the engine computes
    Then contingency_reserve equals Decimal('10000.00')
    And spendable equals Decimal('40000.00')

  Scenario: Headroom exactly zero
    Given a budget cap of Decimal('10000.00') USD, contingency 15%
    And a single line "Venue" at Decimal('8500.00') USD, must tier
    When the engine computes
    Then headroom equals Decimal('0.00')
    And over_budget is False
    And under_budget is True

  @zero-sum
  Scenario: Full zero-sum reconciliation
    Given a budget cap of Decimal('50000.00') and contingency rate Decimal('15')
    And line items totaling Decimal('40000.00') across must/should tiers
    When the engine computes the budget summary
    Then budget_cap - contingency_reserve - spendable MUST equal Decimal('0.00')
    AND spendable - included_totals - headroom MUST equal Decimal('0.00')
    AND contingency_reserve equals Decimal('7500.00')
    AND spendable equals Decimal('42500.00')
    AND headroom equals Decimal('2500.00')

  Scenario: Category rollup correctness
    Given a budget cap of Decimal('50000.00') USD, contingency 15%
    And a line "Venue rental" at Decimal('10000.00') USD, category "venue", must tier
    And a line "AV equipment" at Decimal('5000.00') USD, category "AV", should tier
    And a line "Catering" at Decimal('8000.00') USD, category "catering", must tier
    When the engine computes
    Then category_rollups["venue"] equals Decimal('10000.00')
    And category_rollups["AV"] equals Decimal('5000.00')
    And category_rollups["catering"] equals Decimal('8000.00')

  @variance
  Scenario: Receipt-vs-plan variance + running burn
    Given a budget with a line item "Venue" at Decimal('10000.00') USD, must tier
    And a receipt ingested for "Venue" at Decimal('11500.00') USD
    When the engine computes variance
    Then variance.receipt_vs_plan["Venue"] equals Decimal('1500.00')
    AND variance.running_burn equals Decimal('11500.00')
    AND variance.projected_over_under reflects the overage
