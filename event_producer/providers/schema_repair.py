"""Small deterministic repairs for live-model structured output.

These repairs are deliberately conservative. They only normalize values already
present in provider output or in the original prompt text, and they run before
Pydantic validation so harmless provider shape drift does not trigger fallback.
"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from pydantic import BaseModel

from event_producer.models.schemas import (
    BriefIntakeResult,
    CreativeConceptResult,
    OrchestratorAgentResult,
    ScopeStrategyResult,
    VendorDraftResult,
)


class SchemaRepairResult(BaseModel):
    """Repaired JSON object plus non-secret repair diagnostics."""

    data: dict[str, Any]
    repaired_schema: bool = False
    repaired_fields: list[str] = []


_BRIEF_NONE_FIELDS = (
    "tone",
    "audience_profile",
    "venue_type",
    "date",
    "location",
    "event_type_raw",
)
_BRIEF_LIST_FIELDS = (
    "assumptions",
    "missing_questions",
    "contradictions",
    "market_realism_warnings",
    "goals",
    "must_haves",
    "nice_to_haves",
    "constraints",
)
_CREATIVE_LIST_FIELDS = (
    "event_title_options",
    "experience_principles",
    "creative_ideas",
    "suggested_additions",
    "suggested_cuts_or_reductions",
    "budget_sensitive_notes",
    "production_risks",
    "sponsor_or_partner_hooks",
)
_SCOPE_LIST_FIELDS = (
    "must_have_logic",
    "tradeoffs",
    "recommendations",
    "questions_for_user",
)
_VENDOR_LIST_FIELDS = ("required_vendor_response_fields", "risk_notes")
_ORCHESTRATOR_LIST_FIELDS = ("proposals", "risk_notes")


def repair_schema_output(
    *,
    schema: type[BaseModel],
    agent_name: str,
    original_user_prompt: str,
    decoded_json: dict[str, Any],
) -> SchemaRepairResult:
    """Return a safely repaired object for known live-agent schemas."""
    data = deepcopy(decoded_json)
    repaired_fields: list[str] = []

    if schema is BriefIntakeResult or agent_name == "brief_intake":
        _repair_brief(data, original_user_prompt, repaired_fields)
    elif schema is CreativeConceptResult or agent_name == "creative_concept":
        _repair_creative(data, repaired_fields)
    elif schema is ScopeStrategyResult or agent_name == "scope_strategy":
        _repair_scope_strategy(data, repaired_fields)
    elif schema is VendorDraftResult or agent_name == "vendor_draft":
        _repair_vendor_draft(data, repaired_fields)
    elif schema is OrchestratorAgentResult or agent_name == "orchestrator":
        _repair_orchestrator(data, repaired_fields)

    return SchemaRepairResult(
        data=data,
        repaired_schema=bool(repaired_fields),
        repaired_fields=repaired_fields,
    )


def _mark(fields: list[str], name: str) -> None:
    if name not in fields:
        fields.append(name)


def _set_missing(data: dict[str, Any], field: str, value: Any, fields: list[str]) -> None:
    if field not in data or data[field] is None:
        data[field] = value
        _mark(fields, field)


def _stringify_present(data: dict[str, Any], field: str, fields: list[str]) -> None:
    value = data.get(field)
    if isinstance(value, (int, float)):
        data[field] = str(value)
        _mark(fields, field)


def _stringify_required_present(data: dict[str, Any], field: str, fields: list[str]) -> None:
    value = data.get(field)
    if value is not None and not isinstance(value, str):
        data[field] = _stable_string(value)
        _mark(fields, field)


def _ensure_list(data: dict[str, Any], field: str, fields: list[str]) -> None:
    if field not in data or data[field] is None:
        data[field] = []
        _mark(fields, field)
        return
    if not isinstance(data[field], list):
        data[field] = [_stable_string(data[field])]
        _mark(fields, field)
        return
    repaired = [item if isinstance(item, str) else _stable_string(item) for item in data[field]]
    if repaired != data[field]:
        data[field] = repaired
        _mark(fields, field)


def _ensure_object_list(data: dict[str, Any], field: str, fields: list[str]) -> None:
    if field not in data or data[field] is None:
        data[field] = []
        _mark(fields, field)
    elif not isinstance(data[field], list):
        data[field] = []
        _mark(fields, field)


def _stable_string(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    if isinstance(value, list):
        return json.dumps(value, sort_keys=True, separators=(",", ":"))
    return str(value)


def _repair_brief(data: dict[str, Any], original_user_prompt: str, fields: list[str]) -> None:
    if not isinstance(data.get("normalized_brief"), str):
        data["normalized_brief"] = original_user_prompt.strip()[:1000]
        _mark(fields, "normalized_brief")
    if "event_type" not in data:
        data["event_type"] = ""
        _mark(fields, "event_type")
    _stringify_present(data, "budget_cap", fields)
    _stringify_present(data, "contingency_pct", fields)
    for field in _BRIEF_NONE_FIELDS:
        _set_missing(data, field, None, fields)
    for field in _BRIEF_LIST_FIELDS:
        _ensure_list(data, field, fields)


def _repair_creative(data: dict[str, Any], fields: list[str]) -> None:
    _stringify_required_present(data, "concept_summary", fields)
    for field in _CREATIVE_LIST_FIELDS:
        if field in {"creative_ideas", "suggested_additions", "suggested_cuts_or_reductions"}:
            _ensure_object_list(data, field, fields)
        else:
            _ensure_list(data, field, fields)
    for field in ("suggested_additions", "suggested_cuts_or_reductions"):
        for item in data.get(field, []):
            if isinstance(item, dict):
                _stringify_present(item, "estimated_cost", fields)


def _repair_scope_strategy(data: dict[str, Any], fields: list[str]) -> None:
    _stringify_required_present(data, "strategy_summary", fields)
    for field in _SCOPE_LIST_FIELDS:
        if field == "recommendations":
            _ensure_object_list(data, field, fields)
        else:
            _ensure_list(data, field, fields)


def _repair_vendor_draft(data: dict[str, Any], fields: list[str]) -> None:
    for field in ("subject", "body", "ask_summary", "approval_diff"):
        _stringify_required_present(data, field, fields)
    for field in _VENDOR_LIST_FIELDS:
        _ensure_list(data, field, fields)


def _repair_orchestrator(data: dict[str, Any], fields: list[str]) -> None:
    for field in ("reply", "rationale_summary"):
        _stringify_required_present(data, field, fields)
    _ensure_object_list(data, "proposals", fields)
    _ensure_list(data, "risk_notes", fields)
