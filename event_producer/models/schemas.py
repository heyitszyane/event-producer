"""Typed Pydantic contracts for the Budget Engine and CPM Scheduler.

All monetary/time fields use Decimal — never float. Every model runs in strict
mode so that float-to-Decimal coercion is rejected at the boundary.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ISO_4217_ALLOWLIST: frozenset[str] = frozenset({
    "USD", "EUR", "GBP", "SGD", "THB", "MYR", "IDR",
    "PHP", "VND", "JPY", "KRW", "AUD", "CNY",
})

_TIER_LITERAL = Literal["must", "should", "could", "wow"]


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

    receipt_vs_plan: dict[str, Decimal] = {}
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
    contingency_reserve: Decimal
    spendable: Decimal
    included_totals: Decimal
    headroom: Decimal
    tier_inclusion: dict[str, bool]
    over_budget: bool
    under_budget: bool
    variance: BudgetVariance

    @field_validator(
        "budget_cap", "contingency_reserve", "spendable",
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
    dependencies: list[str] = []
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
    dependencies: list[str] = []
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
    conflict_type: Literal["lead_time", "anchor", "cycle"]
    message: str


class SchedulerConflictReport(BaseModel):
    """Conflict report returned when the scheduler detects infeasibilities."""

    model_config = ConfigDict(strict=True)

    lead_time_conflicts: list[Conflict] = []
    anchor_conflicts: list[Conflict] = []
    cycle: list[str] = []


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
    missing_fields: list[str] = []

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
    injection_flags: list[str] = []

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
    related_items: list[str] = []
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
    call_sheet: list[CallSheetEntry] = []
    vendors: list[Vendor] = []
    risk_flags: list[RiskFlag] = []
    approvals: list[Approval] = []
