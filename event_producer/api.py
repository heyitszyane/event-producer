"""FastAPI REST API wrapper for the Event Producer pipeline.

This module exposes a thin HTTP interface around ``EventProducerApp.run_event()``.
All business logic remains in the app layer; the API only handles serialization
and HTTP concerns.
"""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from event_producer.main import EventProducerApp

# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class RunEventRequest(BaseModel):
    """Request body for the ``POST /run`` endpoint."""

    brief: str
    budget_cap: str
    contingency_pct: str
    attendees: int
    event_type: str
    venue_type: str
    date: str


class ChatRequest(BaseModel):
    """Request body for the ``POST /chat`` endpoint."""

    message: str


class ApprovalAction(BaseModel):
    """Request body for the ``POST /approvals/{approval_id}`` endpoint."""

    action: str  # "approve" or "reject"


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
                    content={"detail": "Missing X-Demo-User header"},
                )
            return await call_next(request)

    app.add_middleware(DemoAuthMiddleware)

    # ---- CORS middleware (demo: allow all origins) -----------------------
    # Added last so it is the outermost middleware and can respond to
    # OPTIONS preflight requests before auth blocks them.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store the EventProducerApp instance on app.state so endpoints can
    # access it without re-instantiating on every request.
    app.state.event_producer = EventProducerApp()

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
        """Retrieve a previously produced event by its ID."""
        producer: EventProducerApp = app.state.event_producer
        event_spec = producer.event_store.get_event(event_id)
        if event_spec is None:
            raise HTTPException(status_code=404, detail="Event not found")
        return event_spec.model_dump()

    @app.get("/healthz")
    async def healthz() -> dict[str, str]:
        """Liveness probe."""
        return {"status": "ok"}

    # ---- Sample approvals (demo stub) ------------------------------------
    _SAMPLE_APPROVALS: list[dict[str, Any]] = [
        {
            "id": "aprv-001",
            "action": "send_vendor_message",
            "requested_by": "producer@example.com",
            "approved_by": "",
            "status": "pending",
            "timestamp": "2026-06-21T10:30:00",
            "notes": "Send RFP to Grand Ballroom Co. for venue booking.",
        },
        {
            "id": "aprv-002",
            "action": "confirm_budget_line",
            "requested_by": "budget-agent",
            "approved_by": "",
            "status": "pending",
            "timestamp": "2026-06-21T11:00:00",
            "notes": "Confirm catering budget line of $5,000 for 200 attendees.",
        },
        {
            "id": "aprv-003",
            "action": "execute_payment",
            "requested_by": "finance-agent",
            "approved_by": "",
            "status": "pending",
            "timestamp": "2026-06-21T11:15:00",
            "notes": "Release 50% deposit to AV vendor ($2,500).",
        },
    ]

    @app.get("/approvals")
    async def list_approvals() -> list[dict[str, Any]]:
        """List pending approvals (demo stub — returns sample data)."""
        return _SAMPLE_APPROVALS

    @app.post("/approvals/{approval_id}")
    async def update_approval(
        approval_id: str,
        body: ApprovalAction,
    ) -> dict[str, Any]:
        """Approve or reject a pending approval (demo stub).

        Returns the updated approval with status set to the requested action.
        This is a stub — real action-gate integration is future work.
        """
        for ap in _SAMPLE_APPROVALS:
            if ap["id"] == approval_id:
                ap["status"] = body.action == "approve" and "approved" or "rejected"
                ap["approved_by"] = "demo-user"
                return ap
        raise HTTPException(status_code=404, detail="Approval not found")

    @app.post("/chat")
    async def chat(req: ChatRequest) -> dict[str, str]:
        """Chat endpoint (stub — acknowledges the message)."""
        print(f"[chat] Received message: {req.message}")
        return {
            "reply": f"Received: {req.message}. The orchestrator will process this."
        }

    return app
