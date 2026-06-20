@production-manager
Feature: Production Manager Agent
  The Production Manager agent computes schedules by calling the CPM Scheduler
  from code (not as an LLM tool). It returns RunOfShow objects with ordered
  timelines, handles scheduling conflicts, and derives call sheets.

  Scenario: Computes schedule from event spec and scope for a networking event
    Given an EventSpec for a networking event on 2026-08-15
    And scope items requiring the following production tasks:
      | id    | name           | duration | dependencies | anchor           |
      | load  | Load In        | 3.0      | []           |                  |
      | av    | AV Setup       | 2.0      | [load]       |                  |
      | sound | Sound Check    | 1.0      | [av]         |                  |
      | doors | Doors Open     | 0.5      | [sound]      | 2026-08-15T18:00 |
      | keynote | Keynote Speech | 1.0    | [doors]      |                  |
    When the Production Manager calls the CPM Scheduler
    Then the result is a ScheduleResult
    And ordered_tasks has 5 entries
    And the critical path includes "load" and "doors"
    And task "doors" earliest_start equals datetime(2026, 8, 15, 18, 0)

  Scenario: Returns RunOfShow with ordered timeline
    Given a computed ScheduleResult for the networking event
    When the Production Manager builds the RunOfShow
    Then the RunOfShow contains the EventSpec
    And the RunOfShow contains the ScheduleResult
    And the RunOfShow contains a call_sheet
    And each call_sheet entry has a start_time before its end_time
    And call_sheet entries are in chronological order by start_time

  Scenario: Handles scheduling conflicts — lead time violation
    Given a task "Book Venue" with no dependencies
    And a task "Venue Confirm" depending on "Book Venue" with lead_time Decimal('30.0') days
    And the event date is only 14 days away
    When the Production Manager calls the CPM Scheduler
    Then a SchedulerConflictReport is returned
    And the report contains a lead_time conflict for task "Venue Confirm"
    And the conflict message mentions "lead time"

  Scenario: Handles scheduling conflicts — anchor conflict
    Given a task "Keynote Setup" anchored to datetime(2026, 8, 15, 9, 0) with duration Decimal('2.0')
    And a task "Panel Setup" depending on "Keynote Setup" anchored to datetime(2026, 8, 15, 10, 0) with duration Decimal('2.0')
    When the Production Manager calls the CPM Scheduler
    Then a SchedulerConflictReport is returned
    And the report contains an anchor conflict for task "Panel Setup"
    And the conflict message mentions "anchor"

  Scenario: Derives call sheet from schedule
    Given a computed ScheduleResult with 4 ordered tasks
    When the Production Manager derives the call sheet
    Then the call sheet has 4 entries
    And each entry has a task_name, start_time, end_time, and is_anchor flag
    And entry 0 has the earliest start_time
    And entry 3 has the latest start_time
    And entries are in chronological order by start_time

  Scenario: Production Manager calls scheduler from code, not as LLM tool
    Given any valid event spec and scope
    When the Production Manager computes the schedule
    Then the CPM Scheduler is invoked as a Python function call
    And the scheduler is NOT invoked as an LLM tool call
    And the result is a ScheduleResult Pydantic model
