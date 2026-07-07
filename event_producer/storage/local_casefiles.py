"""Local file-backed event casefile persistence for P7J."""

from __future__ import annotations

import json
import os
import re
import shutil
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
    NextBestStep,
    NextStepAction,
    RequirementField,
    RequirementsPayload,
    ResolvedEventState,
)

_PAX_RE = re.compile(
    r"(?i)\b(\d{1,5})\s*[-]?\s*(?:pax|people|persons|guests|attendees|heads)\b"
)
# Currency codes and headcount nouns that anchor / disqualify a budget amount.
_CURRENCY_CODES = "SGD|USD|EUR|GBP|MYR|AUD|JPY|INR|CAD|HKD|CNY|NZD|CHF|THB|PHP|IDR|KRW"
_PAX_NOUNS = "pax|people|persons|guests|attendees|heads|founders|investors|builders|crew"
# A budget amount must be anchored to an explicit money signal: the word
# "budget", a currency symbol, or a currency code. Soft quantifiers such as
# "around"/"about"/"up to" are deliberately NOT budget triggers on their own —
# otherwise a phrase like "around 60 guests" is misread as a budget of 60. A
# number immediately followed by a headcount noun is also rejected, and the
# amount cannot be split mid-number (the (?=\D|\Z) guard).
_BUDGET_RE = re.compile(
    r"(?i)(?:budget|[$\£€]|\b(?:" + _CURRENCY_CODES + r"))"
    r"[^.\d]{0,40}?"
    r"(\d[\d,]*\.?\d*)\s*(k|m|million|thousand)?(?=\D|\Z)"
    r"(?!\s*(?:" + _PAX_NOUNS + r"))"
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
        # Fill-only: the structured Budget Cap field is authoritative and is
        # already captured explicitly, so we do NOT re-parse the free-text brief
        # to cross-check it. Money is written too many ways ("$40k", "SGD 10,000",
        # "around ten grand") for regex extraction to be reliable enough to raise
        # a conflict on — a false "budget of 60" is worse than no notice. When the
        # user leaves the field blank we still opportunistically fill it below.
        sources["budget_cap"] = source_for("budget_cap")
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

    # Contingency % is optional with an engine default (15%); it must never
    # block confirmation. Only record a source when the user actually set it.
    if resolved.contingency_pct is not None:
        sources["contingency_pct"] = source_for("contingency_pct")

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


_REQUIREMENT_FIELD_LABELS = {
    "working_title": "Event title / working title",
    "country": "Country",
    "city": "City",
    "currency": "Currency",
    "budget_cap": "Budget cap",
    "date_range": "Date range",
    "expected_turnout": "Expected turnout",
    "event_type": "Event type",
    "event_brief": "Event brief",
}


def _source_label(source: str, *, has_conflict: bool = False) -> str:
    if has_conflict:
        return "Conflict resolved"
    if source == "brief_extracted":
        return "From event brief"
    if source == "missing":
        return "Missing"
    return "Set by you"


def _date_range_label(basics: EventBasics) -> str | None:
    if basics.start_date and basics.end_date and basics.start_date != basics.end_date:
        return f"{basics.start_date} to {basics.end_date}"
    return basics.start_date or basics.end_date or None


def build_requirements_payload(state: CasefileState) -> RequirementsPayload:
    """Return user-facing requirement rows, missing notices, and conflicts."""
    resolved = state.resolved
    basics = resolved.basics
    notices_by_field: dict[str, list[CasefileNotice]] = {}
    for notice in resolved.notices:
        notices_by_field.setdefault(notice.field, []).append(notice)

    def field_status(key: str) -> str:
        field_notices = notices_by_field.get(key, [])
        if any(notice.type == "missing" for notice in field_notices):
            return "missing"
        if any(notice.type == "conflict" for notice in field_notices):
            return "conflict"
        return "ok"

    def source_for(key: str) -> str:
        if key == "date_range":
            sources = {resolved.sources.get("start_date"), resolved.sources.get("end_date")}
            if "missing" in sources:
                return "missing"
            if "brief_extracted" in sources:
                return "brief_extracted"
            return "saved_casefile"
        return resolved.sources.get(key, "missing")

    rows: list[RequirementField] = []
    for key, value in (
        ("working_title", basics.working_title or None),
        ("country", basics.country or None),
        ("city", basics.city or None),
        ("currency", basics.currency or None),
        ("budget_cap", basics.budget_cap),
        ("date_range", _date_range_label(basics)),
        ("expected_turnout", basics.expected_turnout),
        ("event_type", basics.event_type or None),
    ):
        status = field_status(key)
        if key == "date_range" and (
            field_status("start_date") == "missing" or field_status("end_date") == "missing"
        ):
            status = "missing"
        rows.append(RequirementField(
            key=key,
            label=_REQUIREMENT_FIELD_LABELS[key],
            value=value,
            source_label=_source_label(source_for(key), has_conflict=status == "conflict"),
            status=status,  # type: ignore[arg-type]
        ))

    brief_value = "Saved" if state.brief.strip() else "Not saved"
    rows.append(RequirementField(
        key="event_brief",
        label=_REQUIREMENT_FIELD_LABELS["event_brief"],
        value=brief_value,
        source_label="Set by you" if state.brief.strip() else "Missing",
        status="ok" if state.brief.strip() else "missing",
    ))

    return RequirementsPayload(
        confirmed=state.status == "requirements_confirmed",
        confirmed_at=state.requirements_confirmed_at,
        confirmed_by=state.requirements_confirmed_by,
        fields=rows,
        missing=[notice for notice in resolved.notices if notice.type == "missing"],
        conflicts=[notice for notice in resolved.notices if notice.type == "conflict"],
    )


def build_next_best_step(state: CasefileState) -> NextBestStep:
    """Derive the next user action from canonical casefile state."""
    requirements = build_requirements_payload(state)
    missing_fields = [field for field in requirements.fields if field.status == "missing"]
    if missing_fields:
        first_missing = missing_fields[0]
        return NextBestStep(
            state="missing_requirements",
            primary=NextStepAction(
                id="complete_event_basics",
                label="Complete event basics",
                target="brief",
                kind="primary",
                reason=f"{first_missing.label} is not set.",
            ),
            secondary=[
                NextStepAction(
                    id=f"add_{field.key}",
                    label=f"Add {field.label.lower()}",
                    target="brief",
                    kind="secondary",
                    reason=field.source_label,
                )
                for field in missing_fields[:2]
            ],
            rationale="Budget and run sheet quality depend on complete event basics.",
        )

    if requirements.conflicts and state.status != "requirements_confirmed":
        return NextBestStep(
            state="review_notices",
            primary=NextStepAction(
                id="review_requirement_notices",
                label="Review requirement notices",
                target="brief",
                kind="primary",
                reason="The event brief and saved basics disagree.",
            ),
            secondary=[
                NextStepAction(
                    id="edit_event_basics",
                    label="Edit event basics",
                    target="brief",
                    kind="secondary",
                    reason="Update saved fields if the brief should win.",
                ),
                NextStepAction(
                    id="confirm_requirements",
                    label="Confirm requirements",
                    target="brief",
                    kind="secondary",
                    reason="Keep the saved fields and retain the notice.",
                ),
            ],
            rationale="Review the visible notices before confirming the casefile facts.",
        )

    if state.status != "requirements_confirmed":
        return NextBestStep(
            state="generated_unconfirmed" if state.status == "generated" else "draft_unconfirmed",
            primary=NextStepAction(
                id="confirm_requirements",
                label="Confirm requirements",
                target="brief",
                kind="primary",
                reason="The casefile has enough basics to proceed.",
            ),
            secondary=[
                NextStepAction(
                    id="edit_event_basics",
                    label="Edit event basics",
                    target="brief",
                    kind="secondary",
                    reason="Adjust facts before confirming.",
                )
            ],
            rationale="Confirm the casefile facts before asking specialist agents to refine outputs.",
        )

    if "creative-concept" not in state.artifacts:
        return NextBestStep(
            state="confirmed_needs_generation",
            primary=NextStepAction(
                id="generate_concept",
                label="Generate concept",
                target="brief",
                kind="primary",
                reason="No creative concept is saved for this casefile yet.",
            ),
            rationale="Run the production crew now that requirements are confirmed.",
        )

    if "scope-strategy" not in state.artifacts:
        return NextBestStep(
            state="confirmed_needs_scope_strategy",
            primary=NextStepAction(
                id="generate_scope_strategy",
                label="Generate scope strategy",
                target="ai-crew",
                kind="primary",
                reason="Scope strategy has not been saved yet.",
            ),
            rationale="Use the specialist board to refine scope after the first concept.",
        )

    if "vendor-copy" not in state.artifacts:
        return NextBestStep(
            state="confirmed_needs_vendor_copy",
            primary=NextStepAction(
                id="draft_vendor_copy",
                label="Draft vendor copy",
                target="ai-crew",
                kind="primary",
                reason="Vendor copy is not saved for this casefile yet.",
            ),
            secondary=[
                NextStepAction(
                    id="review_budget_fit",
                    label="Review budget fit",
                    target="budget",
                    kind="secondary",
                    reason="Check budget health before vendor outreach.",
                )
            ],
            rationale="Use the direct Vendor Copy Agent to create a draft artifact before any gated outreach.",
        )

    return NextBestStep(
        state="ready_for_review",
        primary=NextStepAction(
            id="review_vendor_draft",
            label="Review vendor draft",
            target="vendors",
            kind="primary",
            reason="Requirements and core artifacts are saved.",
        ),
        secondary=[
            NextStepAction(
                id="run_risk_review",
                label="Run risk review",
                target="risks",
                kind="secondary",
                reason="Check unresolved operational risks.",
            )
        ],
        rationale="The casefile is ready for human review and gated vendor workflow.",
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

    def create_casefile(
        self, basics: EventBasics, brief: str = "", event_id: str | None = None
    ) -> CasefileState:
        # A caller may supply a stable id (e.g. seed demos) so the casefile is
        # reproducible across clones; otherwise a fresh UUID is minted.
        event_id = event_id or str(uuid.uuid4())
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

    def delete_casefile(self, event_id: str) -> None:
        """Remove a casefile directory (state, artifacts, timeline) from disk.

        Raises ``FileNotFoundError`` if the casefile does not exist so callers
        can surface a 404. The index is rebuilt from the surviving directories.
        Seed casefiles can be re-created afterwards via ``ensure_demo_casefiles``.
        """
        if not self._casefile_path(event_id).exists():
            raise FileNotFoundError(event_id)
        shutil.rmtree(self._casefile_dir(event_id), ignore_errors=True)
        self._write_index()

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
        return self._enrich_state(CasefileState(**json.loads(path.read_text(encoding="utf-8"))))

    def update_basics(self, event_id: str, basics: EventBasics) -> CasefileState:
        state = self.get_casefile(event_id)
        state.basics = basics
        state.resolved = resolve_event_state(
            basics,
            state.brief,
            user_fields={field for field, value in basics.model_dump().items() if value not in ("", None)},
        )
        if state.status == "requirements_confirmed":
            state.status = "generated" if state.artifacts else "draft"
        state.requirements_confirmed_at = None
        state.requirements_confirmed_by = None
        state.updated_at = utc_now()
        self._write_state(state)
        self.append_timeline(event_id, "event_basics_updated", {"fields": list(basics.model_dump().keys())})
        self._write_index()
        return self.get_casefile(event_id)

    def update_brief(self, event_id: str, brief: str) -> CasefileState:
        state = self.get_casefile(event_id)
        state.brief = brief
        state.resolved = resolve_event_state(state.basics, brief)
        if state.status == "requirements_confirmed":
            state.status = "generated" if state.artifacts else "draft"
        state.requirements_confirmed_at = None
        state.requirements_confirmed_by = None
        state.updated_at = utc_now()
        self._write_state(state)
        self.append_timeline(event_id, "brief_saved", {"length": len(brief)})
        self._write_index()
        return self.get_casefile(event_id)

    def mark_generated(self, event_id: str, planning_assumptions: dict[str, Any]) -> CasefileState:
        state = self.get_casefile(event_id)
        if state.status != "requirements_confirmed":
            state.status = "generated"
        state.planning_assumptions = {
            **(state.planning_assumptions or {}),
            **planning_assumptions,
        }
        state.updated_at = utc_now()
        self._write_state(state)
        self._write_index()
        return self.get_casefile(event_id)

    def dismiss_market_realism_warning(self, event_id: str, warning: str) -> CasefileState:
        """Persist a user-dismissed budget realism advisory for a casefile."""
        state = self.get_casefile(event_id)
        planning = dict(state.planning_assumptions or {})
        dismissed = [
            str(item)
            for item in planning.get("dismissed_market_realism_warnings", [])
            if str(item).strip()
        ]
        if warning not in dismissed:
            dismissed.append(warning)
        planning["dismissed_market_realism_warnings"] = dismissed
        state.planning_assumptions = planning
        state.updated_at = utc_now()
        self._write_state(state)
        self.append_timeline(event_id, "market_realism_warning_dismissed", {"warning": warning})
        self._write_index()
        return self.get_casefile(event_id)

    def update_run_sheet_task_status(
        self,
        event_id: str,
        task_id: str,
        *,
        status: str,
        notes: str | None = None,
    ) -> CasefileState:
        """Persist operator status/notes for a generated run-of-show task."""
        state = self.get_casefile(event_id)
        planning = dict(state.planning_assumptions or {})
        overrides = {
            str(key): dict(value)
            for key, value in (planning.get("run_sheet_task_overrides") or {}).items()
            if isinstance(value, dict)
        }
        current = dict(overrides.get(task_id, {}))
        current["status"] = status
        if notes is not None:
            current["notes"] = notes
        current["updated_at"] = utc_now()
        overrides[task_id] = current
        planning["run_sheet_task_overrides"] = overrides
        state.planning_assumptions = planning
        state.updated_at = utc_now()
        self._write_state(state)
        self.append_timeline(
            event_id,
            "run_sheet_task_status_updated",
            {"task_id": task_id, "status": status},
        )
        self._write_index()
        return self.get_casefile(event_id)

    def confirm_requirements(self, event_id: str, actor: str = "demo-user") -> CasefileState:
        state = self.get_casefile(event_id)
        now = utc_now()
        state.status = "requirements_confirmed"
        state.requirements_confirmed_at = now
        state.requirements_confirmed_by = actor
        state.updated_at = now
        self._write_state(state)
        self.append_timeline(event_id, "requirements_confirmed", {"actor": actor})
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
        self._write_json(
            self._casefile_path(state.event_id),
            self._enrich_state(state).model_dump(mode="json"),
        )

    def _enrich_state(self, state: CasefileState) -> CasefileState:
        # Resolved state (and its conflict/missing notices) is derived purely
        # from basics + brief, so recompute it on every load. This self-heals
        # casefiles persisted by an older extractor — otherwise a stale notice
        # (e.g. a since-fixed budget mis-read) lingers until the next edit.
        state.resolved = resolve_event_state(
            state.basics,
            state.brief,
            user_fields={
                field
                for field, value in state.basics.model_dump().items()
                if value not in ("", None)
            },
        )
        state.requirements = build_requirements_payload(state)
        state.next_step = build_next_best_step(state)
        return state

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
