@budget-manager
Feature: Budget Manager Agent
  The Budget Manager agent computes budget summaries by calling the Budget Engine
  from code (not as an LLM tool). It returns BudgetSummary objects with correct
  tier gating, explains budget numbers in human-readable form, and handles
  edge cases like empty scope.

  Scenario: Computes budget from scope items for a $50k networking event
    Given a list of ScopeItem objects for a networking event:
      | name              | category   | tier   | estimated_cost | currency |
      | Venue rental      | venue      | must   | 12000.00       | USD      |
      | Catering          | catering   | must   | 8000.00        | USD      |
      | AV equipment      | AV         | should | 5000.00        | USD      |
      | Stage decor       | decor      | could  | 3000.00        | USD      |
      | Live band         | entertainment | wow | 7000.00        | USD      |
    And a budget cap of Decimal('50000.00') USD
    And a contingency rate of Decimal('15')
    When the Budget Manager calls the Budget Engine to compute the budget
    Then the result is a BudgetSummary
    And budget_summary.budget_cap equals Decimal('50000.00')
    And budget_summary.contingency_reserve equals Decimal('7500.00')
    And budget_summary.spendable equals Decimal('42500.00')
    And budget_summary.tier_inclusion["must"] is True
    And budget_summary.tier_inclusion["should"] is True
    And budget_summary.tier_inclusion["could"] is False
    And budget_summary.tier_inclusion["wow"] is False
    And budget_summary.headroom is positive

  Scenario: Returns BudgetSummary with correct tier gating — must/should fit within spendable
    Given must-tier scope items totaling Decimal('15000.00') USD
    And should-tier scope items totaling Decimal('10000.00') USD
    And could-tier scope items totaling Decimal('8000.00') USD
    And a budget cap of Decimal('40000.00') USD with 15% contingency
    When the Budget Manager calls the Budget Engine
    Then budget_summary.spendable equals Decimal('34000.00')
    And budget_summary.tier_inclusion["must"] is True
    And budget_summary.tier_inclusion["should"] is True
    And budget_summary.tier_inclusion["could"] is False
    And budget_summary.included_totals equals Decimal('25000.00')
    And budget_summary.headroom equals Decimal('9000.00')

  Scenario: Explains budget numbers in human-readable form
    Given a computed BudgetSummary for the $50k networking event
    When the Budget Manager formats the explanation
    Then the explanation includes the budget cap
    And the explanation includes the contingency reserve amount
    And the explanation includes the spendable amount
    And the explanation mentions which tiers are included
    And the explanation mentions the headroom remaining
    And the explanation is a human-readable string (not raw JSON)

  Scenario: Handles empty scope items
    Given an empty list of ScopeItem objects
    And a budget cap of Decimal('50000.00') USD
    And a contingency rate of Decimal('15')
    When the Budget Manager calls the Budget Engine
    Then the result is a BudgetSummary
    And budget_summary.lines is empty
    And budget_summary.included_totals equals Decimal('0.00')
    And budget_summary.contingency_reserve equals Decimal('7500.00')
    And budget_summary.spendable equals Decimal('42500.00')
    And budget_summary.headroom equals Decimal('42500.00')
    And budget_summary.over_budget is False

  Scenario: Budget Manager calls engine from code, not as LLM tool
    Given any valid budget input
    When the Budget Manager computes the budget
    Then the Budget Engine is invoked as a Python function call
    And the engine is NOT invoked as an LLM tool call
    And the result is a BudgetSummary Pydantic model
