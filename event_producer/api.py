"""FastAPI REST API wrapper for the Event Producer pipeline.

This module exposes a thin HTTP interface around ``EventProducerApp.run_event()``.
All business logic remains in the app layer; the API only handles serialization
and HTTP concerns.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
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
from event_producer.agents.cards import load_agent_cards
from event_producer.main import EventProducerApp
from event_producer.seeds import ensure_demo_casefiles
from event_producer.models.schemas import (
    Approval,
    BudgetSummary,
    CasefileArtifact,
    CasefileState,
    CasefileSummary,
    EventBasics,
    Proposal,
    RunEventRequest as RunEventSchema,
    ManualConstraintFlags,
    ScopeItem,
    ScopeItemCreate,
    ScopeItemUpdate,
    SpecialistAgentId,
    SpecialistAgentRequest,
    VendorCopyDraft,
    VendorCreateRequest,
    VendorDraftRecord,
    VendorLogCreateRequest,
    VendorUpdateRequest,
)
from event_producer.providers.agent_model import LiveModelProviderError
from event_producer.security.action_gate import enforce, requires_approval
from event_producer.storage.vendor_notebook import VendorNotFoundError


def _load_repo_env() -> None:
    """Load gitignored local .env values without overriding shell-provided env."""
    if (os.environ.get("EVENT_PRODUCER_LOAD_DOTENV", "true") or "").strip().lower() == "false":
        return
    for key, value in read_env_file().items():
        if key and key not in os.environ:
            os.environ[key] = value


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

    brief: str | None = None
    casefile_id: str | None = None
    basics: EventBasics | None = None
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
            brief=self.brief or "",
            budget_cap=self.budget_cap,
            contingency_pct=self.contingency_pct,
            attendees=self.attendees,
            event_type=self.event_type,
            venue_type=self.venue_type,
            date=self.date,
            manual_constraints=self.manual_constraints,
        )


class CasefileCreateRequest(BaseModel):
    """Request body for creating a saved local casefile."""

    basics: EventBasics = Field(default_factory=EventBasics)
    brief: str = ""


class CasefileBriefUpdateRequest(BaseModel):
    """Request body for saving a casefile brief."""

    brief: str = ""


class MarketRealismWarningDismissRequest(BaseModel):
    """Request body for dismissing a soft market-realism advisory."""

    warning: str


class RunSheetTaskStatusUpdateRequest(BaseModel):
    """Persisted operator state for a generated run-of-show task."""

    status: Literal["Scheduled", "Critical path", "In progress", "Blocked", "Complete", "At risk"]
    notes: str | None = None


class VendorCopyArtifactResponse(BaseModel):
    """Reviewable vendor-copy draft plus casefile artifact metadata."""

    event_id: str
    artifact: CasefileArtifact | None = None
    draft: VendorCopyDraft


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
    strict_live_model: bool
    effective_mode: str
    model_name: str
    api_base_url: str | None
    has_api_key: bool
    request_timeout_seconds: int
    fallback_reason: str | None = None


class RuntimeModelTestRequest(BaseModel):
    """Optional tiny prompt override for ``POST /runtime/model/test``."""

    prompt: str | None = None


class RuntimeModelTestResponse(BaseModel):
    """Non-secret provider call diagnostic response."""

    provider: str
    effective_mode: str
    model_name: str
    has_api_key: bool
    ok: bool
    latency_ms: int | None = None
    http_status: int | None = None
    response_shape_keys: list[str] = []
    response_preview: str | None = None
    response_format_mode: str | None = None
    repaired_schema: bool = False
    repaired_fields: list[str] = []
    error: str | None = None
    fallback_reason: str | None = None
    agent_name: str | None = None
    prompt_version: str | None = None


class _ProviderProbe(BaseModel):
    """Expected tiny JSON object returned by provider diagnostics."""

    ok: bool
    message: str


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        A configured ``FastAPI`` instance with all routes registered.
    """
    _load_repo_env()
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
    _allowed_origins = os.environ.get("ALLOWED_ORIGINS", "")
    if _allowed_origins.strip():
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[o.strip() for o in _allowed_origins.split(",") if o.strip()],
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        # Local dev default: the Next dev server may bind any localhost port.
        app.add_middleware(
            CORSMiddleware,
            allow_origin_regex=r"http://(localhost|127\.0\.0\.1):\d+",
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

    def _casefile_or_404(event_id: str) -> CasefileState:
        producer: EventProducerApp = app.state.event_producer
        try:
            return producer.casefile_store.get_casefile(event_id)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Casefile not found")

    @app.post("/casefiles")
    async def create_casefile(req: CasefileCreateRequest) -> dict[str, Any]:
        """Create a local saved event casefile before agent generation."""
        producer: EventProducerApp = app.state.event_producer
        casefile = producer.casefile_store.create_casefile(req.basics, req.brief)
        return casefile.model_dump(mode="json")

    @app.get("/casefiles")
    async def list_casefiles() -> list[dict[str, Any]]:
        """List saved local casefiles by most recent update."""
        producer: EventProducerApp = app.state.event_producer
        summaries: list[CasefileSummary] = producer.casefile_store.list_casefiles()
        return [summary.model_dump(mode="json") for summary in summaries]

    @app.post("/casefiles/seed")
    async def seed_casefiles() -> dict[str, Any]:
        """Materialize the committed demo casefiles (idempotent) and list them.

        The two seeds ship with the repo so a fresh clone has reference events
        to explore. Existing seeds are left untouched.
        """
        producer: EventProducerApp = app.state.event_producer
        seeded_ids = ensure_demo_casefiles(producer)
        summaries = producer.casefile_store.list_casefiles()
        return {
            "seeded_ids": seeded_ids,
            "casefiles": [summary.model_dump(mode="json") for summary in summaries],
        }

    @app.get("/casefiles/{event_id}")
    async def get_casefile(event_id: str) -> dict[str, Any]:
        """Load a full local casefile."""
        return _casefile_or_404(event_id).model_dump(mode="json")

    @app.delete("/casefiles/{event_id}")
    async def delete_casefile(event_id: str) -> dict[str, Any]:
        """Delete a local casefile and all of its artifacts.

        This is local demo-data management: casefiles live in the gitignored
        local store, so removing one touches no vendor comms or financial
        state and needs no approval gate. A missing casefile returns 404.
        Seed casefiles can be restored later via the "Seed Demo" action.
        """
        producer: EventProducerApp = app.state.event_producer
        _casefile_or_404(event_id)
        producer.casefile_store.delete_casefile(event_id)
        return {"event_id": event_id, "deleted": True}

    @app.patch("/casefiles/{event_id}/basics")
    async def update_casefile_basics(event_id: str, basics: EventBasics) -> dict[str, Any]:
        """Update canonical event basics and re-resolve state."""
        producer: EventProducerApp = app.state.event_producer
        _casefile_or_404(event_id)
        return producer.casefile_store.update_basics(event_id, basics).model_dump(mode="json")

    @app.put("/casefiles/{event_id}/brief")
    async def update_casefile_brief(
        event_id: str,
        req: CasefileBriefUpdateRequest,
    ) -> dict[str, Any]:
        """Update casefile brief text and re-resolve conflicts/missing fields."""
        producer: EventProducerApp = app.state.event_producer
        _casefile_or_404(event_id)
        return producer.casefile_store.update_brief(event_id, req.brief).model_dump(mode="json")

    @app.post("/casefiles/{event_id}/warnings/market-realism/dismiss")
    async def dismiss_casefile_market_realism_warning(
        event_id: str,
        req: MarketRealismWarningDismissRequest,
    ) -> dict[str, Any]:
        """Hide a soft budget realism warning for this casefile."""
        producer: EventProducerApp = app.state.event_producer
        _casefile_or_404(event_id)
        warning = req.warning.strip()
        if not warning:
            raise HTTPException(status_code=422, detail="warning is required")
        return producer.casefile_store.dismiss_market_realism_warning(
            event_id,
            warning,
        ).model_dump(mode="json")

    @app.patch("/casefiles/{event_id}/run-sheet/tasks/{task_id}")
    async def update_casefile_run_sheet_task(
        event_id: str,
        task_id: str,
        req: RunSheetTaskStatusUpdateRequest,
    ) -> dict[str, Any]:
        """Persist status/notes for a generated run-of-show task."""
        producer: EventProducerApp = app.state.event_producer
        _casefile_or_404(event_id)
        snapshot = producer.get_run_snapshot(event_id)
        schedule = (snapshot or {}).get("schedule_result") or {}
        task_ids = {
            str(task.get("id"))
            for task in schedule.get("ordered_tasks", [])
            if isinstance(task, dict) and task.get("id")
        }
        if not task_ids:
            raise HTTPException(status_code=409, detail="Run sheet has not been generated yet")
        if task_id not in task_ids:
            raise HTTPException(status_code=404, detail="Run sheet task not found")
        return producer.casefile_store.update_run_sheet_task_status(
            event_id,
            task_id,
            status=req.status,
            notes=req.notes,
        ).model_dump(mode="json")

    @app.post("/casefiles/{event_id}/requirements/confirm")
    async def confirm_casefile_requirements(event_id: str, request: Request) -> dict[str, Any]:
        """Mark the current resolved casefile requirements as confirmed."""
        producer: EventProducerApp = app.state.event_producer
        _casefile_or_404(event_id)
        actor = request.headers.get("x-demo-user") or "demo-user"
        return producer.casefile_store.confirm_requirements(event_id, actor=actor).model_dump(mode="json")

    @app.get("/casefiles/{event_id}/next-step")
    async def get_casefile_next_step(event_id: str) -> dict[str, Any]:
        """Return backend-derived next best step guidance for a casefile."""
        casefile = _casefile_or_404(event_id)
        if casefile.next_step is None:
            raise HTTPException(status_code=500, detail="Next step unavailable")
        return casefile.next_step.model_dump(mode="json")

    @app.post("/casefiles/{event_id}/agents/{agent_id}/run")
    async def run_casefile_specialist_agent(
        event_id: str,
        agent_id: SpecialistAgentId,
        req: SpecialistAgentRequest,
    ) -> dict[str, Any]:
        """Run one direct specialist against server-loaded saved casefile context."""
        producer: EventProducerApp = app.state.event_producer
        _casefile_or_404(event_id)
        if req.vendor_id:
            if agent_id != "vendor_copy":
                raise HTTPException(status_code=422, detail="vendor_id only applies to vendor_copy runs")
            _vendor_or_404(event_id, req.vendor_id)
        response = producer.run_specialist_agent(
            event_id,
            agent_id,
            instruction=req.instruction,
            regenerate=req.regenerate,
            artifact_id=req.artifact_id,
            vendor_id=req.vendor_id,
        )
        return response.model_dump(mode="json")

    _READABLE_ARTIFACTS = {
        "brief-intake",
        "creative-concept",
        "scope-strategy",
        "budget-summary",
        "run-sheet",
        "vendor-copy",
        "vendor-notebook",
        "risk-review",
        "run-snapshot",
    }

    @app.get("/casefiles/{event_id}/run-snapshot")
    async def get_casefile_run_snapshot(event_id: str) -> dict[str, Any]:
        """Return the last persisted pipeline run for a saved casefile.

        Also rehydrates the in-memory event runtime so scope edits, chat, and
        approvals keep working after a backend restart.
        """
        producer: EventProducerApp = app.state.event_producer
        casefile = _casefile_or_404(event_id)
        snapshot = producer.get_run_snapshot(event_id)
        if snapshot is None:
            raise HTTPException(status_code=404, detail="No saved run for this casefile yet")
        producer.ensure_event_runtime(event_id)
        snapshot["casefile"] = casefile.model_dump(mode="json")
        snapshot["resolved_event_state"] = casefile.resolved.model_dump(mode="json")
        snapshot["requirements"] = casefile.requirements.model_dump(mode="json") if casefile.requirements else None
        snapshot["next_step"] = casefile.next_step.model_dump(mode="json") if casefile.next_step else None
        return snapshot

    @app.get("/settings/storage")
    async def get_storage_info() -> dict[str, Any]:
        """Describe where casefiles are stored locally (demo storage, not cloud)."""
        producer: EventProducerApp = app.state.event_producer
        store = producer.casefile_store
        return {
            "root": str(store.root.resolve()),
            "casefile_count": len(store.list_casefiles()),
            "storage_kind": "local_json",
        }

    @app.get("/agents")
    async def get_agent_registry() -> dict[str, Any]:
        """Serve the agent skill-card registry (the crew's runtime contracts).

        Cards live as versioned markdown files under
        ``event_producer/agents/cards/`` and are parsed/validated at load
        time; the Mission Control UI renders the crew board from this
        endpoint rather than from hardcoded frontend copy.
        """
        return {"agents": load_agent_cards()}

    @app.get("/casefiles/{event_id}/artifacts/vendor-copy")
    async def get_vendor_copy_artifact(event_id: str) -> dict[str, Any]:
        """Return the current reviewable vendor-copy draft for a saved casefile."""
        producer: EventProducerApp = app.state.event_producer
        _casefile_or_404(event_id)
        draft, artifact = producer.get_vendor_copy_draft(event_id)
        return VendorCopyArtifactResponse(
            event_id=event_id,
            artifact=artifact,
            draft=draft,
        ).model_dump(mode="json")

    @app.put("/casefiles/{event_id}/artifacts/vendor-copy")
    async def save_vendor_copy_artifact(event_id: str, draft: VendorCopyDraft) -> dict[str, Any]:
        """Save user-edited vendor copy without approving or executing outreach."""
        producer: EventProducerApp = app.state.event_producer
        _casefile_or_404(event_id)
        saved, artifact = producer.save_vendor_copy_draft(event_id, draft)
        return VendorCopyArtifactResponse(
            event_id=event_id,
            artifact=artifact,
            draft=saved,
        ).model_dump(mode="json")

    # ---- Vendor Notebook (persistent per-vendor workspace) ----------------
    # Planning metadata only: drafts are copied manually, payments are
    # user-recorded status, nothing is sent or executed from the app.

    def _vendor_or_404(event_id: str, vendor_id: str) -> None:
        producer: EventProducerApp = app.state.event_producer
        try:
            producer.vendor_notebook.get_vendor(event_id, vendor_id)
        except VendorNotFoundError:
            raise HTTPException(status_code=404, detail="Vendor not found in this casefile")

    @app.get("/casefiles/{event_id}/vendors")
    async def list_casefile_vendors(event_id: str) -> dict[str, Any]:
        """List the casefile's saved vendors with logs, drafts, and statuses."""
        producer: EventProducerApp = app.state.event_producer
        _casefile_or_404(event_id)
        vendors = producer.vendor_notebook.list_vendors(event_id)
        return {"event_id": event_id, "vendors": [v.model_dump(mode="json") for v in vendors]}

    @app.post("/casefiles/{event_id}/vendors")
    async def create_casefile_vendor(event_id: str, req: VendorCreateRequest) -> dict[str, Any]:
        """Add a vendor to the casefile's notebook."""
        producer: EventProducerApp = app.state.event_producer
        _casefile_or_404(event_id)
        vendor = producer.vendor_notebook.add_vendor(event_id, req.model_dump())
        return vendor.model_dump(mode="json")

    @app.patch("/casefiles/{event_id}/vendors/{vendor_id}")
    async def update_casefile_vendor(
        event_id: str, vendor_id: str, req: VendorUpdateRequest
    ) -> dict[str, Any]:
        """Update vendor profile, workflow status, or payment planning fields."""
        producer: EventProducerApp = app.state.event_producer
        _casefile_or_404(event_id)
        _vendor_or_404(event_id, vendor_id)
        vendor = producer.vendor_notebook.update_vendor(
            event_id, vendor_id, req.model_dump(exclude_none=True)
        )
        return vendor.model_dump(mode="json")

    @app.delete("/casefiles/{event_id}/vendors/{vendor_id}")
    async def delete_casefile_vendor(event_id: str, vendor_id: str) -> dict[str, Any]:
        """Remove a vendor from the notebook (recorded in the casefile timeline)."""
        producer: EventProducerApp = app.state.event_producer
        _casefile_or_404(event_id)
        _vendor_or_404(event_id, vendor_id)
        producer.vendor_notebook.delete_vendor(event_id, vendor_id)
        return {"event_id": event_id, "vendor_id": vendor_id, "deleted": True}

    @app.post("/casefiles/{event_id}/vendors/{vendor_id}/log")
    async def append_casefile_vendor_log(
        event_id: str, vendor_id: str, req: VendorLogCreateRequest
    ) -> dict[str, Any]:
        """Log a manual note or a vendor response (injection-screened on entry)."""
        producer: EventProducerApp = app.state.event_producer
        _casefile_or_404(event_id)
        _vendor_or_404(event_id, vendor_id)
        entry = producer.vendor_notebook.append_log(
            event_id,
            vendor_id,
            type=req.type,
            title=req.title
            or ("Vendor response logged" if req.type == "vendor_response_logged" else "Note"),
            body=req.body,
            actor="user",
        )
        return entry.model_dump(mode="json")

    @app.put("/casefiles/{event_id}/vendors/{vendor_id}/draft")
    async def save_casefile_vendor_draft(
        event_id: str, vendor_id: str, draft: VendorDraftRecord
    ) -> dict[str, Any]:
        """Save user edits to the vendor's current draft (draft-only, no send)."""
        producer: EventProducerApp = app.state.event_producer
        _casefile_or_404(event_id)
        _vendor_or_404(event_id, vendor_id)
        vendor = producer.vendor_notebook.save_draft(event_id, vendor_id, draft)
        return vendor.model_dump(mode="json")

    @app.post("/casefiles/{event_id}/vendors/{vendor_id}/draft/mark-copied")
    async def mark_casefile_vendor_draft_copied(event_id: str, vendor_id: str) -> dict[str, Any]:
        """Record that the draft was copied for manual send outside the app."""
        producer: EventProducerApp = app.state.event_producer
        _casefile_or_404(event_id)
        _vendor_or_404(event_id, vendor_id)
        try:
            vendor = producer.vendor_notebook.mark_draft_copied(event_id, vendor_id)
        except VendorNotFoundError:
            raise HTTPException(status_code=409, detail="This vendor has no draft yet")
        return vendor.model_dump(mode="json")

    @app.post("/casefiles/{event_id}/vendors/{vendor_id}/draft/mark-manually-sent")
    async def mark_casefile_vendor_draft_sent(event_id: str, vendor_id: str) -> dict[str, Any]:
        """Record that the user sent the draft outside the app. Sends nothing."""
        producer: EventProducerApp = app.state.event_producer
        _casefile_or_404(event_id)
        _vendor_or_404(event_id, vendor_id)
        try:
            vendor = producer.vendor_notebook.mark_draft_manually_sent(event_id, vendor_id)
        except VendorNotFoundError:
            raise HTTPException(status_code=409, detail="This vendor has no draft yet")
        return vendor.model_dump(mode="json")

    # Registered after the vendor-copy routes so those keep their richer shape.
    @app.get("/casefiles/{event_id}/artifacts/{artifact_name}")
    async def get_casefile_artifact(event_id: str, artifact_name: str) -> dict[str, Any]:
        """Return one saved casefile artifact payload by name."""
        if artifact_name not in _READABLE_ARTIFACTS:
            raise HTTPException(status_code=404, detail="Unknown artifact name")
        producer: EventProducerApp = app.state.event_producer
        _casefile_or_404(event_id)
        try:
            payload = producer.casefile_store.read_artifact(event_id, artifact_name)
        except FileNotFoundError:
            raise HTTPException(status_code=404, detail="Artifact not saved yet")
        return {"event_id": event_id, "name": artifact_name, "payload": payload}

    @app.post("/run")
    async def run_event(req: RunEventRequest) -> Any:
        """Run the full event production pipeline and return the result."""
        producer: EventProducerApp = app.state.event_producer
        try:
            if req.casefile_id:
                _casefile_or_404(req.casefile_id)
                if req.basics is not None:
                    producer.casefile_store.update_basics(req.casefile_id, req.basics)
                if req.brief is not None:
                    producer.casefile_store.update_brief(req.casefile_id, req.brief)
                result = producer.run_casefile(req.casefile_id)
            elif req.basics is not None:
                casefile = producer.casefile_store.create_casefile(
                    req.basics,
                    req.brief or "",
                )
                result = producer.run_casefile(casefile.event_id)
            else:
                if req.brief is None:
                    raise HTTPException(status_code=422, detail="brief is required when no casefile is supplied")
                basics = EventBasics(
                    budget_cap=Decimal(req.budget_cap) if req.budget_cap is not None else None,
                    start_date=req.date or "",
                    end_date=req.date or "",
                    expected_turnout=req.attendees,
                    event_type=req.event_type or "",
                )
                casefile = producer.casefile_store.create_casefile(basics, req.brief)
                producer.casefile_store.append_timeline(casefile.event_id, "agent_run_started", {})
                result = producer.run_event(
                    brief=req.brief,
                    budget_cap=req.budget_cap,
                    contingency_pct=req.contingency_pct,
                    attendees=req.attendees,
                    event_type=req.event_type,
                    venue_type=req.venue_type,
                    date=req.date,
                    manual_constraints=req.manual_constraints,
                    event_id=casefile.event_id,
                )
                producer._persist_casefile_artifacts(casefile.event_id, result)
                casefile = producer.casefile_store.mark_generated(casefile.event_id, {})
                producer.casefile_store.append_timeline(casefile.event_id, "agent_run_completed", {"status": "generated"})
                result["casefile"] = casefile.model_dump(mode="json")
                result["resolved_event_state"] = casefile.resolved.model_dump(mode="json")
                result["requirements"] = casefile.requirements.model_dump(mode="json") if casefile.requirements else None
                result["next_step"] = casefile.next_step.model_dump(mode="json") if casefile.next_step else None
        except LiveModelProviderError as exc:
            return JSONResponse(
                status_code=502,
                content={
                    "error": {
                        "code": "LIVE_MODEL_PROVIDER_FAILED",
                        "message": exc.message,
                        "provider": exc.provider,
                        "model_name": exc.model_name,
                        "agent_name": exc.agent_name,
                        "response_format_mode": exc.response_format_mode,
                        "repaired_schema": exc.repaired_schema,
                        "repaired_fields": exc.repaired_fields,
                    }
                },
            )
        return result

    @app.get("/event/{event_id}")
    async def get_event(event_id: str) -> dict[str, Any]:
        """Retrieve full event state by its ID."""
        producer: EventProducerApp = app.state.event_producer
        producer.ensure_event_runtime(event_id)
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
            strict_live_model=env.strict_live_model,
            effective_mode=env.effective_mode,
            model_name=env.model_name,
            api_base_url=env.api_base_url or None,
            has_api_key=bool(env.api_key),
            request_timeout_seconds=env.request_timeout_seconds,
            fallback_reason=env.fallback_reason or None,
        )

    @app.post("/runtime/model/test")
    async def runtime_model_test(
        req: RuntimeModelTestRequest | None = None,
    ) -> RuntimeModelTestResponse:
        """Run one tiny selected-provider call and return non-secret diagnostics."""
        producer: EventProducerApp = app.state.event_producer
        env = producer._model_env
        if env.effective_mode == "rule_based_fallback":
            return RuntimeModelTestResponse(
                provider=env.provider,
                effective_mode=env.effective_mode,
                model_name=env.model_name,
                has_api_key=bool(env.api_key),
                ok=False,
                error=env.fallback_reason or "live provider not configured",
                fallback_reason=env.fallback_reason or "live_provider_not_configured",
                agent_name="provider_diagnostic",
                prompt_version="provider_diagnostic.v1",
            )

        prompt = (
            (req.prompt if req else None)
            or 'Return exactly JSON: {"ok": true, "message": "provider reachable"}.'
        )
        try:
            result = producer._agent_model.generate_structured(
                agent_name="provider_diagnostic",
                prompt_version="provider_diagnostic.v1",
                system_prompt=(
                    "You are a connectivity diagnostic. Return only a JSON object "
                    "matching the requested schema. Do not include secrets."
                ),
                user_prompt=prompt,
                schema=_ProviderProbe,
            )
        except LiveModelProviderError as exc:
            return RuntimeModelTestResponse(
                provider=exc.provider,
                effective_mode=exc.effective_mode,
                model_name=exc.model_name or env.model_name,
                has_api_key=bool(env.api_key),
                ok=False,
                http_status=exc.http_status,
                response_shape_keys=exc.response_shape_keys,
                response_format_mode=exc.response_format_mode,
                repaired_schema=exc.repaired_schema,
                repaired_fields=exc.repaired_fields,
                error=exc.message,
                fallback_reason=exc.fallback_reason or "provider_test_failed",
                agent_name=exc.agent_name,
                prompt_version=exc.prompt_version,
            )

        return RuntimeModelTestResponse(
            provider=result.provider or env.provider,
            effective_mode=result.effective_mode or env.effective_mode,
            model_name=result.model_name or env.model_name,
            has_api_key=bool(env.api_key),
            ok=result.ok and result.parsed is not None,
            latency_ms=result.latency_ms,
            http_status=result.http_status,
            response_shape_keys=result.response_shape_keys,
            response_preview=result.response_preview or result.raw_text,
            response_format_mode=result.response_format_mode,
            repaired_schema=result.repaired_schema,
            repaired_fields=result.repaired_fields,
            error=result.error,
            fallback_reason=result.fallback_reason,
            agent_name=result.agent_name,
            prompt_version=result.prompt_version,
        )

    def _public_model_settings(*, restart_required: bool = False) -> ModelSettingsPublic:
        producer: EventProducerApp = app.state.event_producer
        env = producer._model_env
        return ModelSettingsPublic(
            provider=env.provider,
            live_enabled=env.live_enabled,
            strict_live_model=env.strict_live_model,
            effective_mode=env.effective_mode,
            model_name=env.model_name,
            api_base_url=env.api_base_url or None,
            has_api_key=bool(env.api_key),
            request_timeout_seconds=env.request_timeout_seconds,
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

        def persist_approval_state() -> None:
            saved = [
                a.model_dump(mode="json")
                for a in producer.event_store.get_approvals(event_id)
            ]
            snapshot_updates: dict[str, Any] = {"approvals": saved}
            snapshot = producer.get_run_snapshot(event_id)
            if isinstance(snapshot, dict) and isinstance(snapshot.get("run_of_show"), dict):
                run_of_show = dict(snapshot["run_of_show"])
                run_of_show["approvals"] = saved
                snapshot_updates["run_of_show"] = run_of_show
            producer.update_run_snapshot(event_id, snapshot_updates)

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
            persist_approval_state()
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
        persist_approval_state()
        return approval.model_dump()

    @app.get("/event/{event_id}/approvals")
    async def list_event_approvals(event_id: str) -> list[dict[str, Any]]:
        """List approvals for one event."""
        producer: EventProducerApp = app.state.event_producer
        producer.ensure_event_runtime(event_id)
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
        producer.ensure_event_runtime(event_id)
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

        # Reporting currency follows the saved casefile; scope items carry
        # their own currency, so an event without a casefile stays USD.
        reporting_currency = "USD"
        try:
            reporting_currency = (
                producer.casefile_store.get_casefile(event_id).resolved.basics.currency
                or "USD"
            )
        except FileNotFoundError:
            if scope_items:
                reporting_currency = scope_items[0].currency or "USD"

        budget_request = {
            "scope_items": [s.model_dump() for s in scope_items],
            "budget_cap": budget_cap,
            "contingency_pct": contingency_pct,
            "reporting_currency": reporting_currency,
            # Count every selected item; Include/Exclude is the only gate.
            "gate_discretionary_tiers": False,
        }
        budget_raw = producer._budget_reason.run(budget_request)
        budget_validated = producer._budget_formatter.run(budget_raw)
        budget_summary = budget_validated["budget_summary"]
        updated_budget = BudgetSummary(**budget_summary)
        producer.event_store.save_budget(event_id, updated_budget)

        # Recompute schedule (best effort; may be None). The production
        # manager anchors the day-of run-of-show to the event date itself.
        production_request = {
            "event_spec": event_spec.model_dump(),
            "scope_items": [s.model_dump() for s in scope_items],
        }
        production_raw = producer._production_reason.run(production_request)
        production_validated = producer._production_formatter.run(production_raw)

        schedule_result = None
        call_sheet = []
        booking_deadlines = list(production_validated.get("booking_deadlines", []))
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
        headroom_changed = previous_headroom is None or previous_headroom != updated_budget.headroom
        if headroom_changed:
            headroom_message = f"Headroom changed from {previous_headroom_text} to {current_headroom_text}."
        else:
            # Every selected item counts, so an unchanged headroom means the
            # edit touched an excluded item (or left the counted total as-is).
            headroom_message = (
                f"Headroom unchanged at {current_headroom_text} — this edit did not change "
                "the items counted toward the budget."
            )

        payload = {
            "scope_items": [s.model_dump() for s in scope_items],
            "budget_summary": budget_summary,
            "schedule_result": schedule_result.model_dump() if schedule_result else None,
            "call_sheet": [c.model_dump() for c in call_sheet],
            "booking_deadlines": booking_deadlines,
            "recompute_notice": {
                "previous_headroom": previous_headroom_text,
                "current_headroom": current_headroom_text,
                "schedule_status": "recomputed" if schedule_result else "warning",
                "message": (
                    f"Budget recalculated. {headroom_message} {schedule_message} "
                    "Risk register and agent trace still reflect the last full pipeline run."
                ),
            },
        }
        # Keep the saved casefile in sync so a reload shows the edited state.
        producer.update_run_snapshot(
            event_id,
            {
                "scope_items": payload["scope_items"],
                "budget_summary": payload["budget_summary"],
                "schedule_result": payload["schedule_result"],
                "call_sheet": payload["call_sheet"],
                "booking_deadlines": payload["booking_deadlines"],
            },
        )
        return payload

    # P7B scope mutation uses a generic event_id parameter; the store is keyed by event_id.
    # Using a query parameter for demo purposes (frontend drives event_id from last /run result).

    @app.post("/event/{event_id}/scope-items")
    async def add_scope_item(event_id: str, req: ScopeItemCreate) -> dict[str, Any]:
        """Add a new scope item to an event and recompute budget."""
        producer: EventProducerApp = app.state.event_producer

        producer.ensure_event_runtime(event_id)
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

        producer.ensure_event_runtime(event_id)
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

        producer.ensure_event_runtime(event_id)
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

        producer.ensure_event_runtime(event_id)
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

        producer.ensure_event_runtime(event_id)
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

    @app.post("/event/{event_id}/scope-items/auto-fit")
    async def auto_fit_scope(event_id: str) -> dict[str, Any]:
        """Select the highest-priority scope items that fit the budget.

        Runs the Budget Engine in "fit to budget" mode (greedy tier gating)
        over every item to decide which whole tiers fit the spendable pool,
        then sets each item's selected flag to match. Nothing is deleted, so
        the user can re-include any item afterward. Budget and schedule are
        then recomputed in count-all mode so headroom reflects the selection.
        """
        producer: EventProducerApp = app.state.event_producer

        producer.ensure_event_runtime(event_id)
        scope = producer.event_store.get_scope(event_id)
        if not scope and event_id != _DEMO_EVENT_ID:
            raise HTTPException(status_code=404, detail="Event not found")
        if not scope:
            return _recompute_event(event_id)

        existing_budget = producer.event_store.get_budget(event_id)
        budget_cap = (
            existing_budget.budget_cap if existing_budget
            else Decimal(str(DEFAULT_EVENT_CONSTRAINTS["budget_cap"]))
        )
        contingency_pct = (
            existing_budget.contingency_pct if existing_budget
            else Decimal(str(DEFAULT_EVENT_CONSTRAINTS["contingency_pct"]))
        )
        reporting_currency = "USD"
        try:
            reporting_currency = (
                producer.casefile_store.get_casefile(event_id).resolved.basics.currency
                or "USD"
            )
        except FileNotFoundError:
            reporting_currency = scope[0].currency or "USD"

        # Consider every item (ignore current selection) and let the engine
        # greedily gate whole tiers to fit the spendable pool.
        fit_request = {
            "scope_items": [{**s.model_dump(), "selected": True} for s in scope],
            "budget_cap": budget_cap,
            "contingency_pct": contingency_pct,
            "reporting_currency": reporting_currency,
            "gate_discretionary_tiers": True,
        }
        fit_raw = producer._budget_reason.run(fit_request)
        tier_inclusion = fit_raw["budget_summary"]["tier_inclusion"]

        for item in scope:
            item.selected = bool(tier_inclusion.get(item.tier, item.tier == "must"))
        producer.event_store.save_scope(event_id, scope)
        producer.audit_log.log(
            action="auto_fit_scope",
            actor="demo-user",
            details=f"Auto-fit scope to budget for event {event_id}",
            event_id=event_id,
        )

        return _recompute_event(event_id)

    # ---------------------------------------------------------------------------
    # P7B — Orchestrator chat and proposal application
    # ---------------------------------------------------------------------------

    @app.post("/event/{event_id}/chat")
    async def orchestrator_chat(
        event_id: str, req: OrchestratorChatRequest
    ) -> Any:
        """Chat with the orchestrator; returns proposed actions, no mutation.

        Proposals are stored server-side; the response includes the stored
        proposal IDs for apply/dismiss operations.
        """
        producer: EventProducerApp = app.state.event_producer
        producer.ensure_event_runtime(event_id)

        # Fetch event context for the orchestrator
        event_spec = producer.event_store.get_event(event_id)
        scope_items = producer.event_store.get_scope(event_id)
        budget_summary = producer.event_store.get_budget(event_id)
        schedule_result = producer.event_store.get_schedule(event_id)
        run_of_show = producer.event_store.get_run_of_show(event_id)
        approvals = producer.event_store.get_approvals(event_id)

        if not event_spec:
            raise HTTPException(status_code=404, detail="Event not found")

        if (
            producer._model_env.live_enabled
            and producer._model_env.strict_live_model
            and producer._model_env.effective_mode == "rule_based_fallback"
        ):
            return JSONResponse(
                status_code=502,
                content={
                    "error": {
                        "code": "LIVE_MODEL_PROVIDER_FAILED",
                        "message": (
                            "Live provider is not callable for Orchestrator: "
                            f"{producer._model_env.fallback_reason}"
                        ),
                        "provider": producer._model_env.provider,
                        "model_name": producer._model_env.model_name,
                        "agent_name": "orchestrator",
                    }
                },
            )

        # Build context for the orchestrator agent
        context = {
            "event_id": event_id,
            "event_spec": event_spec.model_dump(),
            "scope_items": [s.model_dump() for s in scope_items],
            "budget_summary": budget_summary.model_dump() if budget_summary else None,
            "schedule_result": schedule_result.model_dump() if schedule_result else None,
            "approvals": [a.model_dump() for a in approvals],
            "risk_flags": [r.model_dump() for r in run_of_show.risk_flags] if run_of_show else [],
        }

        # The orchestrator agent returns proposed actions
        try:
            result = producer._orchestrator.run(req.message, context)
        except LiveModelProviderError as exc:
            return JSONResponse(
                status_code=502,
                content={
                    "error": {
                        "code": "LIVE_MODEL_PROVIDER_FAILED",
                        "message": exc.message,
                        "provider": exc.provider,
                        "model_name": exc.model_name,
                        "agent_name": exc.agent_name,
                        "response_format_mode": exc.response_format_mode,
                        "repaired_schema": exc.repaired_schema,
                        "repaired_fields": exc.repaired_fields,
                    }
                },
            )

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
        producer.ensure_event_runtime(event_id)

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
