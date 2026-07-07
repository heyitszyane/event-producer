# REPO_SITEMAP.md -- Event Producer Folder Map

> This file describes the **current** repository layout as of P7H.5
> (structured-output hardening for the live-agentic showcase on top of
> P7F/P7E/P7D-FIX behavior).

---

## Root-Level Files

| File | Purpose |
|---|---|
| `README.md` | Front door -- project overview, setup instructions, quickstart |
| `CLAUDE.md` | Persistent instructions for AI coding agents working in this repo |
| `CHANGELOG.md` | Top-level changelog following the Keep-a-Changelog convention |
| `LICENSE` | CC-BY-4.0 license |
| `.gitignore` | Secrets-first ignore rules (see Gitignored section below) |
| `requirements.txt` | Pinned Python dependencies |

---

## Folder-by-Folder Breakdown

### `docs/`
Long-form documentation that does not belong in code-level docstrings. Currently holds this sitemap. Add architecture decision records (ADRs), runbooks, and integration guides here as the project matures.

### `changelogs/`
Per-phase detailed change logs that feed into the top-level `CHANGELOG.md`. Each phase (P0, P1, ...) gets its own file or subdirectory. This keeps the root changelog readable while preserving granular history.

### `project_documents/` *(GITIGNORED)*
Handover briefs, spec copies, and other working documents that should not be committed to version control. Subdirectory `handover-briefs/` is the default landing zone for phase-transition documents. `result-artifacts/` stores subagent output from the planner/generator/evaluator pipeline.

> **This entire directory is gitignored.** Do not commit files from here.

### `temp/` *(GITIGNORED)*
Scratch space for experiments, one-off scripts, and transient artifacts. Safe to delete at any time.

> **This entire directory is gitignored.** Do not commit files from here.

### `event_producer/` -- Main Python Package (Backend)

The core application code. Organized by architectural layer:

#### `event_producer/__init__.py`
Package marker. Exports top-level symbols if needed.

#### `event_producer/main.py`
Application entry point. Wires agents, engines, and providers into a runnable app. Contains `InMemoryEventStore` (full CRUD implementation of the `EventStore` ABC) and `EventProducerApp` (composition root).

#### `event_producer/api.py`
FastAPI REST API wrapper. Exposes `/run`, `/casefiles`, `/casefiles/seed` (materialize committed demo casefiles), `/casefiles/{id}`, `/casefiles/{id}/requirements/confirm`, `/casefiles/{id}/next-step`, `/casefiles/{id}/agents/{agent_id}/run`, `/casefiles/{id}/artifacts/vendor-copy`, `/runtime/model`, `/runtime/model/test`, `/settings/model`, `/event/{id}`, `/event/{id}/chat`, `/event/{id}/proposals/{id}/apply`, `/event/{id}/proposals/{id}/dismiss`, `/event/{id}/scope-items`, `/event/{id}/scope-items/{id}` (scope mutation), `/event/{id}/scope-items/{idx}/toggle`, `/event/{id}/scope-items/{idx}/retier`, `/event/{id}/scope-items/auto-fit` (engine trims lowest-priority tiers to fit the budget), `/event/{id}/approvals`, `/event/{id}/approvals/{approval_id}`, legacy sample `/approvals`, legacy sample `/approvals/{id}`, `/chat`, `/healthz`, and `GET /agents` (the agent skill-card registry, parsed from `event_producer/agents/cards/` at runtime). HITL approval flow with action-gate integration. CORS driven by `ALLOWED_ORIGINS` env var. Direct specialist-agent actions load saved casefile context server-side, save advisory artifacts, and append timeline entries without mutating critical event basics. Vendor-copy artifact endpoints load and save reviewable draft copy without approving or executing external actions. Scope/proposal mutation responses include recompute notices with before/after headroom, schedule status, and stale-agent-output honesty. Provider diagnostic responses are non-secret and surface strict-live failures with provider/model/agent context.

#### `event_producer/config/`
Small shared configuration constants.

| File | Purpose |
|---|---|
| `defaults.py` | Documented fallback constraints used by the deterministic demo pipeline |

#### `event_producer/agents/`
Role-based agents plus reasoner/formatter splits. Each agent file owns a single responsibility:

| File | Agent Role |
|---|---|
| `orchestrator.py` | Top-level coordinator; returns structured proposals for scope changes (P7B/P7D-FIX) |
| `brief_intake.py` | Extracts requirements from messy briefs, including date/location/headcount and market-realism warnings |
| `creative_concept.py` | Produces advisory creative ideas and add/cut suggestions through live/fallback model seam |
| `scope_strategy.py` | Produces advisory live/fallback scope tradeoffs and recommendations without mutating scope |
| `brief_scope.py` | Parses and validates event specs and attendee-scaled scope items |
| `budget_manager.py` | Owns budget allocation decisions (delegates math to Budget Engine) |
| `production_manager.py` | Manages production timeline and deliverables |
| `vendor_coordinator.py` | Handles vendor selection, live/fallback vendor draft generation, and gated communication |
| `risk_flagger.py` | Identifies and surfaces risks across all domains |
| `cards.py` | Loads + validates the agent skill-card registry from `cards/` (frontmatter contracts); `assemble_system_prompt` appends card bodies into the LLM agents' live prompts (load-bearing seam) |
| `cards/` | 10 versioned agent skill cards: YAML contract (capabilities, inputs/outputs, structural boundaries, prompt refs) + instruction body; served by `GET /agents`, rendered as the Mission Control crew board, and appended into live prompt assembly |
| `prompts/` | Versioned system prompts referenced by the live-capable agents and their skill cards |

Most role agents are rule-based (deterministic). Brief Intake, Creative
Concept, Scope Strategy, Vendor Draft, and Orchestrator can use the optional
server-side model provider seam when explicitly enabled; otherwise they run
honest fallback mode. Gemini is the default live provider; OpenRouter and
local/OpenAI-compatible endpoints are also supported. Live providers expose
non-secret structured-output diagnostics (`response_format_mode`,
`repaired_schema`, and `repaired_fields`) so schema drift can be debugged
without logging secrets or full prompts.

#### `event_producer/engines/`
Deterministic, pure-Python cores with no external dependencies. These are the "math" layer -- fully testable in isolation.

| File | Engine |
|---|---|
| `budget.py` | Budget allocation, tracking, and variance calculations. Decimal-only. Tier-gating. Multi-currency with line-total-first FX rounding. Receipt aggregation. |
| `scheduler.py` | Run-of-show CPM scheduler; produces time-coded production schedules. Dependency resolution, lead-time validation, anchor constraints, cycle detection, conflict reporting. |

#### `event_producer/models/`
Pydantic schemas shared across the codebase. Single file `schemas.py`. All monetary fields use `Decimal` (strict mode rejects float). Mutable defaults use `Field(default_factory=...)`. P7D-FIX adds `ManualConstraintFlags`, `BriefIntakeSourceMap`, and `RequirementSource` so API clients can distinguish brief extraction, manual overrides, fallback defaults, and missing values. P7L adds typed direct specialist-agent request/response contracts.

#### `event_producer/security/`
Action-gate enforcement, prompt-injection flagging, and audit logging. These modules form the trust boundary for all agent actions.

| File | Responsibility |
|---|---|
| `action_gate.py` | Gate checks before any side-effecting operation |
| `injection_flag.py` | Heuristic and model-based injection detection |
| `audit_log.py` | Immutable append-only audit trail for all gated actions |

#### `event_producer/providers/` -- Moat-Seam Boundary
Abstract interfaces that define the **seam** between the agent layer and external systems.

| File | Interface |
|---|---|
| `event_store.py` | Persistence for event data (CRUD contract). Includes `list_events()`, `delete_event()`, `save_approval()`, `get_approvals()`. |
| `agent_model.py` | Protocol for structured live/fallback model calls |
| `model_env.py` | Server-side model provider/env resolution |
| `model_router.py` | Chooses fallback, Gemini, or OpenAI-compatible provider |
| `diagnostics.py` | Non-secret provider diagnostic helpers for latency, previews, and sanitized validation errors |
| `schema_repair.py` | Conservative provider-side structured-output repair before Pydantic validation |
| `../config/model_settings.py` | Local-dev provider settings reader/writer for gitignored `.env` |
| `gemini_model.py` | Lazy live Gemini provider; uses response schemas when SDK support is available |
| `openai_compatible_model.py` | Lazy live OpenAI-compatible provider for OpenRouter/local endpoints; tries JSON Schema response format before JSON object fallback where supported |
| `fallback_model.py` | Honest deterministic fallback provider |
| `rate_card.py` | Vendor rate lookup and caching (FX rates) |
| `vendor_sourcer.py` | Vendor discovery and qualification |

#### `event_producer/storage/`
Local file-backed casefile persistence (Firestore-ready provider seam; demo storage, not cloud).

| File | Purpose |
|---|---|
| `local_casefiles.py` | Saved casefile store: state resolution/precedence, artifacts, timeline, requirements payloads, next-best-step. `create_casefile` accepts an optional stable `event_id` for reproducible seeds |
| `vendor_notebook.py` | Vendor Notebook over the casefile store: persistent per-vendor records with workflow/payment status, append-only logs (vendor replies injection-screened on entry), one current draft each, and selected-vendor-only prompt context |

#### `event_producer/seeds/`
Committed demo casefiles so a fresh clone has reference events (`.local_state/` is gitignored). `ensure_demo_casefiles` idempotently creates and runs two seeds — an LA product launch (USD) and a Singapore founder networking night (SGD) — surfaced by `POST /casefiles/seed`, the app's **Seed Demo** button, and `scripts/seed_demo.py`.

#### `event_producer/mcp/`
MCP (Model Context Protocol) server implementation. Exposes EventStore operations through a uniform MCP-style interface. All CRUD goes through the `EventStore` provider ABC -- no private introspection.

| File | Purpose |
|---|---|
| `server.py` | MCP server with honest CRUD/list/delete via provider seam. Includes `McpHttpHandler` for HTTP access. |

---

### `web/` -- Next.js Frontend

Browser-based UI for the event producer system. Static export (`output: 'export'`) served by Firebase Hosting.

| Path | Purpose |
|---|---|
| `web/package.json` | Node dependencies and scripts |
| `web/next.config.js` | Next.js config (static export) |
| `web/pages/` | Next.js page components (file-system routing) |
| `web/pages/index.tsx` | Main Paper War Room page with persistent side nav, route-like section state, runtime summary strip, Settings provider test, strict-live error display, and AI Producer proposal controls |
| `web/pages/api/[...proxy].ts` | Dev-only API proxy (not included in static export) |
| `web/components/` | Shared UI components (AgentCrewTrace, AgentMissionControl, ApprovalInbox, BudgetCard, ChatPane, ConflictReportCard, EventCommandHeader, ExtractedRequirements, InfoHint, IntakeHero, NextBestStep, RequirementsConfirmation, RiskCard, RunOfShowCard, ScopeCard, VendorNotebook). The UI exposes direct specialist-agent actions, live/fallback agent modes, deterministic engine outputs, the per-vendor notebook, and Approval Wall status inside Overview, Brief Intake, AI Crew, Scope, Budget, Run Sheet, Approvals, Vendors, Risks, and Audit Log sections. |
| `web/lib/api.ts` | Browser API helper for API base resolution, demo header injection, structured backend error parsing, and strict-live provider failure details |
| `web/lib/humanize.ts` | User-facing display-label helpers for enum/action/category/provenance strings |
| `web/types/agentic.ts` | Shared frontend types for model modes, provenance, proposals, direct specialist-agent actions, Scope Strategy, Vendor Draft, provider diagnostics, and recompute notices |
| `web/styles/globals.css` | Design token system + component classes (single source of truth for styling) |
| `web/public/` | Static assets |
| `web/out/` | Static export output (gitignored) |

---

### `tests/` -- Eval Framework and Test Suite

All test code lives here.

| File | Coverage |
|---|---|
| `test_budget_engine.py` | Deterministic budget engine unit tests (FX rounding, tier gating, contingency, receipt variance) |
| `test_cpm_scheduler.py` | CPM scheduler unit tests (dependencies, lead times, anchors, cycles, conflicts) |
| `test_agents.py` | Agent tests (brief/scope, budget manager, production manager, vendor coordinator, risk flagger) |
| `test_api.py` | REST API tests (run, event state, approvals, HITL flow, error shapes) |
| `test_provider_diagnostics.py` | Provider runtime diagnostics, strict-live failure envelope, and degraded live-provider fallback tests |
| `test_structured_output_hardening.py` | P7H.5 JSON Schema response-format, safe repair, Gemini config, and strict-live invalid-output tests |
| `test_security.py` | Action-gate, injection flag, and audit log tests |
| `test_mcp.py` | MCP server tests (CRUD, list, delete via provider seam) |
| `test_fx_rates.py` | FX rate provider tests |
| `test_p6d_default_demo_contract.py` | Default demo contract tests (non-empty scope, budget, schedule, agent trace, approval, chat log) |
| `test_p6f_security_demo.py` | Scripted security beat tests (3 fixtures, no-execution guarantee, approval transitions) |
| `test_p7b_scope_mutation.py` | P7B scope mutation/proposal source-of-truth tests |
| `test_p7d_constraint_overrides.py` | P7D-FIX constraint provenance, inactive override, 100-pax stress, and budget realism tests |
| `test_p7d_scope_customization.py` | P7D-FIX scope CRUD, proposal apply, and recompute-notice tests |
| `test_live_scope_strategy.py` | P7H Scope Strategy safety and live/fallback contract tests |
| `test_orchestrator_live.py` | P7H live-capable Orchestrator proposal and strict-provider behavior tests |
| `test_vendor_draft_live.py` | P7H Vendor Draft live/fallback and approval-wall safety tests |
| `test_p7l_specialist_agents.py` | P7L direct specialist-agent artifact, timeline, fallback, invalid-agent, and no-silent-basics-mutation tests |
| `test_p7n_run_snapshot.py` | P7N run-snapshot persistence, restart rehydration, snapshot write-back on scope edits, artifact/storage endpoint tests |
| `eval_cases/` | Red-team eval set written in Gherkin (`*.feature` files) |

---

### `project_documents/result-artifacts/p7d-fix/` *(GITIGNORED)*

Internal fix-pass evidence required by the 21B handover brief. Contains task
artifacts, saved planner/generator/evaluator subagent outputs, screenshot
evidence or screenshot blocker, and final verdict.

---

### `scripts/`

| File | Purpose |
|---|---|
| `seed_demo.py` | Seeds a demo networking event via the REST API |

---

### `deploy/` -- Cloud Run and Firebase Configuration

Infrastructure-as-code for deployment targets.

| File | Purpose |
|---|---|
| `Dockerfile` | Container image definition for Cloud Run |
| `cloudbuild.yaml` | Google Cloud Build pipeline config (includes all 4 QA gates: mypy + ruff + pytest + build) |
| `cloudbuild.backend.yaml` | First-pass backend image build for new hosted environments before frontend URLs exist |
| `firebase.json` | Firebase Hosting config (serves `web/out` from static export) |

---

## Moat-Seam Boundary

The `event_producer/providers/` directory defines the **moat-seam boundary** -- the architectural line that separates the agent/reasoning layer from all external I/O.

**How it works:**

1. Each provider file contains an **abstract interface** (Python ABC or Protocol class) that defines a contract: method signatures, input/output types, and error semantics.
2. The agent layer (`event_producer/agents/`) imports and depends **only** on these abstract interfaces. Agents never import concrete implementations directly.
3. Concrete implementations (e.g., `InMemoryEventStore`) are injected at the composition root (`event_producer/main.py`).
4. This seam makes it possible to:
   - Swap backends without touching agent code (e.g., replace in-memory store with Firestore).
   - Test agents in-memory with fake providers.
   - Deploy to different environments with different provider configs.

**Rule:** If a module outside `providers/` imports a concrete external SDK (Firestore client, Google Sheets API, HTTP library), the abstraction has leaked. Fix it by pushing the dependency behind a provider interface.

---

## High-Risk Files -- Do Not Edit Casually

These files have outsized blast radius. Changes here can cascade across the entire system. Always review impact and run the full test suite before committing.

| # | File | Why It Is High-Risk |
|---|---|---|
| 1 | `event_producer/main.py` | Composition root. Contains `InMemoryEventStore` and `EventProducerApp`. Changing wiring or initialization order can break every agent and provider binding. |
| 2 | `event_producer/models/schemas.py` | Shared Pydantic schemas. A field rename or type change propagates to every agent, engine, and provider that consumes the model. |
| 3 | `event_producer/providers/event_store.py` | Moat-seam interface. Changing a method signature requires updating every concrete implementation and every agent that calls it. |
| 4 | `event_producer/security/action_gate.py` | Trust boundary enforcement. A logic error here can either block legitimate actions or allow unauthorized ones. |
| 5 | `event_producer/engines/budget.py` | Deterministic financial core. Silent rounding or allocation errors compound across an entire event budget. |
| 6 | `event_producer/engines/scheduler.py` | Deterministic scheduling core. Dependency/lead-time/anchor validation changes affect all schedule outputs. |
| 7 | `event_producer/api.py` | REST API surface. Error shape or endpoint contract changes affect frontend and all API consumers. |
| 8 | `deploy/Dockerfile` | Production container definition. A broken layer or missing dependency takes down the entire deployed service. |
| 9 | `deploy/cloudbuild.yaml` | CI/CD pipeline. A broken gate or missing QA step can deploy broken code. |
| 10 | `.gitignore` | Secrets-first policy. Accidentally un-ignoring a pattern can expose credentials or large binaries to version control. |

---

*Last updated: 2026-07-03 (P7H.5 structured-output hardening pass)*
