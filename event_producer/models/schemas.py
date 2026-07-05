"""Typed Pydantic contracts for the Budget Engine and CPM Scheduler.

All monetary/time fields use Decimal — never float. Every model runs in strict
mode so that float-to-Decimal coercion is rejected at the boundary.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ISO_4217_ALLOWLIST: frozenset[str] = frozenset({
    "USD", "EUR", "GBP", "SGD", "THB", "MYR", "IDR",
    "PHP", "VND", "JPY", "KRW", "AUD", "CNY",
})

_TIER_LITERAL = Literal["must", "should", "could", "wow"]

# P7A — agent / model mode taxonomy used across the crew trace.
AgentMode = Literal[
    "gemini_live",
    "openai_compatible_live",
    "rule_based_fallback",
    "deterministic_engine",
    "scripted_fixture",
    "human_approval_gate",
    "not_enabled",
]

CasefileSource = Literal["user_field", "saved_casefile", "brief_extracted", "missing", "demo_seed"]
CasefileNoticeType = Literal["missing", "conflict", "info"]
RequirementFieldStatus = Literal["ok", "missing", "conflict"]
NextStepActionKind = Literal["primary", "secondary"]

_AGENT_STATUS = Literal[
    "complete",
    "warning",
    "blocked",
    "pending_approval",
    "error",
]


# ---------------------------------------------------------------------------
# Validators (reusable helpers)
# ---------------------------------------------------------------------------

def _reject_float(field_name: str, value) -> None:
    """Raise if value is a float — strict Decimal-only enforcement."""
    if isinstance(value, float):
        raise TypeError(
            f"{field_name} must be a Decimal, not float. "
            f"Use Decimal('...') string literals instead."
        )


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class FxRate(BaseModel):
    """Exchange rate between two currencies."""

    model_config = ConfigDict(strict=True)

    base: str
    quote: str
    rate: Decimal

    @field_validator("base", "quote")
    @classmethod
    def validate_currency_code(cls, v: str, info) -> str:
        if len(v) != 3 or v.upper() != v:
            raise ValueError(
                f"{info.field_name} must be a 3-letter uppercase ISO 4217 code"
            )
        if v not in ISO_4217_ALLOWLIST:
            raise ValueError(
                f"{info.field_name} '{v}' is not in the supported currency allowlist"
            )
        return v

    @field_validator("rate")
    @classmethod
    def validate_rate(cls, v: Decimal, info) -> Decimal:
        _reject_float(info.field_name, v)
        if v <= 0:
            raise ValueError(f"{info.field_name} must be positive")
        return v


class BudgetLine(BaseModel):
    """A single budget line item."""

    model_config = ConfigDict(strict=True)

    label: str
    qty: Decimal
    unit_cost: Decimal
    currency: str
    category: str
    tier: _TIER_LITERAL

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str, info) -> str:
        if len(v) != 3 or v.upper() != v:
            raise ValueError(
                f"{info.field_name} must be a 3-letter uppercase ISO 4217 code"
            )
        if v not in ISO_4217_ALLOWLIST:
            raise ValueError(
                f"{info.field_name} '{v}' is not in the supported currency allowlist"
            )
        return v

    @field_validator("qty")
    @classmethod
    def validate_qty(cls, v: Decimal, info) -> Decimal:
        _reject_float(info.field_name, v)
        if v <= 0:
            raise ValueError(f"{info.field_name} must be > 0")
        return v

    @field_validator("unit_cost")
    @classmethod
    def validate_unit_cost(cls, v: Decimal, info) -> Decimal:
        _reject_float(info.field_name, v)
        if v < 0:
            raise ValueError(f"{info.field_name} must be >= 0")
        return v


class BudgetVariance(BaseModel):
    """Variance tracking between planned and actual spend."""

    model_config = ConfigDict(strict=True)

    receipt_vs_plan: dict[str, Decimal] = Field(default_factory=dict)
    running_burn: Decimal = Decimal("0.00")
    projected_total: Decimal = Decimal("0.00")
    projected_over_under: Decimal = Decimal("0.00")
    burn_rate: Decimal = Decimal("0.00")

    @field_validator(
        "running_burn", "projected_total", "projected_over_under", "burn_rate"
    )
    @classmethod
    def validate_decimals(cls, v: Decimal, info) -> Decimal:
        _reject_float(info.field_name, v)
        return v


class BudgetSummary(BaseModel):
    """Reconciled budget summary produced by the Budget Engine."""

    model_config = ConfigDict(strict=True)

    lines: list[BudgetLine]
    category_rollups: dict[str, Decimal]
    tier_rollups: dict[str, Decimal]
    budget_cap: Decimal
    contingency_pct: Decimal
    contingency_reserve: Decimal
    spendable: Decimal
    included_totals: Decimal
    headroom: Decimal
    tier_inclusion: dict[str, bool]
    over_budget: bool
    under_budget: bool
    variance: BudgetVariance

    @field_validator(
        "budget_cap", "contingency_pct", "contingency_reserve", "spendable",
        "included_totals", "headroom",
    )
    @classmethod
    def validate_decimals(cls, v: Decimal, info) -> Decimal:
        _reject_float(info.field_name, v)
        return v


class BudgetInput(BaseModel):
    """Input to the Budget Engine."""

    model_config = ConfigDict(strict=True)

    lines: list[BudgetLine]
    budget_cap: Decimal
    contingency_pct: Decimal

    @field_validator("budget_cap", "contingency_pct")
    @classmethod
    def validate_decimals(cls, v: Decimal, info) -> Decimal:
        _reject_float(info.field_name, v)
        return v


class Receipt(BaseModel):
    """A vendor receipt tied to a budget line item."""

    model_config = ConfigDict(strict=True)

    vendor: str
    amount: Decimal
    currency: str
    line_item_label: str

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str, info) -> str:
        if len(v) != 3 or v.upper() != v:
            raise ValueError(
                f"{info.field_name} must be a 3-letter uppercase ISO 4217 code"
            )
        if v not in ISO_4217_ALLOWLIST:
            raise ValueError(
                f"{info.field_name} '{v}' is not in the supported currency allowlist"
            )
        return v

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Decimal, info) -> Decimal:
        _reject_float(info.field_name, v)
        return v


# ---------------------------------------------------------------------------
# CPM Scheduler Models
# ---------------------------------------------------------------------------

class ScheduleTask(BaseModel):
    """Input model for a single task in the CPM Scheduler."""

    model_config = ConfigDict(strict=True)

    id: str
    name: str
    duration: Decimal
    dependencies: list[str] = Field(default_factory=list)
    lead_time: Decimal | None = None
    anchor: datetime | None = None

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} must be a non-empty string")
        return v

    @field_validator("duration")
    @classmethod
    def validate_duration(cls, v: Decimal, info) -> Decimal:
        _reject_float(info.field_name, v)
        if v <= 0:
            raise ValueError(f"{info.field_name} must be > 0")
        return v

    @field_validator("lead_time")
    @classmethod
    def validate_lead_time(cls, v: Decimal | None, info) -> Decimal | None:
        if v is not None:
            _reject_float(info.field_name, v)
            if v < 0:
                raise ValueError(f"{info.field_name} must be >= 0")
        return v


class ScheduledTask(BaseModel):
    """A ScheduleTask with computed scheduling fields."""

    model_config = ConfigDict(strict=True)

    id: str
    name: str
    duration: Decimal
    dependencies: list[str] = Field(default_factory=list)
    lead_time: Decimal | None = None
    anchor: datetime | None = None
    earliest_start: datetime
    earliest_finish: datetime
    latest_start: datetime
    latest_finish: datetime

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} must be a non-empty string")
        return v

    @field_validator("duration")
    @classmethod
    def validate_duration(cls, v: Decimal, info) -> Decimal:
        _reject_float(info.field_name, v)
        if v <= 0:
            raise ValueError(f"{info.field_name} must be > 0")
        return v

    @field_validator("lead_time")
    @classmethod
    def validate_lead_time(cls, v: Decimal | None, info) -> Decimal | None:
        if v is not None:
            _reject_float(info.field_name, v)
            if v < 0:
                raise ValueError(f"{info.field_name} must be >= 0")
        return v


class ScheduleResult(BaseModel):
    """Successful schedule output from the CPM Scheduler."""

    model_config = ConfigDict(strict=True)

    ordered_tasks: list[ScheduledTask]
    critical_path: list[str]


class Conflict(BaseModel):
    """Individual scheduling conflict entry."""

    model_config = ConfigDict(strict=True)

    task_id: str
    conflict_type: Literal["lead_time", "anchor", "cycle", "missing_dependency", "duplicate_id"]
    message: str


class SchedulerConflictReport(BaseModel):
    """Conflict report returned when the scheduler detects infeasibilities."""

    model_config = ConfigDict(strict=True)

    lead_time_conflicts: list[Conflict] = Field(default_factory=list)
    anchor_conflicts: list[Conflict] = Field(default_factory=list)
    cycle: list[str] = Field(default_factory=list)


class CallSheetEntry(BaseModel):
    """A single entry in a derived call sheet."""

    model_config = ConfigDict(strict=True)

    task_name: str
    start_time: datetime
    end_time: datetime
    is_anchor: bool


# ---------------------------------------------------------------------------
# P3 — Event Spec, Scope, Vendor, Task, Risk, Approval, Run-of-Show
# ---------------------------------------------------------------------------

class EventSpec(BaseModel):
    """Parsed event brief produced by the configurator agent."""

    model_config = ConfigDict(strict=True)

    name: str
    description: str
    event_type: str
    attendees: int
    venue_type: str
    duration_hours: Decimal
    date: str
    missing_fields: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} must be a non-empty string")
        return v

    @field_validator("attendees")
    @classmethod
    def validate_attendees(cls, v: int, info) -> int:
        if v <= 0:
            raise ValueError(f"{info.field_name} must be > 0")
        return v

    @field_validator("duration_hours")
    @classmethod
    def validate_duration_hours(cls, v: Decimal, info) -> Decimal:
        _reject_float(info.field_name, v)
        if v <= 0:
            raise ValueError(f"{info.field_name} must be > 0")
        return v

    @field_validator("date")
    @classmethod
    def validate_date(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} must be a non-empty string")
        # Validate ISO date format YYYY-MM-DD
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError(
                f"{info.field_name} must be a valid ISO date string (YYYY-MM-DD)"
            )
        return v


class ScopeItem(BaseModel):
    """A single scope item proposed for the event."""

    model_config = ConfigDict(strict=True)

    name: str
    description: str
    category: str
    tier: _TIER_LITERAL
    estimated_cost: Decimal
    currency: str
    qty: Decimal = Decimal("1")
    selected: bool = False

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} must be a non-empty string")
        return v

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str, info) -> str:
        if len(v) != 3 or v.upper() != v:
            raise ValueError(
                f"{info.field_name} must be a 3-letter uppercase ISO 4217 code"
            )
        if v not in ISO_4217_ALLOWLIST:
            raise ValueError(
                f"{info.field_name} '{v}' is not in the supported currency allowlist"
            )
        return v

    @field_validator("estimated_cost")
    @classmethod
    def validate_estimated_cost(cls, v: Decimal, info) -> Decimal:
        _reject_float(info.field_name, v)
        if v < 0:
            raise ValueError(f"{info.field_name} must be >= 0")
        return v

    @field_validator("qty")
    @classmethod
    def validate_qty(cls, v: Decimal, info) -> Decimal:
        _reject_float(info.field_name, v)
        if v <= 0:
            raise ValueError(f"{info.field_name} must be > 0")
        return v


class Vendor(BaseModel):
    """A vendor record."""

    model_config = ConfigDict(strict=True)

    id: str
    name: str
    category: str
    contact_email: str = ""
    contact_phone: str = ""
    rating: Decimal = Decimal("0.00")
    notes: str = ""

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} must be a non-empty string")
        return v

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, v: Decimal, info) -> Decimal:
        _reject_float(info.field_name, v)
        if v < 0 or v > 5:
            raise ValueError(f"{info.field_name} must be between 0 and 5")
        return v


class VendorMessage(BaseModel):
    """A message from/to a vendor."""

    model_config = ConfigDict(strict=True)

    vendor_id: str
    direction: Literal["inbound", "outbound"]
    channel: str
    body: str
    timestamp: str = ""
    is_quarantined: bool = False
    injection_flags: list[str] = Field(default_factory=list)

    @field_validator("vendor_id")
    @classmethod
    def validate_vendor_id(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} must be a non-empty string")
        return v

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: str, info) -> str:
        if v:
            try:
                datetime.fromisoformat(v)
            except ValueError:
                raise ValueError(
                    f"{info.field_name} must be a valid ISO datetime string"
                )
        return v


class Task(BaseModel):
    """An action item."""

    model_config = ConfigDict(strict=True)

    id: str
    title: str
    description: str = ""
    assigned_to: str = ""
    status: Literal["pending", "in_progress", "done", "blocked"] = "pending"
    due_date: str = ""
    priority: Literal["low", "medium", "high"] = "medium"

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} must be a non-empty string")
        return v

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} must be a non-empty string")
        return v

    @field_validator("due_date")
    @classmethod
    def validate_due_date(cls, v: str, info) -> str:
        if v:
            try:
                datetime.strptime(v, "%Y-%m-%d")
            except ValueError:
                raise ValueError(
                    f"{info.field_name} must be a valid ISO date string (YYYY-MM-DD)"
                )
        return v


class RiskFlag(BaseModel):
    """A risk or gap identified by the Risk/Gap Flagger."""

    model_config = ConfigDict(strict=True)

    id: str
    category: Literal["budget", "schedule", "vendor", "security", "coverage", "compliance"]
    severity: Literal["info", "warning", "critical"]
    message: str
    related_items: list[str] = Field(default_factory=list)
    resolved: bool = False

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} must be a non-empty string")
        return v

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} must be a non-empty string")
        return v


class Approval(BaseModel):
    """A human approval record for the action-gate."""

    model_config = ConfigDict(strict=True)

    id: str
    action: str
    requested_by: str
    approved_by: str = ""
    status: Literal["pending", "approved", "rejected"] = "pending"
    timestamp: str = ""
    notes: str = ""

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} must be a non-empty string")
        return v

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} must be a non-empty string")
        return v

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: str, info) -> str:
        if v:
            try:
                datetime.fromisoformat(v)
            except ValueError:
                raise ValueError(
                    f"{info.field_name} must be a valid ISO datetime string"
                )
        return v


class RunOfShow(BaseModel):
    """The full run-of-show output tying together all planning artifacts."""

    model_config = ConfigDict(strict=True)

    event_spec: EventSpec
    scope_items: list[ScopeItem]
    budget_summary: BudgetSummary
    schedule_result: ScheduleResult | None = None
    call_sheet: list[CallSheetEntry] = Field(default_factory=list)
    vendors: list[Vendor] = Field(default_factory=list)
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    approvals: list[Approval] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# P6D — Agent Trace
# ---------------------------------------------------------------------------

class AgentTraceStep(BaseModel):
    """A single step in the agent crew trace.

    This is a structural trace of actual rule-based role-agent steps, plus
    (P7A) the surface used by the live/fallback AI intake agents. It is NOT a
    verbatim LLM reasoning transcript. The P7A fields are optional with safe
    defaults so older serialized traces and existing call sites behave
    unchanged.
    """

    model_config = ConfigDict(strict=True)

    id: str
    role: str
    label: str
    status: _AGENT_STATUS = "complete"
    input_summary: str
    output_summary: str
    artifacts: list[str] = Field(default_factory=list)
    deterministic_core: str | None = None
    approval_required: bool = False

    # --- P7A: model-mode telemetry (optional, safe defaults) ----------------
    """Which model surface actually produced this step's output."""
    model_mode: AgentMode = "rule_based_fallback"
    """Concrete model id/name reported by the provider, when known."""
    model_name: str | None = None
    """Prompt asset version used by the agent (e.g. "brief_intake.v1")."""
    prompt_version: str | None = None
    """If the provider did NOT run a live model call, why."""
    fallback_reason: str | None = None
    """Agent-reported confidence in its extraction/signal ("high"/"medium"/"low" or None)."""
    confidence: str | None = None


class ChatLogMessage(BaseModel):
    """A single message in the production chat log."""

    model_config = ConfigDict(strict=True)

    role: str
    content: str
    agent: str = ""


# ---------------------------------------------------------------------------
# P7A — AI intake + creative concept typed results
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# P7D — Requirement source tracking for provenance display
# ---------------------------------------------------------------------------

RequirementSource = Literal["brief_extracted", "manual_override", "fallback_default", "missing"]

class ManualConstraintFlags(BaseModel):
    """Which optional request fields should be treated as user overrides.

    This preserves legacy compatibility while letting the UI send inactive
    placeholder values without turning them into real constraints.
    """

    model_config = ConfigDict(extra="ignore", strict=False)

    budget_cap: bool = False
    contingency_pct: bool = False
    attendees: bool = False
    event_type: bool = False
    venue_type: bool = False
    date: bool = False


class BriefIntakeSourceMap(BaseModel):
    """P7D: Source tracking for each extracted field.

    This allows the UI to show where each value came from:
    - brief_extracted: parsed directly from the user's brief text
    - manual_override: user explicitly provided this value
    - fallback_default: server-side default used (engine requirement)
    - missing: no value available, needs follow-up
    """

    model_config = ConfigDict(extra="ignore", strict=False)

    attendees: RequirementSource = "brief_extracted"
    budget_cap: RequirementSource = "brief_extracted"
    contingency_pct: RequirementSource = "brief_extracted"
    date: RequirementSource = "brief_extracted"
    event_type: RequirementSource = "brief_extracted"
    venue_type: RequirementSource = "brief_extracted"
    location: RequirementSource = "brief_extracted"


class BriefIntakeResult(BaseModel):
    """Output of the Brief Intake Agent.

    The agent extracts a structured picture from a messy human brief. It NEVER
    invents money-critical or schedule-critical values silently; missing or
    uncertain information is surfaced via ``missing_questions``,
    ``assumptions``, and ``confidence`` instead. Budget/schedule math is left to
    the deterministic engines.

    P7D addition: ``source_map`` tracks where each value originated for honest
    display of brief extraction vs. manual overrides vs. fallback defaults.
    """

    # tolerate model-supplied extra/verbose keys rather than dropping the whole
    # parse; the structured fields are what we render.
    model_config = ConfigDict(extra="ignore", strict=False)

    normalized_brief: str
    event_type: str
    event_type_raw: str | None = None
    attendees: int | None = None
    budget_cap: str | None = None
    contingency_pct: str | None = None
    venue_type: str | None = None
    date: str | None = None
    location: str | None = None
    goals: list[str] = Field(default_factory=list)
    audience_profile: str | None = None
    tone: str | None = None
    must_haves: list[str] = Field(default_factory=list)
    nice_to_haves: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    missing_questions: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    market_realism_warnings: list[str] = Field(default_factory=list)
    confidence: str = "low"
    model_mode: AgentMode = "rule_based_fallback"
    # P7D: source map for provenance display
    source_map: BriefIntakeSourceMap | None = None


class CreativeIdea(BaseModel):
    """A single creative experience idea for the event."""

    model_config = ConfigDict(extra="ignore", strict=False)

    title: str
    description: str
    tier: _TIER_LITERAL = "could"
    estimated_complexity: Literal["low", "medium", "high"] = "medium"
    budget_pressure: Literal["low", "medium", "high"] = "medium"
    why_it_fits: str


class CreativeScopeSuggestion(BaseModel):
    """A proposal to add / cut / reduce / reconsider a scope element."""

    model_config = ConfigDict(extra="forbid", strict=False)

    title: str
    description: str
    category: str
    tier: _TIER_LITERAL = "could"
    estimated_cost: str | None = None
    budget_pressure: Literal["low", "medium", "high"] = "medium"
    action_hint: Literal["add", "cut", "reduce", "reconsider"] = "add"
    rationale: str

    @field_validator("category", "title", "description", "rationale")
    @classmethod
    def _non_empty(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} must be a non-empty string")
        return v


class CreativeConceptResult(BaseModel):
    """Output of the Creative Concept Agent (P7A: advisory only).

    These are PROPOSALS. In P7A they do not mutate scope/budget/schedule.
    P7B applies them to editable scope through a user-confirmed action.
    """

    model_config = ConfigDict(extra="ignore", strict=False)

    event_title_options: list[str] = Field(default_factory=list)
    concept_summary: str = ""
    experience_principles: list[str] = Field(default_factory=list)
    creative_ideas: list[CreativeIdea] = Field(default_factory=list)
    suggested_additions: list[CreativeScopeSuggestion] = Field(default_factory=list)
    suggested_cuts_or_reductions: list[CreativeScopeSuggestion] = Field(
        default_factory=list
    )
    budget_sensitive_notes: list[str] = Field(default_factory=list)
    production_risks: list[str] = Field(default_factory=list)
    sponsor_or_partner_hooks: list[str] = Field(default_factory=list)
    model_mode: AgentMode = "rule_based_fallback"


class ScopeStrategyRecommendation(BaseModel):
    """Advisory scope strategy recommendation from the live/fallback strategist."""

    model_config = ConfigDict(extra="ignore", strict=False)

    title: str
    recommendation_type: Literal["add", "cut", "reduce", "retier", "keep", "clarify"]
    category: str
    tier: _TIER_LITERAL = "could"
    rationale: str
    budget_pressure: Literal["low", "medium", "high"] = "medium"
    operational_risk: Literal["low", "medium", "high"] = "medium"
    proposed_scope_item: dict | None = None


class ScopeStrategyResult(BaseModel):
    """Live/fallback strategy layer that advises before deterministic engines run."""

    model_config = ConfigDict(extra="ignore", strict=False)

    strategy_summary: str = ""
    must_have_logic: list[str] = Field(default_factory=list)
    tradeoffs: list[str] = Field(default_factory=list)
    recommendations: list[ScopeStrategyRecommendation] = Field(default_factory=list)
    questions_for_user: list[str] = Field(default_factory=list)
    model_mode: AgentMode = "rule_based_fallback"
    fallback_reason: str | None = None


class VendorDraftResult(BaseModel):
    """Draft-only vendor-facing copy that still requires human approval."""

    model_config = ConfigDict(extra="ignore", strict=False)

    subject: str
    body: str
    ask_summary: str
    required_vendor_response_fields: list[str] = Field(default_factory=list)
    approval_diff: str
    risk_notes: list[str] = Field(default_factory=list)
    model_mode: AgentMode = "rule_based_fallback"
    fallback_reason: str | None = None


class VendorCopyDraft(BaseModel):
    """Reviewable vendor-copy artifact prepared for manual external use."""

    model_config = ConfigDict(extra="ignore", strict=False)

    subject: str = ""
    body: str = ""
    ask_summary: str = ""
    required_vendor_response_fields: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    review_status: Literal["draft", "reviewed"] = "draft"
    generated_at: str | None = None
    updated_at: str | None = None
    source_agent: str = "vendor_copy"
    model_mode: AgentMode | None = None
    fallback_reason: str | None = None


# ---------------------------------------------------------------------------
# P7A — request / response additions
# ------------------------------------------------------------------------------


class RunEventRequest(BaseModel):
    """P7A extended request body for ``POST /run``.

    Kept intentionally compatible with the existing API contract: all the
    legacy structured fields keep their meaning but are now optional at the
    schema layer (with server-side resolution / fallback). ``brief`` becomes the
    primary input and is the only required field. Explicit user-provided
    constraint fields win over model extraction; the AI only fills gaps.
    """

    model_config = ConfigDict(extra="ignore", strict=False)

    brief: str
    budget_cap: str | None = None
    contingency_pct: str | None = None
    attendees: int | None = None
    event_type: str | None = None
    venue_type: str | None = None
    date: str | None = None
    manual_constraints: ManualConstraintFlags | None = None


# ---------------------------------------------------------------------------
# P7J — local casefile state truth
# ---------------------------------------------------------------------------


class EventBasics(BaseModel):
    """User-editable canonical basics for a saved event casefile."""

    model_config = ConfigDict(extra="ignore", strict=False)

    working_title: str = ""
    country: str = ""
    city: str = ""
    currency: str = "USD"
    budget_cap: Decimal | None = None
    contingency_pct: Decimal | None = None
    start_date: str = ""
    end_date: str = ""
    expected_turnout: int | None = None
    event_type: str = ""

    @field_validator("currency")
    @classmethod
    def validate_casefile_currency(cls, v: str, info) -> str:
        value = (v or "USD").upper()
        if len(value) != 3:
            raise ValueError(f"{info.field_name} must be a 3-letter uppercase ISO 4217 code")
        if value not in ISO_4217_ALLOWLIST:
            raise ValueError(f"{info.field_name} '{value}' is not in the supported currency allowlist")
        return value

    @field_validator("budget_cap")
    @classmethod
    def validate_casefile_budget_cap(cls, v: Decimal | None, info) -> Decimal | None:
        if v is not None:
            _reject_float(info.field_name, v)
            if v <= 0:
                raise ValueError(f"{info.field_name} must be > 0")
        return v

    @field_validator("contingency_pct")
    @classmethod
    def validate_casefile_contingency_pct(cls, v: Decimal | None, info) -> Decimal | None:
        if v is not None:
            _reject_float(info.field_name, v)
            if v < 0 or v > 100:
                raise ValueError(f"{info.field_name} must be between 0 and 100")
        return v

    @field_validator("expected_turnout")
    @classmethod
    def validate_expected_turnout(cls, v: int | None, info) -> int | None:
        if v is not None and v <= 0:
            raise ValueError(f"{info.field_name} must be > 0")
        return v


class CasefileNotice(BaseModel):
    """Missing/conflict/info notice surfaced with resolved casefile state."""

    model_config = ConfigDict(extra="ignore", strict=False)

    type: CasefileNoticeType
    field: str
    message: str
    brief_value: str | int | Decimal | None = None
    casefile_value: str | int | Decimal | None = None


class ResolvedEventState(BaseModel):
    """Canonical resolved casefile state used by top-level UI surfaces."""

    model_config = ConfigDict(extra="ignore", strict=False)

    basics: EventBasics
    sources: dict[str, CasefileSource]
    notices: list[CasefileNotice] = Field(default_factory=list)
    confirmed: bool = False


class RequirementField(BaseModel):
    """User-facing requirement row derived from canonical casefile state."""

    model_config = ConfigDict(extra="ignore", strict=False)

    key: str
    label: str
    value: str | int | Decimal | None = None
    source_label: str
    status: RequirementFieldStatus = "ok"


class RequirementsPayload(BaseModel):
    """Structured confirmation payload for the frontend requirements panel."""

    model_config = ConfigDict(extra="ignore", strict=False)

    confirmed: bool = False
    confirmed_at: str | None = None
    confirmed_by: str | None = None
    fields: list[RequirementField] = Field(default_factory=list)
    missing: list[CasefileNotice] = Field(default_factory=list)
    conflicts: list[CasefileNotice] = Field(default_factory=list)


class NextStepAction(BaseModel):
    """Single next-step action the UI can route to a known section."""

    model_config = ConfigDict(extra="ignore", strict=False)

    id: str
    label: str
    target: str
    kind: NextStepActionKind
    reason: str = ""
    disabled: bool = False


class NextBestStep(BaseModel):
    """Backend-derived workflow guidance for the current casefile state."""

    model_config = ConfigDict(extra="ignore", strict=False)

    state: str
    primary: NextStepAction
    secondary: list[NextStepAction] = Field(default_factory=list)
    rationale: str = ""


class CasefileArtifact(BaseModel):
    """Metadata for a JSON artifact stored under a casefile directory."""

    model_config = ConfigDict(extra="ignore", strict=False)

    name: str
    path: str
    updated_at: str


class CasefileState(BaseModel):
    """File-backed event casefile persisted before agent generation."""

    model_config = ConfigDict(extra="ignore", strict=False)

    event_id: str
    created_at: str
    updated_at: str
    basics: EventBasics
    brief: str = ""
    resolved: ResolvedEventState
    status: Literal["draft", "generated", "requirements_confirmed"] = "draft"
    requirements_confirmed_at: str | None = None
    requirements_confirmed_by: str | None = None
    requirements: RequirementsPayload | None = None
    next_step: NextBestStep | None = None
    artifacts: dict[str, CasefileArtifact] = Field(default_factory=dict)
    planning_assumptions: dict[str, Any] = Field(default_factory=dict)


class CasefileSummary(BaseModel):
    """List-view projection for saved local casefiles."""

    model_config = ConfigDict(extra="ignore", strict=False)

    event_id: str
    working_title: str
    country: str
    city: str
    start_date: str
    end_date: str
    expected_turnout: int | None = None
    updated_at: str
    status: Literal["draft", "generated", "requirements_confirmed"] = "draft"


SpecialistAgentId = Literal[
    "creative_concept",
    "scope_strategy",
    "vendor_copy",
    "risk_review",
]


class SpecialistAgentRequest(BaseModel):
    """Direct saved-casefile specialist action request."""

    model_config = ConfigDict(extra="ignore", strict=False)

    instruction: str = ""
    regenerate: bool = False
    artifact_id: str | None = None


class SpecialistAgentResponse(BaseModel):
    """Saved artifact response for a direct specialist action."""

    model_config = ConfigDict(extra="ignore", strict=False)

    event_id: str
    agent_id: SpecialistAgentId
    artifact: CasefileArtifact
    output: dict[str, Any]
    model_mode: AgentMode
    fallback_reason: str | None = None
    notices: list[CasefileNotice] = Field(default_factory=list)
    next_step: NextBestStep | None = None


# ---------------------------------------------------------------------------
# P7B — scope mutation + orchestrator action schemas
# ---------------------------------------------------------------------------

class ScopeItemCreate(BaseModel):
    """Schema for creating a new scope item via API.

    Uses strict=False for string coercion from JSON, then validates
    monetary fields are Decimal (not float).
    """

    model_config = ConfigDict(strict=False)

    name: str
    description: str = ""
    category: str
    tier: _TIER_LITERAL = "could"
    qty: Decimal = Decimal("1")
    estimated_cost: Decimal
    currency: str = "USD"
    selected: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} must be a non-empty string")
        return v

    @field_validator("estimated_cost", "qty")
    @classmethod
    def validate_decimals(cls, v: Decimal, info) -> Decimal:
        # String to Decimal coercion already happened; just validate
        if v < Decimal("0"):
            raise ValueError(f"{info.field_name} must be >= 0")
        return v


class ScopeItemUpdate(BaseModel):
    """Schema for updating an existing scope item via API.

    Uses strict=False for string coercion from JSON for monetary fields.
    """

    model_config = ConfigDict(strict=False)

    name: str | None = None
    description: str | None = None
    category: str | None = None
    tier: _TIER_LITERAL | None = None
    qty: Decimal | None = None
    estimated_cost: Decimal | None = None
    currency: str | None = None
    selected: bool | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None, info) -> str | None:
        if v is not None and not v.strip():
            raise ValueError(f"{info.field_name} must be a non-empty string if provided")
        return v

    @field_validator("estimated_cost", "qty")
    @classmethod
    def validate_decimals(cls, v: Decimal | None, info) -> Decimal | None:
        if v is not None and v < Decimal("0"):
            raise ValueError(f"{info.field_name} must be >= 0")
        return v


class ProposedAction(BaseModel):
    """A proposed action returned by the orchestrator (not yet applied).

    Actions NEVER mutate state directly. The user must click Apply before
    any change occurs. Vendor/payment actions route through the action-gate.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    id: str
    type: Literal["add_scope_item", "update_scope_item", "delete_scope_item",
                   "retier_scope_item", "toggle_scope_item", "add_risk_flag",
                   "request_clarification", "create_approval"]
    title: str
    rationale: str
    payload: dict
    requires_confirmation: bool = True
    requires_approval_gate: bool = False
    model_mode: AgentMode = "rule_based_fallback"
    created_at: str = ""

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} must be a non-empty string")
        return v


class Proposal(BaseModel):
    """A stored proposal object that can be applied or dismissed."""

    model_config = ConfigDict(extra="forbid", strict=True)

    id: str
    event_id: str
    source_agent: str = "orchestrator"
    title: str
    rationale: str
    proposed_actions: list[ProposedAction]
    status: Literal["pending", "applied", "dismissed"] = "pending"
    created_at: str = ""
    model_mode: AgentMode = "rule_based_fallback"
    fallback_reason: str | None = None

    @field_validator("id", "event_id", "title", "rationale")
    @classmethod
    def validate_non_empty(cls, v: str, info) -> str:
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} must be a non-empty string")
        return v


class OrchestratorChatResponse(BaseModel):
    """Response from the orchestrator chat endpoint."""

    model_config = ConfigDict(extra="ignore", strict=False)

    reply: str
    proposals: list[ProposedAction] = Field(default_factory=list)
    model_mode: AgentMode = "rule_based_fallback"
    fallback_reason: str | None = None


class OrchestratorAgentResult(BaseModel):
    """Live/fallback orchestrator model output before API storage.

    The model may include extra explanatory fields, but proposed actions still
    pass through the strict ``ProposedAction`` schema.
    """

    model_config = ConfigDict(extra="ignore", strict=False)

    reply: str
    proposals: list[dict[str, Any]] = Field(default_factory=list)
    rationale_summary: str = ""
    risk_notes: list[str] = Field(default_factory=list)
    model_mode: AgentMode = "rule_based_fallback"
    fallback_reason: str | None = None
