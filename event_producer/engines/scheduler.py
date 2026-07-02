"""CPM Scheduler — deterministic core for event run-of-show timeline.

All duration arithmetic uses ``Decimal`` hours converted to ``timedelta`` via
integer seconds — never float. The engine is a pure function: no I/O, no global
state, no randomness, no time dependence beyond the supplied ``start_time``.

Invariants:
  - Tasks are topologically ordered; cycles are detected and reported.
  - Forward pass computes earliest_start / earliest_finish respecting
    dependencies, lead times, and fixed anchors.
  - Backward pass computes latest_start / latest_finish.
  - Critical path = tasks with zero slack (earliest_start == latest_start).
  - Lead-time violations and anchor conflicts are collected and returned in a
    ``SchedulerConflictReport`` when present.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta
from decimal import Decimal

from event_producer.models.schemas import (
    CallSheetEntry,
    Conflict,
    ScheduleResult,
    ScheduleTask,
    ScheduledTask,
    SchedulerConflictReport,
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_ZERO = Decimal("0")


def _hours_to_timedelta(hours: Decimal) -> timedelta:
    """Convert Decimal hours to timedelta via integer seconds (no float)."""
    return timedelta(seconds=int(hours * Decimal("3600")))


def _days_to_timedelta(days: Decimal) -> timedelta:
    """Convert Decimal days to timedelta via integer seconds (no float)."""
    return timedelta(seconds=int(days * Decimal("86400")))


# ---------------------------------------------------------------------------
# Cycle detection (DFS with path reconstruction)
# ---------------------------------------------------------------------------

def _detect_cycle(
    tasks_by_id: dict[str, ScheduleTask],
) -> list[str] | None:
    """Return a cycle path if one exists, otherwise None.

    Uses iterative DFS with three-color marking. Returns the task IDs forming
    the cycle in order, or None if the graph is acyclic.
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {tid: WHITE for tid in tasks_by_id}
    parent: dict[str, str | None] = {tid: None for tid in tasks_by_id}

    # Deterministic: visit in sorted ID order
    for start_id in sorted(tasks_by_id.keys()):
        if color[start_id] != WHITE:
            continue

        stack: list[tuple[str, int]] = [(start_id, 0)]  # (node, dep_index)
        path: list[str] = []

        while stack:
            node, idx = stack[-1]

            if color[node] == WHITE:
                color[node] = GRAY
                path.append(node)

            deps = tasks_by_id[node].dependencies
            if idx < len(deps):
                stack[-1] = (node, idx + 1)
                neighbor = deps[idx]
                if neighbor not in tasks_by_id:
                    # Missing dependency — skip (not a cycle, will be handled
                    # by topological sort as a dangling edge)
                    continue
                if color[neighbor] == GRAY:
                    # Found cycle — extract the cycle from the path
                    cycle_start = path.index(neighbor)
                    return path[cycle_start:]
                elif color[neighbor] == WHITE:
                    parent[neighbor] = node
                    stack.append((neighbor, 0))
            else:
                color[node] = BLACK
                path.pop()
                stack.pop()

    return None


# ---------------------------------------------------------------------------
# Topological sort (Kahn's algorithm, deterministic tie-breaking by ID)
# ---------------------------------------------------------------------------

def _topological_sort(
    tasks_by_id: dict[str, ScheduleTask],
) -> list[str] | None:
    """Return topologically sorted task IDs, or None if a cycle exists.

    Uses Kahn's algorithm with a sorted queue for deterministic tie-breaking.
    """
    # Build adjacency and in-degree
    in_degree: dict[str, int] = {tid: 0 for tid in tasks_by_id}
    successors: dict[str, list[str]] = {tid: [] for tid in tasks_by_id}

    for tid, task in tasks_by_id.items():
        for dep in task.dependencies:
            if dep in tasks_by_id:
                in_degree[tid] += 1
                successors[dep].append(tid)

    # Start with zero in-degree nodes, sorted by ID for determinism
    queue: deque[str] = deque(sorted(tid for tid, deg in in_degree.items() if deg == 0))
    result: list[str] = []

    while queue:
        node = queue.popleft()
        result.append(node)
        for succ in sorted(successors[node]):
            in_degree[succ] -= 1
            if in_degree[succ] == 0:
                queue.append(succ)

    if len(result) != len(tasks_by_id):
        return None  # cycle detected

    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_schedule(
    tasks: list[ScheduleTask],
    start_time: datetime,
) -> ScheduleResult | SchedulerConflictReport:
    """Compute a CPM schedule from a list of tasks.

    Pure function: deterministic, no I/O, no global state. Returns a
    ``ScheduleResult`` with the ordered timeline and critical path if the
    schedule is feasible, or a ``SchedulerConflictReport`` if cycles,
    lead-time violations, or anchor conflicts are detected.

    Args:
        tasks: List of ScheduleTask objects with dependencies, durations,
            optional lead_times, and optional anchors.
        start_time: The project start time. Used as the earliest start for
            root tasks (those with no dependencies and no anchor).

    Returns:
        ``ScheduleResult`` or ``SchedulerConflictReport``.
    """
    # -- Handle empty task list ---------------------------------------------
    if not tasks:
        return ScheduleResult(ordered_tasks=[], critical_path=[])

    # -- Duplicate task ID validation ----------------------------------------
    seen_ids: set[str] = set()
    dupes: list[str] = []
    for t in tasks:
        if t.id in seen_ids:
            dupes.append(t.id)
        seen_ids.add(t.id)
    if dupes:
        return SchedulerConflictReport(
            cycle=[],
            lead_time_conflicts=[],
            anchor_conflicts=[
                Conflict(task_id=d, conflict_type="duplicate_id",
                         message=f"Duplicate task ID '{d}' detected")
                for d in dupes
            ],
        )

    # -- Build lookup --------------------------------------------------------
    tasks_by_id: dict[str, ScheduleTask] = {t.id: t for t in tasks}

    # -- Missing dependency validation ---------------------------------------
    missing_deps = sorted({dep for task in tasks for dep in task.dependencies if dep not in tasks_by_id})
    if missing_deps:
        return SchedulerConflictReport(
            cycle=[],
            lead_time_conflicts=[],
            anchor_conflicts=[
                Conflict(task_id="", conflict_type="missing_dependency",
                         message=f"Dependency ID '{d}' not found in task list")
                for d in missing_deps
            ],
        )

    # -- Step 1: Cycle detection ---------------------------------------------
    cycle = _detect_cycle(tasks_by_id)
    if cycle is not None:
        return SchedulerConflictReport(
            cycle=cycle,
            lead_time_conflicts=[],
            anchor_conflicts=[],
        )

    # -- Step 2: Topological sort --------------------------------------------
    topo_order = _topological_sort(tasks_by_id)
    if topo_order is None:
        # Should not happen since we already checked for cycles, but guard anyway
        return SchedulerConflictReport(
            cycle=list(tasks_by_id.keys()),
            lead_time_conflicts=[],
            anchor_conflicts=[],
        )

    # -- Step 3: Forward pass ------------------------------------------------
    earliest_start: dict[str, datetime] = {}
    earliest_finish: dict[str, datetime] = {}

    for tid in topo_order:
        task = tasks_by_id[tid]
        duration_td = _hours_to_timedelta(task.duration)

        # Start after all predecessors finish, plus this task's required lead
        # time when it has one.
        pred_finishes: list[datetime] = []
        lead_td = (
            _days_to_timedelta(task.lead_time)
            if task.lead_time is not None and task.lead_time > _ZERO
            else timedelta()
        )
        for dep_id in task.dependencies:
            if dep_id in earliest_finish:
                pred_finishes.append(earliest_finish[dep_id] + lead_td)

        if pred_finishes:
            dep_es = max(pred_finishes)
        else:
            dep_es = start_time

        if task.anchor is not None:
            # Anchored tasks have a fixed wall-clock start; if dependencies
            # push beyond it, that's an anchor conflict (detected later)
            es = max(task.anchor, dep_es)
        else:
            es = dep_es

        earliest_start[tid] = es
        earliest_finish[tid] = es + duration_td

    # -- Step 4: Backward pass -----------------------------------------------
    latest_start: dict[str, datetime] = {}
    latest_finish: dict[str, datetime] = {}

    # Build successors map
    successors: dict[str, list[str]] = {tid: [] for tid in tasks_by_id}
    for tid, task in tasks_by_id.items():
        for dep in task.dependencies:
            if dep in tasks_by_id:
                successors[dep].append(tid)

    # Project end = max earliest_finish across all tasks.
    # Terminal (non-anchored) tasks use this as their latest_finish so that
    # only tasks on the longest path have zero slack.
    project_end = max(earliest_finish.values())

    for tid in reversed(topo_order):
        task = tasks_by_id[tid]
        duration_td = _hours_to_timedelta(task.duration)

        if task.anchor is not None:
            # Anchored tasks have fixed finish = anchor + duration
            lf = task.anchor + duration_td
        else:
            succ_starts: list[datetime] = []
            for succ_id in successors[tid]:
                if succ_id in latest_start:
                    succ = tasks_by_id[succ_id]
                    succ_lead_td = (
                        _days_to_timedelta(succ.lead_time)
                        if succ.lead_time is not None and succ.lead_time > _ZERO
                        else timedelta()
                    )
                    succ_starts.append(latest_start[succ_id] - succ_lead_td)

            if succ_starts:
                lf = min(succ_starts)
            else:
                lf = project_end

        latest_finish[tid] = lf
        latest_start[tid] = lf - duration_td

    # -- Step 5: Lead-time check ---------------------------------------------
    lead_time_conflicts: list[Conflict] = []
    for tid in topo_order:
        task = tasks_by_id[tid]
        if task.lead_time is not None and task.lead_time > _ZERO:
            lead_td = _days_to_timedelta(task.lead_time)
            for dep_id in task.dependencies:
                if dep_id in earliest_finish:
                    required_start = earliest_finish[dep_id] + lead_td
                    if earliest_start[tid] < required_start:
                        lead_time_conflicts.append(
                            Conflict(
                                task_id=tid,
                                conflict_type="lead_time",
                                message=(
                                    f"Task '{tid}' violates lead time: "
                                    f"earliest_start {earliest_start[tid]} is before "
                                    f"dependency '{dep_id}' finish {earliest_finish[dep_id]} "
                                    f"+ lead time {task.lead_time} days"
                                ),
                            )
                        )

    # -- Step 6: Anchor conflict check ---------------------------------------
    anchor_conflicts: list[Conflict] = []
    for tid in topo_order:
        task = tasks_by_id[tid]
        if task.anchor is not None:
            if earliest_start[tid] != task.anchor:
                anchor_conflicts.append(
                    Conflict(
                        task_id=tid,
                        conflict_type="anchor",
                        message=(
                            f"Task '{tid}' anchor conflict: anchor is "
                            f"{task.anchor} but earliest_start was computed as "
                            f"{earliest_start[tid]}"
                        ),
                    )
                )

    # -- If conflicts found, return report -----------------------------------
    if lead_time_conflicts or anchor_conflicts:
        return SchedulerConflictReport(
            lead_time_conflicts=lead_time_conflicts,
            anchor_conflicts=anchor_conflicts,
            cycle=[],
        )

    # -- Step 7: Critical path -----------------------------------------------
    critical_path: list[str] = [
        tid for tid in topo_order
        if earliest_start[tid] == latest_start[tid]
    ]

    # -- Build ScheduledTask list --------------------------------------------
    ordered_tasks: list[ScheduledTask] = []
    for tid in topo_order:
        task = tasks_by_id[tid]
        ordered_tasks.append(
            ScheduledTask(
                id=task.id,
                name=task.name,
                duration=task.duration,
                dependencies=task.dependencies,
                lead_time=task.lead_time,
                anchor=task.anchor,
                earliest_start=earliest_start[tid],
                earliest_finish=earliest_finish[tid],
                latest_start=latest_start[tid],
                latest_finish=latest_finish[tid],
            )
        )

    return ScheduleResult(
        ordered_tasks=ordered_tasks,
        critical_path=critical_path,
    )


def derive_call_sheet(result: ScheduleResult) -> list[CallSheetEntry]:
    """Derive a chronologically ordered call sheet from a ScheduleResult.

    Args:
        result: A valid ScheduleResult from compute_schedule.

    Returns:
        List of CallSheetEntry objects sorted by start_time.
    """
    entries: list[CallSheetEntry] = [
        CallSheetEntry(
            task_name=task.name,
            start_time=task.earliest_start,
            end_time=task.earliest_finish,
            is_anchor=task.anchor is not None,
        )
        for task in result.ordered_tasks
    ]
    entries.sort(key=lambda entry: entry.start_time)
    return entries
