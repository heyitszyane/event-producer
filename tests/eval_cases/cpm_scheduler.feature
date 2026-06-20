@cpm-scheduler
Feature: CPM Scheduler
  The CPM (Critical Path Method) Scheduler computes a deterministic, dependency-aware
  timeline for event production tasks. It respects task dependencies, vendor lead times,
  and fixed wall-clock anchors. All durations use Decimal hours; all lead times use
  Decimal days. The scheduler detects cycles, lead-time violations, and anchor
  conflicts — it never silently produces an infeasible schedule.

  Scenario: Simple linear dependency chain
    Given a start time of datetime(2026, 7, 15, 8, 0)
    And task "A" with duration Decimal('2.0'), no dependencies
    And task "B" with duration Decimal('3.0'), depends on ["A"]
    And task "C" with duration Decimal('1.5'), depends on ["B"]
    When the scheduler computes the schedule
    Then the ordered task ids are ["A", "B", "C"]
    And task "A" earliest_start equals datetime(2026, 7, 15, 8, 0)
    And task "A" earliest_finish equals datetime(2026, 7, 15, 10, 0)
    And task "B" earliest_start equals datetime(2026, 7, 15, 10, 0)
    And task "B" earliest_finish equals datetime(2026, 7, 15, 13, 0)
    And task "C" earliest_start equals datetime(2026, 7, 15, 13, 0)
    And task "C" earliest_finish equals datetime(2026, 7, 15, 14, 30)
    And the critical path is ["A", "B", "C"]

  Scenario: Parallel tasks fan out from a common dependency
    Given a start time of datetime(2026, 7, 15, 8, 0)
    And task "Setup" with duration Decimal('4.0'), no dependencies
    And task "AV Install" with duration Decimal('2.0'), depends on ["Setup"]
    And task "Catering Prep" with duration Decimal('3.0'), depends on ["Setup"]
    When the scheduler computes the schedule
    Then the ordered task ids are ["Setup", "AV Install", "Catering Prep"]
    And task "Setup" earliest_start equals datetime(2026, 7, 15, 8, 0)
    And task "Setup" earliest_finish equals datetime(2026, 7, 15, 12, 0)
    And task "AV Install" earliest_start equals datetime(2026, 7, 15, 12, 0)
    And task "Catering Prep" earliest_start equals datetime(2026, 7, 15, 12, 0)
    And task "AV Install" earliest_finish equals datetime(2026, 7, 15, 14, 0)
    And task "Catering Prep" earliest_finish equals datetime(2026, 7, 15, 15, 0)
    And the critical path is ["Setup", "Catering Prep"]

  Scenario: Fixed wall-clock anchor overrides computed start
    Given a start time of datetime(2026, 7, 15, 8, 0)
    And task "Venue Open" with duration Decimal('1.0'), no dependencies, anchored to datetime(2026, 7, 15, 18, 0)
    And task "Sound Check" with duration Decimal('2.0'), depends on ["Venue Open"]
    When the scheduler computes the schedule
    Then task "Venue Open" earliest_start equals datetime(2026, 7, 15, 18, 0)
    And task "Venue Open" earliest_finish equals datetime(2026, 7, 15, 19, 0)
    And task "Sound Check" earliest_start equals datetime(2026, 7, 15, 19, 0)
    And task "Sound Check" earliest_finish equals datetime(2026, 7, 15, 21, 0)

  Scenario: Lead-time violation detected and reported
    Given a start time of datetime(2026, 7, 10, 8, 0)
    And task "Book Venue" with duration Decimal('0.5'), no dependencies
    And task "Venue Confirm" with duration Decimal('0.5'), depends on ["Book Venue"], lead_time Decimal('3.0')
    And the event date is datetime(2026, 7, 12, 8, 0)
    When the scheduler checks lead times
    Then a SchedulerConflictReport is returned
    And the report contains a lead_time conflict for task "Venue Confirm"
    And the conflict message mentions "lead time"

  Scenario: Anchor conflict between two anchored tasks
    Given a start time of datetime(2026, 7, 15, 8, 0)
    And task "Keynote Setup" with duration Decimal('2.0'), no dependencies, anchored to datetime(2026, 7, 15, 9, 0)
    And task "Panel Setup" with duration Decimal('2.0'), depends on ["Keynote Setup"], anchored to datetime(2026, 7, 15, 10, 0)
    When the scheduler computes the schedule
    Then a SchedulerConflictReport is returned
    And the report contains an anchor conflict for task "Panel Setup"
    And the conflict message mentions "anchor"

  Scenario: Cycle detection prevents infinite loop
    Given a start time of datetime(2026, 7, 15, 8, 0)
    And task "A" with duration Decimal('1.0'), depends on ["C"]
    And task "B" with duration Decimal('1.0'), depends on ["A"]
    And task "C" with duration Decimal('1.0'), depends on ["B"]
    When the scheduler computes the schedule
    Then a SchedulerConflictReport is returned
    And the report contains a cycle conflict
    And the conflict involves tasks ["A", "B", "C"]

  Scenario: Empty task list returns empty schedule
    Given a start time of datetime(2026, 7, 15, 8, 0)
    And no tasks
    When the scheduler computes the schedule
    Then the result is a ScheduleResult
    And ordered_tasks is empty
    And critical_path is empty

  Scenario: Single task with no dependencies
    Given a start time of datetime(2026, 7, 15, 8, 0)
    And task "Rehearsal" with duration Decimal('2.5'), no dependencies
    When the scheduler computes the schedule
    Then the result is a ScheduleResult
    And ordered_tasks has 1 entry
    And the task "Rehearsal" earliest_start equals datetime(2026, 7, 15, 8, 0)
    And the task "Rehearsal" earliest_finish equals datetime(2026, 7, 15, 10, 30)
    And the critical path is ["Rehearsal"]

  Scenario: Call-sheet derivation produces chronologically ordered entries
    Given a start time of datetime(2026, 7, 15, 8, 0)
    And task "Load In" with duration Decimal('2.0'), no dependencies
    And task "Sound Check" with duration Decimal('1.0'), depends on ["Load In"]
    And task "Doors Open" with duration Decimal('0.5'), depends on ["Sound Check"]
    When the scheduler computes the schedule
    And a call sheet is derived
    Then the call sheet has 3 entries
    And entry 0 task_name is "Load In"
    And entry 0 start_time equals datetime(2026, 7, 15, 8, 0)
    And entry 1 task_name is "Sound Check"
    And entry 1 start_time equals datetime(2026, 7, 15, 10, 0)
    And entry 2 task_name is "Doors Open"
    And entry 2 start_time equals datetime(2026, 7, 15, 11, 0)
    And each entry start_time is before its end_time
    And entries are in chronological order by start_time

  Scenario: Deterministic output for identical input
    Given a start time of datetime(2026, 7, 15, 8, 0)
    And task "A" with duration Decimal('1.0'), no dependencies
    And task "B" with duration Decimal('2.0'), depends on ["A"]
    And task "C" with duration Decimal('1.5'), depends on ["A"]
    When the scheduler computes the schedule twice with the same input
    Then both ScheduleResult outputs have identical ordered_tasks
    And both ScheduleResult outputs have identical critical_path
    And both ScheduleResult outputs have identical earliest_start values for all tasks
