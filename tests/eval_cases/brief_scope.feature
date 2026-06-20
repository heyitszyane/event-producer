@brief-scope
Feature: Brief/Scope Agent
  The Brief/Scope agent parses user event descriptions into structured EventSpec
  objects, flags missing fields, proposes scope items with correct must/should/could/wow
  tiers, and rejects invalid input gracefully.

  Scenario: Parses a complete brief into EventSpec
    Given a user brief "Networking event for 200 attendees at a hotel ballroom on 2026-08-15, 4 hours, corporate"
    When the Brief/Scope agent parses the brief
    Then the result is an EventSpec
    And event_spec.name is non-empty
    And event_spec.attendees equals 200
    And event_spec.date equals "2026-08-15"
    And event_spec.duration_hours equals Decimal('4.0')
    And event_spec.venue_type equals "hotel ballroom"
    And event_spec.missing_fields is empty

  Scenario: Flags missing fields in incomplete brief
    Given a user brief "We want to host a party"
    When the Brief/Scope agent parses the brief
    Then the result is an EventSpec
    And event_spec.missing_fields contains "date"
    And event_spec.missing_fields contains "attendees"
    And event_spec.missing_fields contains "venue_type"
    And event_spec.missing_fields contains "duration_hours"

  Scenario: Proposes scope items with correct tiers for a $50k networking event
    Given a parsed EventSpec for a 200-person networking event with a $50000 USD budget
    When the Brief/Scope agent proposes scope items
    Then the result is a list of ScopeItem objects
    And at least one ScopeItem has tier "must" and category "venue"
    And at least one ScopeItem has tier "must" and category "catering"
    And at least one ScopeItem has tier "should" and category "AV"
    And at least one ScopeItem has tier "could" and category "decor"
    And at least one ScopeItem has tier "wow" and category "entertainment"
    And each ScopeItem has a non-empty name
    And each ScopeItem has estimated_cost >= Decimal('0.00')

  Scenario: Rejects invalid input gracefully — zero attendees
    Given a user brief with attendees set to 0
    When the Brief/Scope agent parses the brief
    Then the agent returns an error or flags "attendees" in missing_fields
    And no EventSpec is produced with attendees <= 0

  Scenario: Rejects invalid input gracefully — malformed date
    Given a user brief with date set to "not-a-date"
    When the Brief/Scope agent parses the brief
    Then the agent returns an error or flags "date" in missing_fields
    And no EventSpec is produced with an invalid date string

  Scenario: Rejects invalid input gracefully — negative duration
    Given a user brief with duration_hours set to -2
    When the Brief/Scope agent parses the brief
    Then the agent returns an error or flags "duration_hours" in missing_fields
    And no EventSpec is produced with duration_hours <= 0

  Scenario: Handles empty brief
    Given a user brief that is an empty string
    When the Brief/Scope agent parses the brief
    Then the result is an EventSpec
    And event_spec.missing_fields contains all required fields: "name", "date", "attendees", "venue_type", "duration_hours"
