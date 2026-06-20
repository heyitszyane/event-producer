"""Production Manager agent — computes run-of-show schedule via CPM.

Reason -> Formatter split:
    - ProductionManagerReasonAgent: calls compute_schedule from the CPM
      Scheduler to produce a deterministic timeline.
    - ProductionManagerFormatterAgent: validates the scheduler's output
      against the RunOfShow schema.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from event_producer.engines.scheduler import compute_schedule, derive_call_sheet
from event_producer.models.schemas import (
    CallSheetEntry,
    ScheduleResult,
    ScheduleTask,
    SchedulerConflictReport,
    ScheduledTask,
)

if TYPE_CHECKING:
    from event_producer.providers.event_store import EventStore


# ---------------------------------------------------------------------------
# Category -> duration (hours) and dependency mapping
# ---------------------------------------------------------------------------

_CATEGORY_DURATION: dict[str, Decimal] = {
    "venue": Decimal("4"),
    "catering": Decimal("2"),
    "av_equipment": Decimal("3"),
    "staffing": Decimal("1"),
    "decor": Decimal("2"),
    "security": Decimal("1"),
    "staging": Decimal("4"),
    "registration": Decimal("1"),
    "signage": Decimal("1"),
}

_CATEGORY_DEPENDENCIES: dict[str, list[str]] = {
    "catering": ["venue"],
    "av_equipment": ["venue"],
    "decor": ["venue"],
    "staffing": ["venue"],
}

# Categories that need lead time for vendor booking (days)
_CATEGORY_LEAD_TIME: dict[str, Decimal] = {
    "catering": Decimal("7"),
    "av_equipment": Decimal("3"),
    "staging": Decimal("5"),
    "security": Decimal("3"),
}


def _scope_item_to_schedule_task(
    item: dict,
    scope_items_by_name: dict[str, dict],
) -> ScheduleTask:
    """Convert a scope item dict to a ScheduleTask.

    Args:
        item: Scope item dict with at least 'name' and 'category' keys.
        scope_items_by_name: Lookup of all scope items by name for resolving
            dependency names to IDs.

    Returns:
        A ScheduleTask ready for the CPM scheduler.
    """
    name: str = item["name"]
    category: str = item.get("category", "")
    task_id: str = category if category else name.lower().replace(" ", "_")

    duration: Decimal = _CATEGORY_DURATION.get(category, Decimal("1"))

    # Resolve dependency names to task IDs
    dep_names: list[str] = _CATEGORY_DEPENDENCIES.get(category, [])
    dep_ids: list[str] = []
    for dep_name in dep_names:
        # The dependency name IS the category key, which is used as the task ID
        if dep_name in scope_items_by_name or dep_name in _CATEGORY_DURATION:
            dep_ids.append(dep_name)

    lead_time: Decimal | None = _CATEGORY_LEAD_TIME.get(category)

    return ScheduleTask(
        id=task_id,
        name=name,
        duration=duration,
        dependencies=dep_ids,
        lead_time=lead_time,
    )


def _schedule_result_to_dict(result: ScheduleResult) -> dict:
    """Convert a ScheduleResult Pydantic model to a plain dict."""
    return {
        "ordered_tasks": [
            {
                "id": t.id,
                "name": t.name,
                "duration": t.duration,
                "dependencies": t.dependencies,
                "lead_time": t.lead_time,
                "anchor": t.anchor,
                "earliest_start": t.earliest_start,
                "earliest_finish": t.earliest_finish,
                "latest_start": t.latest_start,
                "latest_finish": t.latest_finish,
            }
            for t in result.ordered_tasks
        ],
        "critical_path": result.critical_path,
    }


def _conflict_report_to_dict(report: SchedulerConflictReport) -> dict:
    """Convert a SchedulerConflictReport Pydantic model to a plain dict."""
    return {
        "lead_time_conflicts": [
            {
                "task_id": c.task_id,
                "conflict_type": c.conflict_type,
                "message": c.message,
            }
            for c in report.lead_time_conflicts
        ],
        "anchor_conflicts": [
            {
                "task_id": c.task_id,
                "conflict_type": c.conflict_type,
                "message": c.message,
            }
            for c in report.anchor_conflicts
        ],
        "cycle": report.cycle,
    }


def _call_sheet_to_dict(entries: list[CallSheetEntry]) -> list[dict]:
    """Convert a list of CallSheetEntry models to plain dicts."""
    return [
        {
            "task_name": e.task_name,
            "start_time": e.start_time,
            "end_time": e.end_time,
            "is_anchor": e.is_anchor,
        }
        for e in entries
    ]


# ---------------------------------------------------------------------------
# Reason Agent
# ---------------------------------------------------------------------------

class ProductionManagerReasonAgent:
    """Reasoning agent that computes the event run-of-show schedule.

    Delegates the actual scheduling to the deterministic CPM Scheduler
    (compute_schedule). The reason agent is responsible for gathering
    the required inputs (tasks with dependencies, durations, lead times)
    and invoking the engine from code — never as an LLM tool.
    """

    def __init__(self, event_store: EventStore) -> None:
        """Initialize the production reason agent.

        Args:
            event_store: Abstract event store interface.
        """
        self._event_store = event_store

    def run(self, request: dict) -> dict:
        """Compute the schedule by calling compute_schedule from code.

        Args:
            request: Request dict containing:
                - event_spec: EventSpec dict (at least 'name', 'date')
                - scope_items: list of ScopeItem dicts (at least 'name',
                  'category')
                - start_time: ISO datetime string for project start

        Returns:
            On success: {"schedule_result": {...}, "call_sheet": [...],
                         "explanation": str}
            On conflict: {"conflict_report": {...}, "explanation": str}
        """
        event_spec: dict = request["event_spec"]
        scope_items: list[dict] = request["scope_items"]
        start_time_str: str = request["start_time"]

        # 1. Parse start_time
        start_time: datetime = datetime.fromisoformat(start_time_str)

        # 2. Build scope items lookup by category for dependency resolution
        scope_items_by_name: dict[str, dict] = {}
        for item in scope_items:
            cat = item.get("category", "")
            if cat:
                scope_items_by_name[cat] = item
            scope_items_by_name[item["name"]] = item

        # 3. Convert scope items to ScheduleTask objects
        tasks: list[ScheduleTask] = [
            _scope_item_to_schedule_task(item, scope_items_by_name)
            for item in scope_items
        ]

        # 4. Call compute_schedule from code (NOT as an LLM tool)
        result = compute_schedule(tasks, start_time)

        # 5. Handle conflict report
        if isinstance(result, SchedulerConflictReport):
            report_dict = _conflict_report_to_dict(result)
            explanation = self._build_conflict_explanation(result, event_spec)
            return {
                "conflict_report": report_dict,
                "explanation": explanation,
            }

        # 6. Handle successful schedule
        assert isinstance(result, ScheduleResult)
        schedule_dict = _schedule_result_to_dict(result)

        # 7. Derive call sheet from the schedule
        call_sheet_entries = derive_call_sheet(result)
        call_sheet_dicts = _call_sheet_to_dict(call_sheet_entries)

        explanation = self._build_success_explanation(result, event_spec)

        return {
            "schedule_result": schedule_dict,
            "call_sheet": call_sheet_dicts,
            "explanation": explanation,
        }

    @staticmethod
    def _build_success_explanation(
        result: ScheduleResult, event_spec: dict
    ) -> str:
        """Build a human-readable explanation of the computed schedule."""
        event_name: str = event_spec.get("name", "the event")
        task_count = len(result.ordered_tasks)
        critical = ", ".join(result.critical_path) if result.critical_path else "none"

        lines = [
            f"Schedule computed for '{event_name}': "
            f"{task_count} tasks, critical path: [{critical}].",
        ]
        for task in result.ordered_tasks:
            lines.append(
                f"  - {task.name}: {task.earliest_start} -> {task.earliest_finish}"
            )
        return "\n".join(lines)

    @staticmethod
    def _build_conflict_explanation(
        report: SchedulerConflictReport, event_spec: dict
    ) -> str:
        """Build a human-readable explanation of scheduling conflicts."""
        event_name: str = event_spec.get("name", "the event")
        parts = [f"Schedule conflict detected for '{event_name}':"]
        if report.cycle:
            parts.append(f"  Cycle detected: {' -> '.join(report.cycle)}")
        for c in report.lead_time_conflicts:
            parts.append(f"  Lead-time conflict on '{c.task_id}': {c.message}")
        for c in report.anchor_conflicts:
            parts.append(f"  Anchor conflict on '{c.task_id}': {c.message}")
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# Formatter Agent
# ---------------------------------------------------------------------------

class ProductionManagerFormatterAgent:
    """Formatter agent that validates scheduler output against RunOfShow.

    Ensures the engine output conforms to the ScheduleResult / CallSheetEntry
    Pydantic schemas. This agent ONLY validates — no engine calls.
    """

    def __init__(self) -> None:
        """Initialize the production formatter agent (no dependencies)."""

    def run(self, raw_output: dict) -> dict:
        """Validate the scheduler output against the expected schemas.

        Args:
            raw_output: The ProductionManagerReasonAgent output to validate.
                May contain 'schedule_result' and 'call_sheet' keys (success
                path) or 'conflict_report' key (conflict path).

        Returns:
            A validated dict with Pydantic-model-backed data.

        Raises:
            pydantic.ValidationError: If the data does not conform to the
                expected schemas.
        """
        if "conflict_report" in raw_output:
            # Conflict path — no schedule_result or call_sheet to validate
            return {
                "conflict_report": raw_output["conflict_report"],
                "explanation": raw_output.get("explanation", ""),
            }

        # Validate schedule_result
        schedule_raw = raw_output.get("schedule_result")
        if schedule_raw is not None:
            # Re-validate through Pydantic to ensure strict conformance
            ordered_tasks = [
                ScheduledTask(**t) for t in schedule_raw.get("ordered_tasks", [])
            ]
            schedule_result = ScheduleResult(
                ordered_tasks=ordered_tasks,
                critical_path=schedule_raw.get("critical_path", []),
            )
        else:
            schedule_result = None

        # Validate call_sheet entries
        call_sheet_raw = raw_output.get("call_sheet", [])
        call_sheet = [CallSheetEntry(**entry) for entry in call_sheet_raw]

        result: dict = {
            "explanation": raw_output.get("explanation", ""),
        }
        if schedule_result is not None:
            result["schedule_result"] = schedule_result
        if call_sheet:
            result["call_sheet"] = call_sheet

        return result
