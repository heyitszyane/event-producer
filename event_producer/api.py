"""FastAPI REST API wrapper for the Event Producer pipeline.

This module exposes a thin HTTP interface around ``EventProducerApp.run_event()``.
All business logic remains in the app layer; the API only handles serialization
and HTTP concerns.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from event_producer.config.defaults import DEFAULT_EVENT_CONSTRAINTS
from event_producer.config.model_settings import (
    ModelSettingsPublic,
    ModelSettingsUpdate,
    apply_to_process_env,
    env_path,
    read_env_file,
    updates_from_settings,
    write_env_values,
)
from event_producer.main import EventProducerApp
from event_producer.models.schemas import (
    Approval,
    BudgetSummary,
    Proposal,
    RunEventRequest as RunEventSchema,
    ManualConstraintFlags,
    ScopeItem,
    ScopeItemCreate,
    ScopeItemUpdate,
)
from event_producer.security.action_gate import enforce, requires_approval

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class RunEventRequest(BaseModel):
    """Request body for the ``POST /run`` endpoint.

    P7A: the legacy shape (all six constraint fields supplied) is preserved so
    existing calls/tests/tests keep working. The constraint fields are now
    **optional**, turning ``brief`` into the primary product input:

    1. ``brief`` is required and is the primary product input.
    2. Structured fields are optional constraints/manual overrides.
    3. If provided, a user-provided field wins over model extraction.
    4. If missing, the Brief Intake Agent may extract it.
    5. If still missing after extraction, a safe server-side fallback is used
       only where required by the deterministic pipeline, and the gap is
       surfaced in ``brief_intake.missing_questions`` +
       ``creative_concept`` assumptions.
    """

    brief: str
    budget_cap: str | None = None
    contingency_pct: str | None = None
    attendees: int | None = None
    event_type: str | None = None
    venue_type: str | None = None
    date: str | None = None
    manual_constraints: ManualConstraintFlags | None = None

    def to_legacy(self) -> RunEventSchema:
        """Return a schema instance (kept for parity with the typed model)."""
        return RunEventSchema(
            brief=self.brief,
            budget_cap=self.budget_cap,
            contingency_pct=self.contingency_pct,
            attendees=self.attendees,
            event_type=self.event_type,
            venue_type=self.venue_type,
            date=self.date,
            manual_constraints=self.manual_constraints,
        )


class ChatRequest(BaseModel):
    """Request body for the ``POST /chat`` endpoint."""

    message: str


class OrchestratorChatRequest(BaseModel):
    """Request body for the orchestrator chat endpoint."""

    message: str


class ApprovalAction(BaseModel):
    """Request body for the ``POST /approvals/{approval_id}`` endpoint."""

    action: Literal["approve", "reject"]


class OrchestratorChatResponse(BaseModel):
    """Response from the orchestrator chat endpoint."""
    reply: str
    proposals: list[dict[str, Any]]
    model_mode: str
    fallback_reason: str | None = None


class RuntimeModelResponse(BaseModel):
    """Non-secret model/provider diagnostics for local smoke testing."""

    provider: str
    live_enabled: bool
    effective_mode: str
    model_name: str
    api_base_url: str | None
    has_api_key: bool
    fallback_reason: str | None = None


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        A configured ``FastAPI`` instance with all routes registered.
    """
    app = FastAPI(title="Event Producer API")

    # ---- Demo auth middleware ---------------------------------------------
    # Added first so it runs *inside* CORS (CORS must be outermost to handle
    # preflight requests before auth rejects them).
    class DemoAuthMiddleware(BaseHTTPMiddleware):
        """Require X-Demo-User header on every request except /healthz."""

        async def dispatch(self, request: Request, call_next):
            if request.url.path == "/healthz":
                return await call_next(request)
            if "x-demo-user" not in request.headers:
                return JSONResponse(
                    status_code=401,
                    content={
                        "error": {
                            "code": "401",
                            "message": "Missing X-Demo-User header",
                        }
                    },
                )
            return await call_next(request)

    app.add_middleware(DemoAuthMiddleware)

    # ---- CORS middleware (env-driven origins) ----------------------------
    # Added last so it is the outermost middleware and can respond to
    # OPTIONS preflight requests before auth blocks them.
    # Set ALLOWED_ORIGINS env var in production (comma-separated list).
    _allowed_origins = os.environ.get(
        "ALLOWED_ORIGINS",
        ",".join(
            [
                "http://localhost:3000",
                "http://localhost:3001",
                "http://localhost:3002",
                "http://127.0.0.1:3000",
                "http://127.0.0.1:3001",
                "http://127.0.0.1:3002",
                "http://localhost:8080",
                "http://127.0.0.1:8080",
            ]
        ),
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in _allowed_origins.split(",") if o.strip()],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store the EventProducerApp instance on app.state so endpoints can
    # access it without re-instantiating on every request.
    app.state.event_producer = EventProducerApp()

    # ---- Global error handler ---------------------------------------------
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """Return consistent error envelope for all HTTP exceptions."""
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": str(exc.status_code), "message": exc.detail}},
        )

    # ---- Routes ----------------------------------------------------------

    @app.post("/run")
    async def run_event(req: RunEventRequest) -> dict[str, Any]:
        """Run the full event production pipeline and return the result."""
        producer: EventProducerApp = app.state.event_producer
        result = producer.run_event(
            brief=req.brief,
            budget_cap=req.budget_cap,
            contingency_pct=req.contingency_pct,
            attendees=req.attendees,
            event_type=req.event_type,
            venue_type=req.venue_type,
            date=req.date,
            manual_constraints=req.manual_constraints,
        )
        return result

    @app.get("/event/{event_id}")
    async def get_event(event_id: str) -> dict[str, Any]:
        """Retrieve full event state by its ID."""
        producer: EventProducerApp = app.state.event_producer
        event_spec = producer.event_store.get_event(event_id)
        if event_spec is None:
            raise HTTPException(status_code=404, detail="Event not found")

        budget = producer.event_store.get_budget(event_id)
        schedule = producer.event_store.get_schedule(event_id)
        ros = producer.event_store.get_run_of_show(event_id)

        return {
            "event_id": event_id,
            "event_spec": event_spec.model_dump(),
            "scope_items": [s.model_dump() for s in producer.event_store.get_scope(event_id)],
            "budget_summary": budget.model_dump() if budget else None,
            "schedule_result": schedule.model_dump() if schedule else None,
            "vendors": [v.model_dump() for v in producer.event_store.get_vendors(event_id)],
            "risk_flags": [f.model_dump() for f in ros.risk_flags] if ros else [],
            "approvals": [a.model_dump() for a in producer.event_store.get_approvals(event_id)],
        }

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        """Liveness probe."""
        return {"status": "ok"}

    @app.get("/runtime/model")
    async def runtime_model() -> RuntimeModelResponse:
        """Return non-secret model-provider state loaded at backend startup."""
        producer: EventProducerApp = app.state.event_producer
        env = producer._model_env
        return RuntimeModelResponse(
            provider=env.provider,
            live_enabled=env.live_enabled,
            effective_mode=env.effective_mode,
            model_name=env.model_name,
            api_base_url=env.api_base_url or None,
            has_api_key=bool(env.api_key),
            fallback_reason=env.fallback_reason or None,
        )

    def _public_model_settings(*, restart_required: bool = False) -> ModelSettingsPublic:
        producer: EventProducerApp = app.state.event_producer
        env = producer._model_env
        return ModelSettingsPublic(
            provider=env.provider,
            live_enabled=env.live_enabled,
            effective_mode=env.effective_mode,
            model_name=env.model_name,
            api_base_url=env.api_base_url or None,
            has_api_key=bool(env.api_key),
            fallback_reason=env.fallback_reason or None,
            env_path=str(env_path()),
            restart_required=restart_required,
        )

    @app.get("/settings/model")
    async def get_model_settings() -> ModelSettingsPublic:
        """Return non-secret local model settings for the dev settings panel."""
        return _public_model_settings()

    def _settings_write_allowed(request: Request) -> bool:
        host = request.url.hostname or ""
        return host in {"127.0.0.1", "localhost", "testserver"}

    @app.post("/settings/model")
    async def update_model_settings(
        settings: ModelSettingsUpdate, request: Request
    ) -> ModelSettingsPublic:
        """Persist local provider settings to .env and refresh the in-process app."""
        if not _settings_write_allowed(request):
            raise HTTPException(status_code=403, detail="Settings writes are local-dev only")
        current = read_env_file()
        updates = updates_from_settings(settings, current)
        write_env_values(updates)
        apply_to_process_env(updates)
        app.state.event_producer = EventProducerApp()
        return _public_model_settings()

    # ---- Demo approvals (persisted via EventStore) -----------------------
    _DEMO_EVENT_ID = "demo-event"

    _SAMPLE_APPROVALS: list[Approval] = [
        Approval(
            id="aprv-001",
            action="send_vendor_message",
            requested_by="producer@example.com",
            approved_by="",
            status="pending",
            timestamp="2026-06-21T10:30:00",
            notes="Send RFP to Grand Ballroom Co. for venue booking.",
        ),
        Approval(
            id="aprv-002",
            action="confirm_budget_line",
            requested_by="budget-agent",
            approved_by="",
            status="pending",
            timestamp="2026-06-21T11:00:00",
            notes="Confirm catering budget line of $5,000 for 200 attendees.",
        ),
        Approval(
            id="aprv-003",
            action="execute_payment",
            requested_by="finance-agent",
            approved_by="",
            status="pending",
            timestamp="2026-06-21T11:15:00",
            notes="Release 50% deposit to AV vendor ($2,500).",
        ),
    ]

    # Persist sample approvals to EventStore on startup
    for _ap in _SAMPLE_APPROVALS:
        app.state.event_producer.event_store.save_approval(_DEMO_EVENT_ID, _ap)

    def _demo_actor(request: Request) -> str:
        return request.headers.get("x-demo-user") or "demo-user"

    def _update_event_approval(
        event_id: str,
        approval_id: str,
        body: ApprovalAction,
        actor: str,
    ) -> dict[str, Any]:
        producer: EventProducerApp = app.state.event_producer
        approvals = producer.event_store.get_approvals(event_id)
        approval = next((a for a in approvals if a.id == approval_id), None)
        if approval is None:
            raise HTTPException(status_code=404, detail="Approval not found")

        if body.action == "reject":
            approval.status = "rejected"
            approval.approved_by = actor
            producer.audit_log.log(
                action="approval_rejected",
                actor=actor,
                details=f"Rejected approval {approval_id}",
                approval_id=approval_id,
                event_id=event_id,
            )
            producer.event_store.save_approval(event_id, approval)
            return approval.model_dump()

        approval.status = "approved"
        approval.approved_by = actor
        if requires_approval(approval.action):
            enforce(approval.action, approval)
            producer.audit_log.log(
                action="vendor_send_simulated"
                if approval.action == "send_vendor_message"
                else "approval_gate_released",
                actor=actor,
                details=f"Approved gated action {approval.action} for approval {approval_id}",
                approval_id=approval_id,
                event_id=event_id,
            )
        else:
            producer.audit_log.log(
                action="approval_approved",
                actor=actor,
                details=f"Approved non-gated sample action {approval.action}",
                approval_id=approval_id,
                event_id=event_id,
            )

        producer.event_store.save_approval(event_id, approval)
        return approval.model_dump()

    @app.get("/event/{event_id}/approvals")
    async def list_event_approvals(event_id: str) -> list[dict[str, Any]]:
        """List approvals for one event."""
        producer: EventProducerApp = app.state.event_producer
        if producer.event_store.get_event(event_id) is None and event_id != _DEMO_EVENT_ID:
            raise HTTPException(status_code=404, detail="Event not found")
        approvals = producer.event_store.get_approvals(event_id)
        return [a.model_dump() for a in approvals]

    @app.post("/event/{event_id}/approvals/{approval_id}")
    async def update_event_approval(
        event_id: str,
        approval_id: str,
        body: ApprovalAction,
        request: Request,
    ) -> dict[str, Any]:
        """Approve or reject an event-scoped approval through the action-gate."""
        producer: EventProducerApp = app.state.event_producer
        if producer.event_store.get_event(event_id) is None and event_id != _DEMO_EVENT_ID:
            raise HTTPException(status_code=404, detail="Event not found")
        return _update_event_approval(event_id, approval_id, body, _demo_actor(request))

    @app.get("/approvals")
    async def list_approvals() -> list[dict[str, Any]]:
        """Legacy sample route: list approvals for the demo-event fixture."""
        producer: EventProducerApp = app.state.event_producer
        approvals = producer.event_store.get_approvals(_DEMO_EVENT_ID)
        return [a.model_dump() for a in approvals]

    @app.post("/approvals/{approval_id}")
    async def update_approval(
        approval_id: str,
        body: ApprovalAction,
        request: Request,
    ) -> dict[str, Any]:
        """Legacy sample route: update an approval under demo-event."""
        return _update_event_approval(_DEMO_EVENT_ID, approval_id, body, _demo_actor(request))

    @app.post("/chat")
    async def chat(req: ChatRequest) -> dict[str, str]:
        """Chat endpoint (stub — acknowledges the message).

        P7B Note: This is a legacy stub for backward compatibility.
        The event-aware orchestrator chat is at POST /event/{event_id}/chat.
        """
        print(f"[chat] Received message: {req.message}")
        return {
            "reply": f"Received: {req.message}. The orchestrator will process this."
        }

    # ---------------------------------------------------------------------------
    # P7B — Scope mutation endpoints
    # ---------------------------------------------------------------------------

    def _recompute_event(event_id: str) -> dict[str, Any]:
        """Recompute budget and schedule after scope mutation.

        This helper calls the deterministic engines on the current scope items,
        preserving the budget/schedule invariants. Returns the updated snapshot.
        """
        producer: EventProducerApp = app.state.event_producer

        # Fetch current state
        scope_items = producer.event_store.get_scope(event_id)
        event_spec = producer.event_store.get_event(event_id)
        if not event_spec:
            raise HTTPException(status_code=404, detail="Event not found")

        # Recompute budget using existing engine (preserve original contingency_pct)
        existing_budget = producer.event_store.get_budget(event_id)
        previous_headroom = existing_budget.headroom if existing_budget else None
        budget_cap = (
            existing_budget.budget_cap if existing_budget
            else Decimal(str(DEFAULT_EVENT_CONSTRAINTS["budget_cap"]))
        )
        contingency_pct = (
            existing_budget.contingency_pct if existing_budget
            else Decimal(str(DEFAULT_EVENT_CONSTRAINTS["contingency_pct"]))
        )

        budget_request = {
            "scope_items": [s.model_dump() for s in scope_items],
            "budget_cap": budget_cap,
            "contingency_pct": contingency_pct,
            "reporting_currency": "USD",
        }
        budget_raw = producer._budget_reason.run(budget_request)
        budget_validated = producer._budget_formatter.run(budget_raw)
        budget_summary = budget_validated["budget_summary"]
        updated_budget = BudgetSummary(**budget_summary)
        producer.event_store.save_budget(event_id, updated_budget)

        # Recompute schedule (best effort; may be None)
        event_date = datetime.strptime(event_spec.date, "%Y-%m-%d")
        start_time = event_date.replace(
            hour=8, minute=0, second=0, tzinfo=timezone.utc,
        ) - timedelta(days=30)

        production_request = {
            "event_spec": event_spec.model_dump(),
            "scope_items": [s.model_dump() for s in scope_items],
            "start_time": start_time.isoformat(),
        }
        production_raw = producer._production_reason.run(production_request)
        production_validated = producer._production_formatter.run(production_raw)

        schedule_result = None
        call_sheet = []
        if "schedule_result" in production_validated and production_validated["schedule_result"] is not None:
            schedule_result = production_validated["schedule_result"]
            if schedule_result is not None:
                producer.event_store.save_schedule(event_id, schedule_result)

        if "call_sheet" in production_validated:
            call_sheet = list(production_validated["call_sheet"])

        # Risk flags recompute (optional - for now return empty, can extend later)
        # For P7B, we skip risk recompute to keep scope focused

        schedule_message = (
            "Schedule recomputed."
            if schedule_result
            else "Schedule warning: new item is not yet scheduled."
        )
        previous_headroom_text = str(previous_headroom) if previous_headroom is not None else "unknown"
        current_headroom_text = str(updated_budget.headroom)

        return {
            "scope_items": [s.model_dump() for s in scope_items],
            "budget_summary": budget_summary,
            "schedule_result": schedule_result.model_dump() if schedule_result else None,
            "call_sheet": [c.model_dump() for c in call_sheet],
            "recompute_notice": {
                "previous_headroom": previous_headroom_text,
                "current_headroom": current_headroom_text,
                "schedule_status": "recomputed" if schedule_result else "warning",
                "message": (
                    "Budget recalculated. "
                    f"Headroom changed from {previous_headroom_text} to {current_headroom_text}. "
                    f"{schedule_message} Risk register and agent trace still reflect the last full pipeline run; "
                    "rerun the event to refresh all agent outputs."
                ),
            },
        }

    # P7B scope mutation uses a generic event_id parameter; the store is keyed by event_id.
    # Using a query parameter for demo purposes (frontend drives event_id from last /run result).

    @app.post("/event/{event_id}/scope-items")
    async def add_scope_item(event_id: str, req: ScopeItemCreate) -> dict[str, Any]:
        """Add a new scope item to an event and recompute budget."""
        producer: EventProducerApp = app.state.event_producer

        scope = producer.event_store.get_scope(event_id)
        if not scope and event_id != _DEMO_EVENT_ID:
            raise HTTPException(status_code=404, detail="Event not found")

        # Create ScopeItem from the request
        new_item = ScopeItem(
            name=req.name,
            description=req.description,
            category=req.category,
            tier=req.tier,
            estimated_cost=req.estimated_cost,
            currency=req.currency,
            qty=req.qty,
            selected=req.selected,
        )
        scope.append(new_item)
        producer.event_store.save_scope(event_id, scope)
        producer.audit_log.log(
            action="add_scope_item",
            actor="demo-user",
            details=f"Added scope item '{req.name}' to event {event_id}",
            event_id=event_id,
        )

        return _recompute_event(event_id)

    @app.patch("/event/{event_id}/scope-items/{item_id}")
    async def update_scope_item(
        event_id: str, item_id: str, req: ScopeItemUpdate
    ) -> dict[str, Any]:
        """Update an existing scope item and recompute budget."""
        producer: EventProducerApp = app.state.event_producer

        scope = producer.event_store.get_scope(event_id)
        if not scope and event_id != _DEMO_EVENT_ID:
            raise HTTPException(status_code=404, detail="Event not found")

        # Find and update the item by index (simplified for MVP)
        # In a real system, ScopeItem would have its own ID; for now we use index
        idx = int(item_id) if item_id.isdigit() else -1
        if idx < 0 or idx >= len(scope):
            raise HTTPException(status_code=404, detail="Scope item not found")

        item = scope[idx]
        update_data = req.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(item, field, value)

        producer.event_store.save_scope(event_id, scope)
        producer.audit_log.log(
            action="update_scope_item",
            actor="demo-user",
            details=f"Updated scope item '{item.name}' in event {event_id}",
            event_id=event_id,
        )

        return _recompute_event(event_id)

    @app.delete("/event/{event_id}/scope-items/{item_id}")
    async def delete_scope_item(event_id: str, item_id: str) -> dict[str, Any]:
        """Delete a scope item and recompute budget."""
        producer: EventProducerApp = app.state.event_producer

        scope = producer.event_store.get_scope(event_id)
        if not scope and event_id != _DEMO_EVENT_ID:
            raise HTTPException(status_code=404, detail="Event not found")

        idx = int(item_id) if item_id.isdigit() else -1
        if idx < 0 or idx >= len(scope):
            raise HTTPException(status_code=404, detail="Scope item not found")

        deleted_name = scope[idx].name
        scope.pop(idx)
        producer.event_store.save_scope(event_id, scope)
        producer.audit_log.log(
            action="delete_scope_item",
            actor="demo-user",
            details=f"Deleted scope item '{deleted_name}' from event {event_id}",
            event_id=event_id,
        )

        return _recompute_event(event_id)

    @app.post("/event/{event_id}/scope-items/{item_id}/toggle")
    async def toggle_scope_item(event_id: str, item_id: str) -> dict[str, Any]:
        """Toggle the selected flag on a scope item and recompute budget."""
        producer: EventProducerApp = app.state.event_producer

        scope = producer.event_store.get_scope(event_id)
        if not scope and event_id != _DEMO_EVENT_ID:
            raise HTTPException(status_code=404, detail="Event not found")

        idx = int(item_id) if item_id.isdigit() else -1
        if idx < 0 or idx >= len(scope):
            raise HTTPException(status_code=404, detail="Scope item not found")

        scope[idx].selected = not scope[idx].selected
        producer.event_store.save_scope(event_id, scope)
        producer.audit_log.log(
            action="toggle_scope_item",
            actor="demo-user",
            details=f"Toggled scope item '{scope[idx].name}' in event {event_id}",
            event_id=event_id,
        )

        return _recompute_event(event_id)

    @app.post("/event/{event_id}/scope-items/{item_id}/retier")
    async def retier_scope_item(
        event_id: str, item_id: str, req: dict
    ) -> dict[str, Any]:
        """Change the tier on a scope item and recompute budget."""
        producer: EventProducerApp = app.state.event_producer

        scope = producer.event_store.get_scope(event_id)
        if not scope and event_id != _DEMO_EVENT_ID:
            raise HTTPException(status_code=404, detail="Event not found")

        idx = int(item_id) if item_id.isdigit() else -1
        if idx < 0 or idx >= len(scope):
            raise HTTPException(status_code=404, detail="Scope item not found")

        new_tier = req.get("tier", "could")
        if new_tier not in ("must", "should", "could", "wow"):
            raise HTTPException(status_code=422, detail="Invalid tier value")

        scope[idx].tier = new_tier
        producer.event_store.save_scope(event_id, scope)
        producer.audit_log.log(
            action="retier_scope_item",
            actor="demo-user",
            details=f"Retiered scope item '{scope[idx].name}' to '{new_tier}' in event {event_id}",
            event_id=event_id,
        )

        return _recompute_event(event_id)

    # ---------------------------------------------------------------------------
    # P7B — Orchestrator chat and proposal application
    # ---------------------------------------------------------------------------

    @app.post("/event/{event_id}/chat")
    async def orchestrator_chat(
        event_id: str, req: OrchestratorChatRequest
    ) -> OrchestratorChatResponse:
        """Chat with the orchestrator; returns proposed actions, no mutation.

        Proposals are stored server-side; the response includes the stored
        proposal IDs for apply/dismiss operations.
        """
        producer: EventProducerApp = app.state.event_producer

        # Fetch event context for the orchestrator
        event_spec = producer.event_store.get_event(event_id)
        scope_items = producer.event_store.get_scope(event_id)
        budget_summary = producer.event_store.get_budget(event_id)

        if not event_spec:
            raise HTTPException(status_code=404, detail="Event not found")

        # Build context for the orchestrator agent
        context = {
            "event_id": event_id,
            "event_spec": event_spec.model_dump(),
            "scope_items": [s.model_dump() for s in scope_items],
            "budget_summary": budget_summary.model_dump() if budget_summary else None,
        }

        # The orchestrator agent returns proposed actions
        result = producer._orchestrator.run(req.message, context)

        # Store each proposed action as a Proposal object for apply/dismiss
        stored_proposals: list[dict[str, Any]] = []
        for pa in result.proposals:
            # Convert ProposedAction to Proposal and store
            prop = Proposal(
                id=pa.id,
                event_id=event_id,
                title=pa.title,
                rationale=pa.rationale,
                proposed_actions=[pa],
                status="pending",
                created_at=pa.created_at or datetime.now(timezone.utc).isoformat(),
                model_mode=pa.model_mode,
                fallback_reason=result.fallback_reason,
            )
            producer.event_store.save_proposal(event_id, prop)
            stored_proposals.append(pa.model_dump())

        return OrchestratorChatResponse(
            reply=result.reply,
            proposals=stored_proposals,
            model_mode=result.model_mode,
            fallback_reason=result.fallback_reason,
        )

    @app.post("/event/{event_id}/proposals/{proposal_id}/apply")
    async def apply_proposal(event_id: str, proposal_id: str) -> dict[str, Any]:
        """Apply a pending proposal; mutates scope based on proposed actions."""
        producer: EventProducerApp = app.state.event_producer

        # Validate event exists
        event_spec = producer.event_store.get_event(event_id)
        if not event_spec:
            raise HTTPException(status_code=404, detail="Event not found")

        # Find the proposal
        proposal = producer.event_store.get_proposal(event_id, proposal_id)
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")
        if proposal.status != "pending":
            raise HTTPException(status_code=409, detail="Proposal already applied or dismissed")

        # Check for approval-gated actions in any proposed action
        for action in proposal.proposed_actions:
            if action.requires_approval_gate:
                raise HTTPException(
                    status_code=422,
                    detail="Proposal contains approval-gated action; use /approvals instead"
                )

        # Apply each action to scope
        scope = producer.event_store.get_scope(event_id)
        for action in proposal.proposed_actions:
            if action.type == "add_scope_item":
                payload = action.payload
                new_item = ScopeItem(
                    name=payload.get("name", "Unnamed"),
                    description=payload.get("description", ""),
                    category=payload.get("category", "other"),
                    tier=payload.get("tier", "could"),
                    estimated_cost=Decimal(str(payload.get("estimated_cost", "0"))),
                    currency=payload.get("currency", "USD"),
                    qty=Decimal(str(payload.get("qty", "1"))),
                    selected=payload.get("selected", True),
                )
                scope.append(new_item)
                producer.audit_log.log(
                    action="apply_proposal_add",
                    actor="demo-user",
                    details=f"Applied proposal action {action.id}: added '{payload.get('name')}'",
                    event_id=event_id,
                )
            elif action.type == "toggle_scope_item":
                # For now, toggle by index or name; MVP uses name match
                item_name = action.payload.get("name")
                for item in scope:
                    if item.name == item_name:
                        item.selected = action.payload.get("selected", False)
                        producer.audit_log.log(
                            action="apply_proposal_toggle",
                            actor="demo-user",
                            details=f"Applied proposal action {action.id}: toggled '{item_name}'",
                            event_id=event_id,
                        )
                        break

        # Save updated scope and mark proposal as applied
        producer.event_store.save_scope(event_id, scope)
        proposal.status = "applied"
        producer.event_store.save_proposal(event_id, proposal)

        return _recompute_event(event_id)

    @app.post("/event/{event_id}/proposals/{proposal_id}/dismiss")
    async def dismiss_proposal(event_id: str, proposal_id: str) -> dict[str, Any]:
        """Dismiss a pending proposal without mutation."""
        producer: EventProducerApp = app.state.event_producer

        event_spec = producer.event_store.get_event(event_id)
        if not event_spec:
            raise HTTPException(status_code=404, detail="Event not found")

        proposal = producer.event_store.get_proposal(event_id, proposal_id)
        if not proposal:
            raise HTTPException(status_code=404, detail="Proposal not found")
        if proposal.status != "pending":
            raise HTTPException(status_code=409, detail="Proposal already applied or dismissed")

        proposal.status = "dismissed"
        producer.event_store.save_proposal(event_id, proposal)
        producer.audit_log.log(
            action="dismiss_proposal",
            actor="demo-user",
            details=f"Dismissed proposal {proposal_id}",
            event_id=event_id,
        )

        # Return current state unchanged
        return {"proposal_id": proposal_id, "status": "dismissed"}

    return app
