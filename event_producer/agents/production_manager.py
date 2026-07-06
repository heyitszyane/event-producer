"""Production Manager agent — computes run-of-show schedule via CPM.

Reason -> Formatter split:
    - ProductionManagerReasonAgent: calls compute_schedule from the CPM
      Scheduler to produce a deterministic timeline.
    - ProductionManagerFormatterAgent: validates the scheduler's output
      against the RunOfShow schema.
"""

from __future__ import annotations

from datetime import datetime, timedelta
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
# Day-of run-of-show template + vendor booking lead times
# ---------------------------------------------------------------------------

# Categories that need lead time for vendor booking (days). These are NOT
# day-of schedule rows — they become booking deadlines counted back from the
# event date. Venue is listed first with the longest lead time because it is
# usually the earliest commitment an event needs to lock.
_CATEGORY_LEAD_TIME: dict[str, Decimal] = {
    "venue": Decimal("21"),
    "catering": Decimal("7"),
    "staging": Decimal("5"),
    "av_equipment": Decimal("3"),
    "security": Decimal("3"),
}

# Scope categories whose physical setup is covered by the single combined
# "Setup & Load-In" task (they are not scheduled individually).
_SETUP_CATEGORIES: tuple[str, ...] = (
    "venue", "av_equipment", "decor", "signage", "staging",
)

# Doors open at 09:00 wall-clock on the event day; the pre-doors chain
# (setup -> tech check -> registration) is counted back from that anchor.
_DOORS_OPEN_HOUR = 9

# Program label by event type.
_PROGRAM_NAME: dict[str, str] = {
    "networking": "Networking Program",
    "conference": "Conference Sessions",
    "product_launch": "Launch Program",
    "corporate": "Main Program",
}


def _day_of_tasks(event_spec: dict, scope_items: list[dict]) -> list[ScheduleTask]:
    """Build the day-of run-of-show template.

    One combined Setup task covers all setup scope (venue prep, AV, decor,
    signage, staging); the rest is the standard arc of an event day. Users
    add rows manually when their show needs more granularity.
    """
    categories = {str(item.get("category", "")) for item in scope_items}
    setup_covered = sorted(
        cat for cat in categories if cat in _SETUP_CATEGORIES
    )
    setup_name = "Setup & Load-In"
    if setup_covered:
        pretty = ", ".join(cat.replace("_", " ").replace("av equipment", "AV") for cat in setup_covered)
        setup_name = f"Setup & Load-In ({pretty})"
    # Staging builds take longer than a standard room flip.
    setup_duration = Decimal("3") if "staging" in categories else Decimal("2")

    program_name = _PROGRAM_NAME.get(
        str(event_spec.get("event_type", "")), "Main Program"
    )
    try:
        program_duration = Decimal(str(event_spec.get("duration_hours") or "4"))
    except ArithmeticError:
        program_duration = Decimal("4")
    if program_duration <= Decimal("0"):
        program_duration = Decimal("4")

    return [
        ScheduleTask(id="setup", name=setup_name, duration=setup_duration, dependencies=[]),
        ScheduleTask(id="tech_check", name="AV & Tech Check", duration=Decimal("0.5"), dependencies=["setup"]),
        ScheduleTask(id="registration", name="Registration & Check-In Opens", duration=Decimal("0.5"), dependencies=["tech_check"]),
        ScheduleTask(id="doors_open", name="Doors Open", duration=Decimal("0.5"), dependencies=["registration"]),
        ScheduleTask(id="program", name=program_name, duration=program_duration, dependencies=["doors_open"]),
        ScheduleTask(id="strike", name="Strike & Load-Out", duration=Decimal("1.5"), dependencies=["program"]),
    ]


def _booking_deadlines(event_date: datetime, scope_items: list[dict]) -> list[dict]:
    """Derive vendor booking deadlines from scope lead times.

    Returns one entry per lead-time category present in scope: book this
    category by ``book_by`` or the vendor cannot deliver by the event date.
    """
    deadlines: list[dict] = []
    seen: set[str] = set()
    for item in scope_items:
        category = str(item.get("category", ""))
        lead = _CATEGORY_LEAD_TIME.get(category)
        if lead is None or category in seen:
            continue
        seen.add(category)
        book_by = event_date - timedelta(days=int(lead))
        deadlines.append({
            "item": str(item.get("name", category)),
            "category": category,
            "lead_time_days": int(lead),
            "book_by": book_by.date().isoformat(),
        })
    deadlines.sort(key=lambda entry: entry["book_by"])
    return deadlines


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
                - event_spec: EventSpec dict (at least 'name'; 'date' drives
                  the day-of anchor when present)
                - scope_items: list of ScopeItem dicts (at least 'name',
                  'category')
                - start_time: optional ISO datetime string; its date is used
                  only when event_spec has no usable date

        Returns:
            On success: {"schedule_result": {...}, "call_sheet": [...],
                         "booking_deadlines": [...], "explanation": str}
            On conflict: {"conflict_report": {...}, "explanation": str}
        """
        event_spec: dict = request["event_spec"]
        scope_items: list[dict] = request["scope_items"]

        # 1. Anchor the run-of-show to the event date. Naive local wall-clock
        # times by design: "doors open 09:00" means 09:00 on the event day,
        # not a UTC instant the browser shifts by timezone.
        event_date: datetime | None = None
        date_str = str(event_spec.get("date") or "").strip()
        if date_str:
            try:
                event_date = datetime.strptime(date_str, "%Y-%m-%d")
            except ValueError:
                event_date = None
        if event_date is None and request.get("start_time"):
            parsed = datetime.fromisoformat(str(request["start_time"]))
            event_date = datetime(parsed.year, parsed.month, parsed.day)
        if event_date is None:
            event_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # 2. Build the day-of template and count the pre-doors chain back
        # from the doors-open anchor so doors always open at 09:00.
        tasks = _day_of_tasks(event_spec, scope_items)
        pre_doors_hours = sum(
            (task.duration for task in tasks if task.id in ("setup", "tech_check", "registration")),
            Decimal("0"),
        )
        doors_open = event_date.replace(hour=_DOORS_OPEN_HOUR, minute=0)
        start_time = doors_open - timedelta(seconds=int(pre_doors_hours * Decimal("3600")))

        # 3. Call compute_schedule from code (NOT as an LLM tool)
        result = compute_schedule(tasks, start_time)

        # 4. Handle conflict report
        if isinstance(result, SchedulerConflictReport):
            report_dict = _conflict_report_to_dict(result)
            explanation = self._build_conflict_explanation(result, event_spec)
            return {
                "conflict_report": report_dict,
                "explanation": explanation,
            }

        # 5. Handle successful schedule
        assert isinstance(result, ScheduleResult)
        schedule_dict = _schedule_result_to_dict(result)

        # 6. Derive call sheet + vendor booking deadlines
        call_sheet_entries = derive_call_sheet(result)
        call_sheet_dicts = _call_sheet_to_dict(call_sheet_entries)
        booking_deadlines = _booking_deadlines(event_date, scope_items)

        explanation = self._build_success_explanation(result, event_spec)

        return {
            "schedule_result": schedule_dict,
            "call_sheet": call_sheet_dicts,
            "booking_deadlines": booking_deadlines,
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
        if "booking_deadlines" in raw_output:
            result["booking_deadlines"] = list(raw_output["booking_deadlines"])

        return result
