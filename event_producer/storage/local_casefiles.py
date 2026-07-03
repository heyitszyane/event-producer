"""Local file-backed event casefile persistence for P7J."""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from event_producer.models.schemas import (
    CasefileArtifact,
    CasefileNotice,
    CasefileState,
    CasefileSummary,
    EventBasics,
    ResolvedEventState,
)

_PAX_RE = re.compile(
    r"(?i)\b(\d{1,5})\s*[-]?\s*(?:pax|people|persons|guests|attendees|heads)\b"
)
_BUDGET_RE = re.compile(
    r"(?i)(?:budget(?:\s+is)?|around|about|up to|max|cap|[$\£€])\s*[:\-]?\s*"
    r"(\d[\d,]*\.?\d*)\s*(k|m|million|thousand)?"
)
_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")


def utc_now() -> str:
    """Return a stable UTC timestamp for persisted metadata."""
    return datetime.now(timezone.utc).isoformat()


def _clean(value: str | None) -> str:
    return (value or "").strip()


def _extract_expected_turnout(brief: str) -> int | None:
    match = _PAX_RE.search(brief or "")
    return int(match.group(1)) if match else None


def _extract_budget_cap(brief: str) -> Decimal | None:
    match = _BUDGET_RE.search(brief or "")
    if not match:
        return None
    value = Decimal(match.group(1).replace(",", ""))
    suffix = (match.group(2) or "").lower()
    if suffix in {"k", "thousand"}:
        value *= Decimal("1000")
    elif suffix in {"m", "million"}:
        value *= Decimal("1000000")
    return value


def _extract_start_date(brief: str) -> str:
    match = _DATE_RE.search(brief or "")
    return match.group(1) if match else ""


def _extract_city(brief: str) -> str:
    match = re.search(r"\b(?:in|at)\s+([A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\b", brief or "")
    return match.group(1) if match else ""


def resolve_event_state(
    basics: EventBasics,
    brief: str,
    *,
    user_fields: set[str] | None = None,
) -> ResolvedEventState:
    """Resolve canonical casefile state from structured basics and brief text.

    Structured casefile fields always win. Brief extraction only fills blank
    fields, and any disagreement is surfaced as a conflict notice.
    """
    user_fields = user_fields or set()
    sources: dict[str, str] = {}
    notices: list[CasefileNotice] = []
    resolved = basics.model_copy(deep=True)

    extracted_turnout = _extract_expected_turnout(brief)
    extracted_budget = _extract_budget_cap(brief)
    extracted_date = _extract_start_date(brief)
    extracted_city = _extract_city(brief)

    def source_for(field: str) -> str:
        return "user_field" if field in user_fields else "saved_casefile"

    for field in ("working_title", "country", "city", "start_date", "end_date", "event_type"):
        value = _clean(getattr(resolved, field))
        if value:
            sources[field] = source_for(field)
        else:
            sources[field] = "missing"

    if not resolved.city and extracted_city:
        resolved.city = extracted_city
        sources["city"] = "brief_extracted"
    if not resolved.start_date and extracted_date:
        resolved.start_date = extracted_date
        sources["start_date"] = "brief_extracted"
    if not resolved.end_date and resolved.start_date:
        resolved.end_date = resolved.start_date
        sources["end_date"] = sources.get("start_date", "brief_extracted")

    sources["currency"] = source_for("currency") if resolved.currency else "missing"

    if resolved.budget_cap is not None:
        sources["budget_cap"] = source_for("budget_cap")
        if extracted_budget is not None and extracted_budget != resolved.budget_cap:
            notices.append(CasefileNotice(
                type="conflict",
                field="budget_cap",
                message=(
                    f"Your brief mentions a budget of {extracted_budget}, but this "
                    f"casefile is set to {resolved.budget_cap}. Using {resolved.budget_cap}."
                ),
                brief_value=extracted_budget,
                casefile_value=resolved.budget_cap,
            ))
    elif extracted_budget is not None:
        resolved.budget_cap = extracted_budget
        sources["budget_cap"] = "brief_extracted"
    else:
        sources["budget_cap"] = "missing"
        notices.append(CasefileNotice(
            type="missing",
            field="budget_cap",
            message="Budget cap is not set yet.",
        ))

    if resolved.expected_turnout is not None:
        sources["expected_turnout"] = source_for("expected_turnout")
        if extracted_turnout is not None and extracted_turnout != resolved.expected_turnout:
            notices.append(CasefileNotice(
                type="conflict",
                field="expected_turnout",
                message=(
                    f"Your brief mentions {extracted_turnout} pax, but this casefile "
                    f"is set to {resolved.expected_turnout} pax. Using {resolved.expected_turnout} pax."
                ),
                brief_value=extracted_turnout,
                casefile_value=resolved.expected_turnout,
            ))
    elif extracted_turnout is not None:
        resolved.expected_turnout = extracted_turnout
        sources["expected_turnout"] = "brief_extracted"
    else:
        sources["expected_turnout"] = "missing"
        notices.append(CasefileNotice(
            type="missing",
            field="expected_turnout",
            message="Expected turnout is not set yet.",
        ))

    for field in ("working_title", "country", "city", "start_date", "end_date", "event_type"):
        if sources.get(field) == "missing":
            notices.append(CasefileNotice(
                type="missing",
                field=field,
                message=f"{field.replace('_', ' ').title()} is not set yet.",
            ))

    confirmed = not any(notice.type == "missing" for notice in notices)
    return ResolvedEventState(
        basics=resolved,
        sources=sources,  # type: ignore[arg-type]
        notices=notices,
        confirmed=confirmed,
    )


class LocalCasefileStore:
    """Small synchronous JSON store under ``.local_state/event_producer/events``."""

    def __init__(self, root: Path | str | None = None) -> None:
        env_root = os.environ.get("EVENT_PRODUCER_CASEFILE_ROOT")
        self.root = Path(root or env_root or ".local_state/event_producer/events")
        self.root.mkdir(parents=True, exist_ok=True)
        self._ensure_index()

    @property
    def index_path(self) -> Path:
        return self.root / "index.json"

    def create_casefile(self, basics: EventBasics, brief: str = "") -> CasefileState:
        event_id = str(uuid.uuid4())
        now = utc_now()
        state = CasefileState(
            event_id=event_id,
            created_at=now,
            updated_at=now,
            basics=basics,
            brief=brief,
            resolved=resolve_event_state(
                basics,
                brief,
                user_fields={field for field, value in basics.model_dump().items() if value not in ("", None)},
            ),
        )
        self._casefile_dir(event_id).mkdir(parents=True, exist_ok=True)
        self._artifact_dir(event_id).mkdir(parents=True, exist_ok=True)
        self._write_state(state)
        self.append_timeline(event_id, "casefile_created", {"status": state.status})
        self._write_index()
        return self.get_casefile(event_id)

    def list_casefiles(self) -> list[CasefileSummary]:
        self._ensure_index()
        summaries: list[CasefileSummary] = []
        for event_id in self._read_index():
            try:
                summaries.append(self.summary_for(self.get_casefile(event_id)))
            except FileNotFoundError:
                continue
        return sorted(summaries, key=lambda item: item.updated_at, reverse=True)

    def get_casefile(self, event_id: str) -> CasefileState:
        path = self._casefile_path(event_id)
        if not path.exists():
            raise FileNotFoundError(event_id)
        return CasefileState(**json.loads(path.read_text(encoding="utf-8")))

    def update_basics(self, event_id: str, basics: EventBasics) -> CasefileState:
        state = self.get_casefile(event_id)
        state.basics = basics
        state.resolved = resolve_event_state(
            basics,
            state.brief,
            user_fields={field for field, value in basics.model_dump().items() if value not in ("", None)},
        )
        state.updated_at = utc_now()
        self._write_state(state)
        self.append_timeline(event_id, "event_basics_updated", {"fields": list(basics.model_dump().keys())})
        self._write_index()
        return self.get_casefile(event_id)

    def update_brief(self, event_id: str, brief: str) -> CasefileState:
        state = self.get_casefile(event_id)
        state.brief = brief
        state.resolved = resolve_event_state(state.basics, brief)
        state.updated_at = utc_now()
        self._write_state(state)
        self.append_timeline(event_id, "brief_saved", {"length": len(brief)})
        self._write_index()
        return self.get_casefile(event_id)

    def mark_generated(self, event_id: str, planning_assumptions: dict[str, Any]) -> CasefileState:
        state = self.get_casefile(event_id)
        state.status = "generated"
        state.planning_assumptions = planning_assumptions
        state.updated_at = utc_now()
        self._write_state(state)
        self._write_index()
        return self.get_casefile(event_id)

    def write_artifact(self, event_id: str, name: str, payload: Any) -> CasefileArtifact:
        self._artifact_dir(event_id).mkdir(parents=True, exist_ok=True)
        path = self._artifact_dir(event_id) / f"{name}.json"
        self._write_json(path, payload)
        state = self.get_casefile(event_id)
        artifact = CasefileArtifact(
            name=name,
            path=str(path.relative_to(self._casefile_dir(event_id))),
            updated_at=utc_now(),
        )
        state.artifacts[name] = artifact
        state.updated_at = utc_now()
        self._write_state(state)
        self.append_timeline(event_id, "artifact_saved", {"name": name, "path": artifact.path})
        self._write_index()
        return artifact

    def read_artifact(self, event_id: str, name: str) -> Any:
        path = self._artifact_dir(event_id) / f"{name}.json"
        if not path.exists():
            raise FileNotFoundError(f"{event_id}/{name}")
        return json.loads(path.read_text(encoding="utf-8"))

    def append_timeline(self, event_id: str, event_type: str, payload: dict[str, Any] | None = None) -> None:
        self._casefile_dir(event_id).mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": utc_now(),
            "type": event_type,
            "payload": payload or {},
        }
        with (self._casefile_dir(event_id) / "timeline.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True, default=str) + "\n")

    def summary_for(self, state: CasefileState) -> CasefileSummary:
        basics = state.resolved.basics
        return CasefileSummary(
            event_id=state.event_id,
            working_title=basics.working_title,
            country=basics.country,
            city=basics.city,
            start_date=basics.start_date,
            end_date=basics.end_date,
            expected_turnout=basics.expected_turnout,
            updated_at=state.updated_at,
            status=state.status,
        )

    def _ensure_index(self) -> None:
        if not self.index_path.exists():
            self._write_index()

    def _read_index(self) -> list[str]:
        if not self.index_path.exists():
            return self._rebuild_index()
        data = json.loads(self.index_path.read_text(encoding="utf-8"))
        event_ids = data.get("event_ids", [])
        return [str(event_id) for event_id in event_ids]

    def _write_index(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        event_ids = self._rebuild_index()
        self._write_json(self.index_path, {"event_ids": event_ids})

    def _rebuild_index(self) -> list[str]:
        if not self.root.exists():
            return []
        event_ids = sorted(
            path.name for path in self.root.iterdir()
            if path.is_dir() and (path / "casefile.json").exists()
        )
        return event_ids

    def _write_state(self, state: CasefileState) -> None:
        self._write_json(self._casefile_path(state.event_id), state.model_dump(mode="json"))

    def _casefile_dir(self, event_id: str) -> Path:
        return self.root / event_id

    def _artifact_dir(self, event_id: str) -> Path:
        return self._casefile_dir(event_id) / "artifacts"

    def _casefile_path(self, event_id: str) -> Path:
        return self._casefile_dir(event_id) / "casefile.json"

    def _write_json(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )
        tmp.replace(path)
