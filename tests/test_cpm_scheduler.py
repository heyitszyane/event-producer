"""Unit tests for the CPM Scheduler.

All durations use Decimal("...") string literals — never float.
Tests are isolated, deterministic, and cover every Gherkin scenario
plus additional edge cases.
"""

import inspect
from datetime import datetime
from decimal import Decimal

import pytest

from event_producer.engines.scheduler import compute_schedule, derive_call_sheet
from event_producer.models.schemas import (
    ScheduleTask,
    ScheduleResult,
    SchedulerConflictReport,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def start_time() -> datetime:
    """Standard project start time used across multiple tests."""
    return datetime(2026, 7, 15, 8, 0)


# ---------------------------------------------------------------------------
# 1. Simple linear dependency chain (Gherkin Scenario 1)
# ---------------------------------------------------------------------------


def test_linear_dependency_chain(start_time: datetime) -> None:
    """A -> B -> C: verify ordering, times, and critical path."""
    tasks = [
        ScheduleTask(id="A", name="Task A", duration=Decimal("2.0")),
        ScheduleTask(id="B", name="Task B", duration=Decimal("3.0"), dependencies=["A"]),
        ScheduleTask(id="C", name="Task C", duration=Decimal("1.5"), dependencies=["B"]),
    ]
    result = compute_schedule(tasks, start_time)

    assert isinstance(result, ScheduleResult)
    assert [t.id for t in result.ordered_tasks] == ["A", "B", "C"]

    by_id = {t.id: t for t in result.ordered_tasks}

    assert by_id["A"].earliest_start == datetime(2026, 7, 15, 8, 0)
    assert by_id["A"].earliest_finish == datetime(2026, 7, 15, 10, 0)

    assert by_id["B"].earliest_start == datetime(2026, 7, 15, 10, 0)
    assert by_id["B"].earliest_finish == datetime(2026, 7, 15, 13, 0)

    assert by_id["C"].earliest_start == datetime(2026, 7, 15, 13, 0)
    assert by_id["C"].earliest_finish == datetime(2026, 7, 15, 14, 30)

    assert result.critical_path == ["A", "B", "C"]


# ---------------------------------------------------------------------------
# 2. Parallel tasks fan out from common dependency (Gherkin Scenario 2)
# ---------------------------------------------------------------------------


def test_parallel_tasks(start_time: datetime) -> None:
    """Setup -> AV Install, Setup -> Catering Prep. Verify fan-out and critical path."""
    tasks = [
        ScheduleTask(id="Setup", name="Setup", duration=Decimal("4.0")),
        ScheduleTask(
            id="AV Install", name="AV Install", duration=Decimal("2.0"),
            dependencies=["Setup"],
        ),
        ScheduleTask(
            id="Catering Prep", name="Catering Prep", duration=Decimal("3.0"),
            dependencies=["Setup"],
        ),
    ]
    result = compute_schedule(tasks, start_time)

    assert isinstance(result, ScheduleResult)
    ids = [t.id for t in result.ordered_tasks]
    assert ids[0] == "Setup"
    assert set(ids[1:]) == {"AV Install", "Catering Prep"}

    by_id = {t.id: t for t in result.ordered_tasks}

    assert by_id["Setup"].earliest_start == datetime(2026, 7, 15, 8, 0)
    assert by_id["Setup"].earliest_finish == datetime(2026, 7, 15, 12, 0)

    assert by_id["AV Install"].earliest_start == datetime(2026, 7, 15, 12, 0)
    assert by_id["Catering Prep"].earliest_start == datetime(2026, 7, 15, 12, 0)

    assert by_id["AV Install"].earliest_finish == datetime(2026, 7, 15, 14, 0)
    assert by_id["Catering Prep"].earliest_finish == datetime(2026, 7, 15, 15, 0)

    # Critical path picks the longer branch: Setup -> Catering Prep (7h) > Setup -> AV Install (6h)
    assert result.critical_path == ["Setup", "Catering Prep"]


# ---------------------------------------------------------------------------
# 3. Fixed wall-clock anchor overrides computed start (Gherkin Scenario 3)
# ---------------------------------------------------------------------------


def test_fixed_anchor(start_time: datetime) -> None:
    """Anchored task starts at anchor time, not computed time."""
    tasks = [
        ScheduleTask(
            id="Venue Open", name="Venue Open", duration=Decimal("1.0"),
            anchor=datetime(2026, 7, 15, 18, 0),
        ),
        ScheduleTask(
            id="Sound Check", name="Sound Check", duration=Decimal("2.0"),
            dependencies=["Venue Open"],
        ),
    ]
    result = compute_schedule(tasks, start_time)

    assert isinstance(result, ScheduleResult)
    by_id = {t.id: t for t in result.ordered_tasks}

    assert by_id["Venue Open"].earliest_start == datetime(2026, 7, 15, 18, 0)
    assert by_id["Venue Open"].earliest_finish == datetime(2026, 7, 15, 19, 0)

    assert by_id["Sound Check"].earliest_start == datetime(2026, 7, 15, 19, 0)
    assert by_id["Sound Check"].earliest_finish == datetime(2026, 7, 15, 21, 0)


# ---------------------------------------------------------------------------
# 4. Lead-time violation detected and reported (Gherkin Scenario 4)
# ---------------------------------------------------------------------------


def test_lead_time_violation(start_time: datetime) -> None:
    """Lead-time conflict between Book Venue and Venue Confirm."""
    # start_time is July 10 08:00; event date is July 12 08:00
    tasks = [
        ScheduleTask(id="Book Venue", name="Book Venue", duration=Decimal("0.5")),
        ScheduleTask(
            id="Venue Confirm", name="Venue Confirm", duration=Decimal("0.5"),
            dependencies=["Book Venue"],
            lead_time=Decimal("3.0"),
        ),
    ]
    result = compute_schedule(tasks, start_time)

    assert isinstance(result, SchedulerConflictReport)
    assert len(result.lead_time_conflicts) >= 1
    conflict_ids = [c.task_id for c in result.lead_time_conflicts]
    assert "Venue Confirm" in conflict_ids
    # Verify the message mentions "lead time"
    venue_confirm_conflicts = [
        c for c in result.lead_time_conflicts if c.task_id == "Venue Confirm"
    ]
    assert any("lead time" in c.message.lower() for c in venue_confirm_conflicts)


# ---------------------------------------------------------------------------
# 5. Anchor conflict between two anchored tasks (Gherkin Scenario 5)
# ---------------------------------------------------------------------------


def test_anchor_conflict(start_time: datetime) -> None:
    """Panel Setup anchored before Keynote Setup finishes -> anchor conflict."""
    tasks = [
        ScheduleTask(
            id="Keynote Setup", name="Keynote Setup", duration=Decimal("2.0"),
            anchor=datetime(2026, 7, 15, 9, 0),
        ),
        ScheduleTask(
            id="Panel Setup", name="Panel Setup", duration=Decimal("2.0"),
            dependencies=["Keynote Setup"],
            anchor=datetime(2026, 7, 15, 10, 0),
        ),
    ]
    result = compute_schedule(tasks, start_time)

    assert isinstance(result, SchedulerConflictReport)
    assert len(result.anchor_conflicts) >= 1
    conflict_ids = [c.task_id for c in result.anchor_conflicts]
    assert "Panel Setup" in conflict_ids
    # Verify the message mentions "anchor"
    panel_conflicts = [
        c for c in result.anchor_conflicts if c.task_id == "Panel Setup"
    ]
    assert any("anchor" in c.message.lower() for c in panel_conflicts)


# ---------------------------------------------------------------------------
# 6. Cycle detection prevents infinite loop (Gherkin Scenario 6)
# ---------------------------------------------------------------------------


def test_cycle_detection(start_time: datetime) -> None:
    """A -> B -> C -> A: cycle must be detected and reported."""
    tasks = [
        ScheduleTask(id="A", name="Task A", duration=Decimal("1.0"), dependencies=["C"]),
        ScheduleTask(id="B", name="Task B", duration=Decimal("1.0"), dependencies=["A"]),
        ScheduleTask(id="C", name="Task C", duration=Decimal("1.0"), dependencies=["B"]),
    ]
    result = compute_schedule(tasks, start_time)

    assert isinstance(result, SchedulerConflictReport)
    assert set(result.cycle) == {"A", "B", "C"}


# ---------------------------------------------------------------------------
# 7. Empty task list returns empty schedule (Gherkin Scenario 7)
# ---------------------------------------------------------------------------


def test_empty_task_list(start_time: datetime) -> None:
    """No tasks -> empty ScheduleResult."""
    result = compute_schedule([], start_time)

    assert isinstance(result, ScheduleResult)
    assert result.ordered_tasks == []
    assert result.critical_path == []


# ---------------------------------------------------------------------------
# 8. Single task with no dependencies (Gherkin Scenario 8)
# ---------------------------------------------------------------------------


def test_single_task_no_deps(start_time: datetime) -> None:
    """Single task: verify start, finish, and critical path."""
    tasks = [
        ScheduleTask(id="Rehearsal", name="Rehearsal", duration=Decimal("2.5")),
    ]
    result = compute_schedule(tasks, start_time)

    assert isinstance(result, ScheduleResult)
    assert len(result.ordered_tasks) == 1

    task = result.ordered_tasks[0]
    assert task.id == "Rehearsal"
    assert task.earliest_start == datetime(2026, 7, 15, 8, 0)
    assert task.earliest_finish == datetime(2026, 7, 15, 10, 30)
    assert result.critical_path == ["Rehearsal"]


# ---------------------------------------------------------------------------
# 9. Call-sheet derivation produces chronologically ordered entries
#    (Gherkin Scenario 10)
# ---------------------------------------------------------------------------


def test_call_sheet_derivation(start_time: datetime) -> None:
    """derive_call_sheet produces chronologically ordered entries."""
    tasks = [
        ScheduleTask(id="Load In", name="Load In", duration=Decimal("2.0")),
        ScheduleTask(
            id="Sound Check", name="Sound Check", duration=Decimal("1.0"),
            dependencies=["Load In"],
        ),
        ScheduleTask(
            id="Doors Open", name="Doors Open", duration=Decimal("0.5"),
            dependencies=["Sound Check"],
        ),
    ]
    result = compute_schedule(tasks, start_time)
    assert isinstance(result, ScheduleResult)

    call_sheet = derive_call_sheet(result)

    assert len(call_sheet) == 3

    assert call_sheet[0].task_name == "Load In"
    assert call_sheet[0].start_time == datetime(2026, 7, 15, 8, 0)

    assert call_sheet[1].task_name == "Sound Check"
    assert call_sheet[1].start_time == datetime(2026, 7, 15, 10, 0)

    assert call_sheet[2].task_name == "Doors Open"
    assert call_sheet[2].start_time == datetime(2026, 7, 15, 11, 0)

    # Each entry start_time is before its end_time
    for entry in call_sheet:
        assert entry.start_time < entry.end_time

    # Entries are in chronological order by start_time
    for i in range(len(call_sheet) - 1):
        assert call_sheet[i].start_time <= call_sheet[i + 1].start_time


# ---------------------------------------------------------------------------
# 10. Deterministic output for identical input (Gherkin Scenario 11)
# ---------------------------------------------------------------------------


def test_deterministic_output(start_time: datetime) -> None:
    """Same input twice -> identical ScheduleResult."""
    tasks = [
        ScheduleTask(id="A", name="Task A", duration=Decimal("1.0")),
        ScheduleTask(id="B", name="Task B", duration=Decimal("2.0"), dependencies=["A"]),
        ScheduleTask(id="C", name="Task C", duration=Decimal("1.5"), dependencies=["A"]),
    ]
    result_1 = compute_schedule(list(tasks), start_time)
    result_2 = compute_schedule(list(tasks), start_time)

    assert isinstance(result_1, ScheduleResult)
    assert isinstance(result_2, ScheduleResult)

    # Identical ordered_tasks
    assert [t.id for t in result_1.ordered_tasks] == [t.id for t in result_2.ordered_tasks]

    # Identical critical_path
    assert result_1.critical_path == result_2.critical_path

    # Identical earliest_start values for all tasks
    by_id_1 = {t.id: t for t in result_1.ordered_tasks}
    by_id_2 = {t.id: t for t in result_2.ordered_tasks}
    for tid in by_id_1:
        assert by_id_1[tid].earliest_start == by_id_2[tid].earliest_start


# ---------------------------------------------------------------------------
# 11. No float arithmetic in engine source
# ---------------------------------------------------------------------------


def test_no_float_arithmetic() -> None:
    """The scheduler engine must not call float() anywhere in its source."""
    import event_producer.engines.scheduler as sched_mod
    module_source = inspect.getsource(sched_mod)
    assert "float(" not in module_source, (
        "Scheduler engine contains float() calls — must use Decimal only"
    )


# ---------------------------------------------------------------------------
# 12. Pure function — no random import
# ---------------------------------------------------------------------------


def test_pure_function_no_random() -> None:
    """The scheduler engine must not import random (pure function requirement)."""
    import event_producer.engines.scheduler as sched_mod
    module_source = inspect.getsource(sched_mod)
    assert "import random" not in module_source, (
        "Scheduler engine imports random — must be a pure deterministic function"
    )
    assert "from random" not in module_source, (
        "Scheduler engine imports from random — must be a pure deterministic function"
    )


# ---------------------------------------------------------------------------
# 13. Conflict report returned (not ScheduleResult) when conflicts exist
# ---------------------------------------------------------------------------


def test_conflict_report_not_schedule_result(start_time: datetime) -> None:
    """When conflicts exist, SchedulerConflictReport is returned, not ScheduleResult."""
    # Use a cycle as the conflict trigger
    tasks = [
        ScheduleTask(id="X", name="Task X", duration=Decimal("1.0"), dependencies=["Z"]),
        ScheduleTask(id="Y", name="Task Y", duration=Decimal("1.0"), dependencies=["X"]),
        ScheduleTask(id="Z", name="Task Z", duration=Decimal("1.0"), dependencies=["Y"]),
    ]
    result = compute_schedule(tasks, start_time)

    assert isinstance(result, SchedulerConflictReport)
    assert not isinstance(result, ScheduleResult)
    assert len(result.cycle) > 0
