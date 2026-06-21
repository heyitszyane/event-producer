"""Composition root — wires all agents, engines, and providers together.

This module is the single place where concrete implementations are
instantiated and injected into the abstract agent interfaces. It exposes
``EventProducerApp``, the entry point for running an end-to-end event
production pipeline from brief to run-of-show.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from event_producer.agents.brief_scope import (
    BriefScopeFormatterAgent,
    BriefScopeReasonAgent,
)
from event_producer.agents.budget_manager import (
    BudgetManagerFormatterAgent,
    BudgetManagerReasonAgent,
)
from event_producer.agents.orchestrator import OrchestratorAgent
from event_producer.agents.production_manager import (
    ProductionManagerFormatterAgent,
    ProductionManagerReasonAgent,
)
from event_producer.agents.risk_flagger import RiskFlaggerAgent
from event_producer.agents.vendor_coordinator import (
    VendorCoordinatorFormatterAgent,
    VendorCoordinatorReasonAgent,
)
from event_producer.models.schemas import (
    AgentTraceStep,
    Approval,
    BudgetSummary,
    ChatLogMessage,
    EventSpec,
    RiskFlag,
    RunOfShow,
    ScheduleResult,
    ScopeItem,
    Vendor,
    VendorMessage,
)
from event_producer.providers.event_store import EventStore
from event_producer.providers.rate_card import FxRateProvider, StaticFxRateProvider
from event_producer.providers.vendor_sourcer import VendorSourcer
from event_producer.security.audit_log import AuditLog


# ---------------------------------------------------------------------------
# Concrete provider implementations (MVP / in-memory)
# ---------------------------------------------------------------------------


class InMemoryEventStore(EventStore):
    """Dict-based in-memory event store for the MVP.

    Stores events, scopes, budgets, schedules, vendors, messages, and
    run-of-show records keyed by event_id. All operations are synchronous
    and deterministic.
    """

    def __init__(self) -> None:
        self._events: dict[str, EventSpec] = {}
        self._scopes: dict[str, list[ScopeItem]] = {}
        self._budgets: dict[str, BudgetSummary] = {}
        self._schedules: dict[str, ScheduleResult] = {}
        self._vendors: dict[str, list[Vendor]] = {}
        self._messages: dict[str, list[VendorMessage]] = {}
        self._run_of_shows: dict[str, RunOfShow] = {}
        self._approvals: dict[str, list[Approval]] = {}

    def save_event(self, event_id: str, event_spec: EventSpec) -> None:
        self._events[event_id] = event_spec

    def get_event(self, event_id: str) -> Optional[EventSpec]:
        return self._events.get(event_id)

    def save_scope(self, event_id: str, items: list[ScopeItem]) -> None:
        self._scopes[event_id] = list(items)

    def get_scope(self, event_id: str) -> list[ScopeItem]:
        return list(self._scopes.get(event_id, []))

    def save_budget(self, event_id: str, budget: BudgetSummary) -> None:
        self._budgets[event_id] = budget

    def get_budget(self, event_id: str) -> Optional[BudgetSummary]:
        return self._budgets.get(event_id)

    def save_schedule(self, event_id: str, schedule: ScheduleResult) -> None:
        self._schedules[event_id] = schedule

    def get_schedule(self, event_id: str) -> Optional[ScheduleResult]:
        return self._schedules.get(event_id)

    def save_vendor(self, event_id: str, vendor: Vendor) -> None:
        vendors = self._vendors.setdefault(event_id, [])
        # Replace existing vendor with same ID, otherwise append
        for i, v in enumerate(vendors):
            if v.id == vendor.id:
                vendors[i] = vendor
                return
        vendors.append(vendor)

    def get_vendors(self, event_id: str) -> list[Vendor]:
        return list(self._vendors.get(event_id, []))

    def save_message(self, event_id: str, message: VendorMessage) -> None:
        self._messages.setdefault(event_id, []).append(message)

    def get_messages(self, event_id: str) -> list[VendorMessage]:
        return list(self._messages.get(event_id, []))

    def save_run_of_show(self, event_id: str, ros: RunOfShow) -> None:
        self._run_of_shows[event_id] = ros

    def get_run_of_show(self, event_id: str) -> Optional[RunOfShow]:
        return self._run_of_shows.get(event_id)

    def list_events(self) -> list[str]:
        return sorted(self._events.keys())

    def delete_event(self, event_id: str) -> bool:
        if event_id not in self._events:
            return False
        del self._events[event_id]
        self._scopes.pop(event_id, None)
        self._budgets.pop(event_id, None)
        self._schedules.pop(event_id, None)
        self._vendors.pop(event_id, None)
        self._messages.pop(event_id, None)
        self._run_of_shows.pop(event_id, None)
        self._approvals.pop(event_id, None)
        return True

    def save_approval(self, event_id: str, approval: Approval) -> None:
        approvals = self._approvals.setdefault(event_id, [])
        for i, a in enumerate(approvals):
            if a.id == approval.id:
                approvals[i] = approval
                return
        approvals.append(approval)

    def get_approvals(self, event_id: str) -> list[Approval]:
        return list(self._approvals.get(event_id, []))


class InMemoryVendorSourcer(VendorSourcer):
    """Hardcoded vendor sourcer for the MVP.

    Returns a small static list of sample vendors. No network calls.
    """

    _SAMPLE_VENDORS: list[Vendor] = [
        Vendor(
            id="vendor-001",
            name="Grand Ballroom Co.",
            category="venue",
            contact_email="bookings@grandballroom.example",
            contact_phone="+1-555-0101",
            rating=Decimal("4.5"),
            notes="Premium indoor venue, capacity up to 500",
        ),
        Vendor(
            id="vendor-002",
            name="Catering Excellence",
            category="catering",
            contact_email="events@cateringexc.example",
            contact_phone="+1-555-0202",
            rating=Decimal("4.8"),
            notes="Full-service catering, dietary accommodations available",
        ),
        Vendor(
            id="vendor-003",
            name="AV Pro Systems",
            category="av_equipment",
            contact_email="rentals@avpro.example",
            contact_phone="+1-555-0303",
            rating=Decimal("4.2"),
            notes="Sound, lighting, and projection equipment",
        ),
        Vendor(
            id="vendor-004",
            name="StaffPro Events",
            category="staffing",
            contact_email="info@staffpro.example",
            contact_phone="+1-555-0404",
            rating=Decimal("4.0"),
            notes="Professional event staff and coordinators",
        ),
        Vendor(
            id="vendor-005",
            name="SecureGuard Services",
            category="security",
            contact_email="contracts@secureguard.example",
            contact_phone="+1-555-0505",
            rating=Decimal("4.3"),
            notes="Licensed event security personnel",
        ),
    ]

    def search(self, category: str, location: str = "") -> list[Vendor]:
        category_lower = category.lower()
        return [v for v in self._SAMPLE_VENDORS if v.category == category_lower]

    def get_by_id(self, vendor_id: str) -> Vendor | None:
        for v in self._SAMPLE_VENDORS:
            if v.id == vendor_id:
                return v
        return None

    def qualify(self, vendor: Vendor, requirements: dict) -> bool:
        min_rating = Decimal(str(requirements.get("min_rating", "0.00")))
        return vendor.rating >= min_rating


# ---------------------------------------------------------------------------
# Composition root
# ---------------------------------------------------------------------------


class EventProducerApp:
    """Top-level composition root for the Event Producer pipeline.

    Creates all provider instances, audit log, and agent pairs. Provides
    the ``run_event`` entry point that orchestrates the full flow from
    brief to run-of-show.
    """

    def __init__(self) -> None:
        # --- Providers ---
        self._event_store = InMemoryEventStore()
        self._vendor_sourcer = InMemoryVendorSourcer()
        self._fx_provider: FxRateProvider = StaticFxRateProvider()
        self._audit_log = AuditLog()

        # --- Agents: Brief/Scope ---
        self._brief_scope_reason = BriefScopeReasonAgent(event_store=self._event_store)
        self._brief_scope_formatter = BriefScopeFormatterAgent()

        # --- Agents: Budget ---
        self._budget_reason = BudgetManagerReasonAgent(
            event_store=self._event_store,
            fx_provider=self._fx_provider,
        )
        self._budget_formatter = BudgetManagerFormatterAgent()

        # --- Agents: Production ---
        self._production_reason = ProductionManagerReasonAgent(event_store=self._event_store)
        self._production_formatter = ProductionManagerFormatterAgent()

        # --- Agents: Risk ---
        self._risk_flagger = RiskFlaggerAgent(event_store=self._event_store)

        # --- Agents: Vendor ---
        self._vendor_reason = VendorCoordinatorReasonAgent(
            event_store=self._event_store,
            vendor_sourcer=self._vendor_sourcer,
            audit_log=self._audit_log,
        )
        self._vendor_formatter = VendorCoordinatorFormatterAgent()

        # --- Agents: Orchestrator ---
        self._orchestrator = OrchestratorAgent(event_store=self._event_store)

    @property
    def event_store(self) -> InMemoryEventStore:
        return self._event_store

    @property
    def vendor_sourcer(self) -> InMemoryVendorSourcer:
        return self._vendor_sourcer

    @property
    def fx_provider(self) -> FxRateProvider:
        return self._fx_provider

    @property
    def audit_log(self) -> AuditLog:
        return self._audit_log

    def run_event(
        self,
        brief: str,
        budget_cap: str,
        contingency_pct: str,
        attendees: int,
        event_type: str,
        venue_type: str,
        date: str,
    ) -> dict:
        """Run the full event production pipeline.

        Steps:
            1. Brief/Scope — parse brief, propose scope items
            2. Budget — reconcile budget to zero
            3. Production — compute run-of-show schedule
            4. Vendor — draft a sample vendor RFP + create pending approval
            5. Risk — flag risks and gaps
            6. Compose — assemble into a RunOfShow

        Args:
            brief: Raw event description.
            budget_cap: Maximum budget as a string (e.g. "50000").
            contingency_pct: Contingency percentage as a string (e.g. "15").
            attendees: Expected number of attendees.
            event_type: One of "networking", "product_launch", "conference",
                "corporate".
            venue_type: Venue description (e.g. "indoor", "outdoor").
            date: Event date in YYYY-MM-DD format.

        Returns:
            A dict with keys: event_id, event_spec, scope_items, budget_summary,
            schedule_result, conflict_report, call_sheet, risk_flags, vendor_draft,
            run_of_show, agent_trace, chat_log, approvals, security_beat.
        """
        event_id = str(uuid.uuid4())
        agent_trace: list[AgentTraceStep] = []
        chat_log: list[ChatLogMessage] = []
        approvals: list[Approval] = []

        # ------------------------------------------------------------------
        # Step 1: Brief / Scope
        # ------------------------------------------------------------------
        brief_request = {
            "brief": brief,
            "budget_cap": budget_cap,
            "attendees": attendees,
            "event_type": event_type,
            "venue_type": venue_type,
            "date": date,
        }
        brief_raw = self._brief_scope_reason.run(brief_request)
        brief_validated = self._brief_scope_formatter.run(brief_raw)

        event_spec = EventSpec(**brief_validated["event_spec"])
        scope_items = [ScopeItem(**s) for s in brief_validated["scope_items"]]

        # Persist
        self._event_store.save_event(event_id, event_spec)
        self._event_store.save_scope(event_id, scope_items)

        # Trace + chat
        agent_trace.append(AgentTraceStep(
            id="trace-brief-scope",
            role="Brief/Scope Agent",
            label="Parsed event brief and proposed initial scope",
            status="complete",
            input_summary=f"{brief}, {attendees} attendees, ${budget_cap} cap, {venue_type} {event_type} setting",
            output_summary=f"Created event identity and must/should/could scope tiers ({len(scope_items)} items)",
            artifacts=["event_spec", "scope_items"],
            deterministic_core=None,
            approval_required=False,
        ))
        chat_log.append(ChatLogMessage(
            role="system",
            content=f"Event production pipeline started for '{brief}'",
        ))
        chat_log.append(ChatLogMessage(
            role="agent",
            agent="Brief/Scope Agent",
            content=f"Parsed event brief. Proposed {len(scope_items)} scope items: "
                    + ", ".join(s["name"] for s in brief_validated["scope_items"]),
        ))

        # ------------------------------------------------------------------
        # Step 2: Budget
        # ------------------------------------------------------------------
        budget_request = {
            "scope_items": brief_validated["scope_items"],
            "budget_cap": budget_cap,
            "contingency_pct": contingency_pct,
            "reporting_currency": "USD",
        }
        budget_raw = self._budget_reason.run(budget_request)
        budget_validated = self._budget_formatter.run(budget_raw)

        budget_summary = BudgetSummary(**budget_validated["budget_summary"])

        # Persist
        self._event_store.save_budget(event_id, budget_summary)

        # Trace + chat
        agent_trace.append(AgentTraceStep(
            id="trace-budget",
            role="Budget Manager",
            label="Costed scope through Budget Engine",
            status="complete",
            input_summary=f"Scope items and ${budget_cap} budget cap with {contingency_pct}% contingency",
            output_summary="Reserved contingency, computed spendable budget, rollups, and headroom",
            artifacts=["budget_summary"],
            deterministic_core="Budget Engine",
            approval_required=False,
        ))
        chat_log.append(ChatLogMessage(
            role="agent",
            agent="Budget Manager",
            content=(
                f"Reconciled budget: ${budget_cap} cap, "
                f"${budget_summary.contingency_reserve} contingency ({contingency_pct}%), "
                f"${budget_summary.spendable} spendable. "
                f"Included ${budget_summary.included_totals}. "
                f"Headroom: ${budget_summary.headroom}."
            ),
        ))

        # ------------------------------------------------------------------
        # Step 3: Production (Schedule)
        # ------------------------------------------------------------------
        # Start 30 days before the event so that vendor lead times (e.g.,
        # catering 7 days, staging 5 days, AV 3 days, security 3 days) are
        # feasible.  The production manager further adjusts the start time
        # to account for the maximum lead time across all tasks.
        event_date = datetime.strptime(event_spec.date, "%Y-%m-%d")
        start_time = event_date.replace(
            hour=8, minute=0, second=0, tzinfo=timezone.utc,
        ) - timedelta(days=30)

        production_request = {
            "event_spec": brief_validated["event_spec"],
            "scope_items": brief_validated["scope_items"],
            "start_time": start_time.isoformat(),
        }
        production_raw = self._production_reason.run(production_request)
        production_validated = self._production_formatter.run(production_raw)

        schedule_result = None
        call_sheet = []
        if "schedule_result" in production_validated and production_validated["schedule_result"] is not None:
            sr = production_validated["schedule_result"]
            schedule_result = sr if isinstance(sr, ScheduleResult) else ScheduleResult(**sr)
            self._event_store.save_schedule(event_id, schedule_result)

        if "call_sheet" in production_validated:
            call_sheet = list(production_validated["call_sheet"])

        # Trace + chat
        task_count = len(schedule_result.ordered_tasks) if schedule_result else 0
        critical_path_str = (
            ", ".join(schedule_result.critical_path)
            if schedule_result and schedule_result.critical_path
            else "none"
        )
        agent_trace.append(AgentTraceStep(
            id="trace-production",
            role="Production Manager",
            label="Generated run-of-show through CPM Scheduler",
            status="complete",
            input_summary="EventSpec and included scope items",
            output_summary=f"Created ordered schedule with {task_count} tasks. Critical path: {critical_path_str}",
            artifacts=["run_of_show"],
            deterministic_core="CPM Scheduler",
            approval_required=False,
        ))
        chat_log.append(ChatLogMessage(
            role="agent",
            agent="Production Manager",
            content=f"Generated run-of-show with {task_count} tasks. Critical path: {critical_path_str}.",
        ))

        # ------------------------------------------------------------------
        # Step 4: Vendor (draft RFP — sample) + Approval creation
        # ------------------------------------------------------------------
        # Pick a sample vendor from the sourcer for the RFP draft
        sample_vendors = self._vendor_sourcer.search("venue")
        vendor_draft = None
        if sample_vendors:
            sample_vendor = sample_vendors[0]
            self._event_store.save_vendor(event_id, sample_vendor)

            vendor_request = {
                "action": "draft_rfp",
                "vendor_id": sample_vendor.id,
                "event_id": event_id,
            }
            vendor_raw = self._vendor_reason.run(vendor_request)
            vendor_validated = self._vendor_formatter.run(vendor_raw)
            vendor_draft = vendor_validated

            # Create a real pending approval for the vendor draft
            approval = Approval(
                id=f"aprv-{event_id[:8]}-vendor",
                action="send_vendor_message",
                requested_by="vendor-coordinator",
                approved_by="",
                status="pending",
                timestamp=datetime.now(timezone.utc).isoformat(),
                notes=f"Send RFP to {sample_vendor.name} for {sample_vendor.category} booking.",
            )
            self._event_store.save_approval(event_id, approval)
            approvals.append(approval)

        # Trace + chat
        vendor_name = sample_vendors[0].name if sample_vendors else "unknown"
        agent_trace.append(AgentTraceStep(
            id="trace-vendor",
            role="Vendor Coordinator",
            label="Drafted vendor-facing action",
            status="pending_approval",
            input_summary="Venue / AV / F&B needs from scope",
            output_summary=f"Prepared outbound vendor draft to {vendor_name} blocked behind human approval",
            artifacts=["vendors", "approvals"],
            deterministic_core=None,
            approval_required=True,
        ))
        chat_log.append(ChatLogMessage(
            role="agent",
            agent="Vendor Coordinator",
            content=f"Drafted RFP for {vendor_name}. Awaiting human approval before sending.",
        ))

        # ------------------------------------------------------------------
        # Step 5: Risk
        # ------------------------------------------------------------------
        risk_state = {
            "event_spec": brief_validated["event_spec"],
            "budget_summary": budget_validated["budget_summary"],
            "schedule_result": production_validated.get("schedule_result"),
            "conflict_report": production_validated.get("conflict_report"),
            "vendors": [v.model_dump() for v in sample_vendors] if sample_vendors else [],
            "vendor_messages": [],
        }
        risk_flags_raw = self._risk_flagger.run(risk_state)
        risk_flags = [RiskFlag(**f) for f in risk_flags_raw]

        # Trace + chat
        risk_count = len(risk_flags)
        risk_summary = "; ".join(f.message for f in risk_flags) if risk_flags else "No risks detected"
        agent_trace.append(AgentTraceStep(
            id="trace-risk",
            role="Risk/Gap Flagger",
            label="Reviewed operational and security risks",
            status="warning" if risk_flags else "complete",
            input_summary="Full event state, vendor draft, budget, schedule",
            output_summary=f"Raised {risk_count} risk(s)/gap(s) and structural action-gate reminder",
            artifacts=["risks", "security_events"],
            deterministic_core="Action Gate",
            approval_required=False,
        ))
        chat_log.append(ChatLogMessage(
            role="agent",
            agent="Risk/Gap Flagger",
            content=f"Raised {risk_count} risk(s): {risk_summary}.",
        ))

        # ------------------------------------------------------------------
        # Step 6: Compose RunOfShow
        # ------------------------------------------------------------------
        run_of_show = RunOfShow(
            event_spec=event_spec,
            scope_items=scope_items,
            budget_summary=budget_summary,
            schedule_result=schedule_result,
            call_sheet=call_sheet,
            vendors=sample_vendors if sample_vendors else [],
            risk_flags=risk_flags,
            approvals=approvals,
        )

        self._event_store.save_run_of_show(event_id, run_of_show)

        # ------------------------------------------------------------------
        # Security beat (P6D: honest placeholder — scripted beat deferred to P6F)
        # ------------------------------------------------------------------
        security_beat = {
            "status": "deferred_to_p6f",
            "note": "Scripted injection/security beat will be wired in P6F. "
                    "Current P6D preserves the structural approval gate and "
                    "does not execute vendor actions automatically.",
        }

        # ------------------------------------------------------------------
        # Return result dict
        # ------------------------------------------------------------------
        conflict_report = production_validated.get("conflict_report")
        return {
            "event_id": event_id,
            "event_spec": event_spec.model_dump(),
            "scope_items": [s.model_dump() for s in scope_items],
            "budget_summary": budget_summary.model_dump(),
            "schedule_result": schedule_result.model_dump() if schedule_result else None,
            "conflict_report": conflict_report,
            "call_sheet": [c.model_dump() for c in call_sheet],
            "risk_flags": [f.model_dump() for f in risk_flags],
            "vendor_draft": vendor_draft,
            "run_of_show": run_of_show.model_dump(),
            "agent_trace": [step.model_dump() for step in agent_trace],
            "chat_log": [msg.model_dump() for msg in chat_log],
            "approvals": [a.model_dump() for a in approvals],
            "security_beat": security_beat,
        }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def create_app():
    """Create and return the FastAPI application.

    This is a thin re-export that delegates to ``event_producer.api.create_app``
    so that ``main.py`` can serve as an alternative entry point.
    """
    from event_producer.api import create_app as _create_app

    return _create_app()


if __name__ == "__main__":
    import uvicorn

    # Run the FastAPI app via uvicorn on port 8080
    uvicorn.run(
        "event_producer.api:create_app",
        host="0.0.0.0",
        port=8080,
        factory=True,
    )

    # The block below is kept for backwards compatibility when running
    # the pipeline without the API server. Uncomment to use:
    #
    # app = EventProducerApp()
    # result = app.run_event(
    #     brief="Networking event for industry professionals",
    #     budget_cap="50000",
    #     contingency_pct="15",
    #     attendees=200,
    #     event_type="networking",
    #     venue_type="indoor",
    #     date="2026-08-15",
    # )
    # print(json.dumps(result, indent=2, default=str))
