"""FastAPI REST API wrapper for the Event Producer pipeline.

This module exposes a thin HTTP interface around ``EventProducerApp.run_event()``.
All business logic remains in the app layer; the API only handles serialization
and HTTP concerns.
"""

from __future__ import annotations

import os
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from event_producer.main import EventProducerApp
from event_producer.models.schemas import Approval, RunEventRequest as RunEventSchema
from event_producer.security.action_gate import enforce

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
        )


class ChatRequest(BaseModel):
    """Request body for the ``POST /chat`` endpoint."""

    message: str


class ApprovalAction(BaseModel):
    """Request body for the ``POST /approvals/{approval_id}`` endpoint."""

    action: Literal["approve", "reject"]


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
        "ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8080"
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

    @app.get("/approvals")
    async def list_approvals() -> list[dict[str, Any]]:
        """List pending approvals (retrieved from EventStore)."""
        producer: EventProducerApp = app.state.event_producer
        approvals = producer.event_store.get_approvals(_DEMO_EVENT_ID)
        return [a.model_dump() for a in approvals]

    @app.post("/approvals/{approval_id}")
    async def update_approval(
        approval_id: str,
        body: ApprovalAction,
    ) -> dict[str, Any]:
        """Approve or reject a pending approval through the action-gate.

        When approving a gated action (e.g., send_vendor_message), the
        action-gate enforce() is called to demonstrate the structural
        security boundary. Rejected approvals do not execute.
        """
        producer: EventProducerApp = app.state.event_producer
        approvals = producer.event_store.get_approvals(_DEMO_EVENT_ID)
        approval = next((a for a in approvals if a.id == approval_id), None)
        if approval is None:
            raise HTTPException(status_code=404, detail="Approval not found")

        if body.action == "reject":
            approval.status = "rejected"
            approval.approved_by = "demo-user"
            producer.event_store.save_approval(_DEMO_EVENT_ID, approval)
            return approval.model_dump()

        # body.action == "approve"
        approval.status = "approved"
        approval.approved_by = "demo-user"

        # Enforce the action-gate for gated actions
        if approval.action in {"send_vendor_message", "change_payment_details",
                               "mark_paid", "reschedule", "change_scope",
                               "approve_budget", "lock_scope", "release_funds"}:
            enforce(approval.action, approval)
            # Simulated vendor send: log to audit
            producer.audit_log.log(
                action="vendor_send_simulated",
                actor="demo-user",
                details=f"Simulated send for approval {approval_id}",
                approval_id=approval_id,
                event_id=_DEMO_EVENT_ID,
            )

        producer.event_store.save_approval(_DEMO_EVENT_ID, approval)
        return approval.model_dump()

    @app.post("/chat")
    async def chat(req: ChatRequest) -> dict[str, str]:
        """Chat endpoint (stub — acknowledges the message)."""
        print(f"[chat] Received message: {req.message}")
        return {
            "reply": f"Received: {req.message}. The orchestrator will process this."
        }

    return app
