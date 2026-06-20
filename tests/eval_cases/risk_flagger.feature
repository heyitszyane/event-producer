@risk-flagger
Feature: Risk/Gap Flagger Agent
  The Risk/Gap Flagger agent analyzes the current event state (budget, schedule,
  vendors) and produces RiskFlag items for budget overruns, scheduling conflicts,
  missing vendor coverage, and other gaps.

  Scenario: Detects budget overrun risk
    Given a BudgetSummary where over_budget is True
    And budget_summary.headroom is negative
    And budget_summary.tier_inclusion["could"] is False
    When the Risk Flagger analyzes the budget
    Then the result includes a RiskFlag
    And the RiskFlag category is "budget"
    And the RiskFlag severity is "critical"
    And the RiskFlag message mentions "over budget" or "headroom"
    And the RiskFlag is not resolved

  Scenario: Detects scheduling conflicts
    Given a SchedulerConflictReport with lead_time_conflicts containing at least one Conflict
    And the conflict task_id is "Venue Confirm"
    And the conflict conflict_type is "lead_time"
    When the Risk Flagger analyzes the schedule
    Then the result includes a RiskFlag
    And the RiskFlag category is "schedule"
    And the RiskFlag severity is "warning" or "critical"
    And the RiskFlag message mentions "lead time"
    And the RiskFlag related_items includes "Venue Confirm"

  Scenario: Detects missing vendor coverage
    Given a list of ScopeItem objects where tier is "must"
    And no Vendor is assigned to the "venue" category
    When the Risk Flagger checks vendor coverage
    Then the result includes a RiskFlag
    And the RiskFlag category is "coverage"
    And the RiskFlag severity is "critical"
    And the RiskFlag message mentions "venue" and "no vendor" or "missing"
    And the RiskFlag related_items includes the venue scope item name

  Scenario: Returns empty risk list for clean state
    Given a BudgetSummary where over_budget is False
    And budget_summary.headroom is positive
    And a ScheduleResult with no conflicts
    And all must-tier scope items have assigned vendors
    When the Risk Flagger performs a full analysis
    Then the result is a list of RiskFlag objects
    And the list is empty
    And no RiskFlag has severity "critical"

  Scenario: Detects anchor conflict risk
    Given a SchedulerConflictReport with anchor_conflicts containing at least one Conflict
    And the conflict task_id is "Panel Setup"
    And the conflict conflict_type is "anchor"
    When the Risk Flagger analyzes the schedule
    Then the result includes a RiskFlag
    And the RiskFlag category is "schedule"
    And the RiskFlag message mentions "anchor"
    And the RiskFlag related_items includes "Panel Setup"

  Scenario: Detects cycle in schedule
    Given a SchedulerConflictReport with a cycle involving tasks ["A", "B", "C"]
    When the Risk Flagger analyzes the schedule
    Then the result includes a RiskFlag
    And the RiskFlag category is "schedule"
    And the RiskFlag severity is "critical"
    And the RiskFlag message mentions "cycle" or "circular dependency"
    And the RiskFlag related_items includes "A"
