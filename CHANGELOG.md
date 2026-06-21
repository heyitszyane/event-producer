# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.6.0] - 2026-06-21

### P6 — Frontend Redesign: Mission Control Dashboard

**Scope:** Complete frontend redesign for capstone demo credibility. No backend changes.

#### Layout & Architecture
- Replaced single-column stack with two-column grid layout (60/40) with max-width 1200px
- Added sticky event command header with event identity, nav jump links, and Run button
- Extracted `ConflictReportCard` to standalone component
- Created new `EventCommandHeader` component with collapsible form panel
- Added footer status line

#### Visual System
- Introduced complete CSS custom property design token system (surface, text, accent, status, tier, spacing, typography, radii, shadows)
- Replaced all inline style objects with CSS class references
- Rewrote `globals.css` from scratch with token-driven architecture
- Added numeric formatting: currency (`$50,000.00`), percentages, dates, durations
- Added category rollup bar chart to BudgetCard
- Added tier inclusion pills to BudgetCard
- Added collapsible variance details to BudgetCard
- Improved RunOfShowCard with status banner and critical/anchor path highlighting
- Added approval confirmation flow (prevents accidental approve/reject)
- Added collapsed-by-default panels for Approvals, Risks, Chat
- Added loading pulse animation on Run button

#### Data Fixes
- Fixed vendors data path: reads from `result.run_of_show.vendors` (was `result.vendors`)
- Added `X-Demo-User` header to all `fetch()` calls (fixes 401 in production)
- Added `event_spec` rendering in header (event name, type, date, headcount, venue)
- Added vendor lock status indicators and notes rendering

#### Responsive Design
- Desktop (≥1024px): two-column grid
- Tablet (768–1023px): single column
- Mobile (<768px): full-width, table-to-card conversion via `data-label` attributes
- No horizontal scroll at any breakpoint

#### Accessibility
- Semantic landmarks: `<header>`, `<nav>`, `<main>`, `<section>`, `<footer>`
- Heading hierarchy: h1 (event name) → h2 (card headings)
- `aria-labelledby` on sections, `aria-label` on metrics and buttons
- `aria-live="polite"` on chat messages container
- `:focus-visible` styles with 2px accent outline
- `@media (prefers-reduced-motion: reduce)` disables all animations
- `.sr-only` class for screen-reader-only text

---

## [0.5.1] - 2026-06-21

### P5B — Submission-Readiness Cleanup

**Scope:** Fix public-submission and clean-room reproducibility defects. No new features.

#### Reproducibility
- Added `pytest==9.1.1` to `requirements.txt` so Cloud Build QA gates can install test runner in a clean environment
- Replaced `npm ci` with `pnpm -C web install --frozen-lockfile` in `deploy/cloudbuild.yaml` (repo uses pnpm lockfile, not npm)

#### Documentation Honesty
- README "Concepts Demonstrated" table: replaced "Agent skills | Each role ships as a reusable ADK skill" with honest "Skill-like role agents — reusable role modules with typed inputs/outputs; formal Agents CLI skill packaging is deferred."
- README "Concepts Demonstrated" table: replaced "Model routing | Flash-Lite for formatters, Flash for reasoning" with honest "Model-routing seam — reason/formatter split is represented structurally; live Gemini/Flash routing is deferred."

#### API Consistency
- Auth middleware error response changed from `{"detail": "Missing X-Demo-User header"}` to `{"error": {"code": "401", "message": "Missing X-Demo-User header"}}` to match the standard app-level error envelope

---

## [0.5.0] - 2026-06-21

### P5A -- Audit-Fix Pass: Correctiveness Hardening, MCP Honesty, HITL Wiring, API Stabilization, Frontend/Deploy Coherence, Docs Honesty

**Scope:** Close all 20 P5A-Fxx audit findings. No new features.

#### Correctness (Budget Engine + CPM Scheduler)
- Fixed FX rounding to line-total-first (prevents unit-cost drift with fractional rates)
- Fixed receipt variance to aggregate by label (multiple receipts per label now summed before computing variance)
- Added missing-dependency validation in CPM Scheduler (returns `SchedulerConflictReport` with `conflict_type="missing_dependency"`)
- Added duplicate-task-ID validation in CPM Scheduler (returns conflict with `conflict_type="duplicate_id"`)
- Fixed mutable default values in Pydantic schemas to use `Field(default_factory=...)` (prevents shared-state bugs)
- Fixed risk flagger: deterministic IDs (SHA-256 hash), Decimal arithmetic for money values, vendor category alignment (`av_equipment`)

#### MCP / EventStore Honesty
- Added `list_events()` and `delete_event()` to the `EventStore` ABC
- Implemented both methods in `InMemoryEventStore`
- Removed private `_events` introspection from MCP server (`__dict__` hacks replaced with provider seam calls)
- MCP `delete_event()` now actually removes events
- Added `save_approval()` and `get_approvals()` to `EventStore` ABC and `InMemoryEventStore`

#### Security / HITL Integration
- Replaced sample approval dicts with real `Approval` objects persisted via EventStore
- Restricted `ApprovalAction.action` to `Literal["approve", "reject"]` (invalid actions return 422)
- Wired approval endpoint to action-gate: `enforce()` called before executing gated actions
- Demonstrated unapproved vendor send fails with `PermissionError`
- Full HITL loop: pending -> approved/rejected -> action-gate enforced -> audit logged

#### API Stabilization
- `GET /event/{event_id}` now returns full event state (spec, scope, budget, schedule, vendors, risk flags, approvals)
- Consistent error envelope `{"error": {"code": ..., "message": ...}}` for app routes
- Conflict report included in `/run` response when `schedule_result` is None
- Not-found endpoints return consistent error shape

#### Frontend / Deploy Coherence
- Next.js configured for static export (`output: 'export'` in `next.config.js`)
- Frontend calls backend via `NEXT_PUBLIC_API_BASE_URL` (no hardcoded localhost)
- Conflict report rendered in UI when `schedule_result` is null
- Firebase Hosting serves `web/out/` (static export directory)
- CORS origins driven by `ALLOWED_ORIGINS` environment variable
- Cloud Build config updated with all four QA gates (mypy + ruff + pytest + build)
- Cloud Build deploy steps `waitFor` all QA steps before building/pushing
- Firebase CLI image assumption documented in cloudbuild.yaml

#### Documentation Honesty
- README rewritten to reflect P5A state (not P0 scaffold)
- `requirements.txt` versions pinned
- `CLAUDE.md` stale TODOs removed
- `docs/REPO_SITEMAP.md` updated to match actual repo

---

## [0.4.0] - 2026-06-21

### P4 -- Deployment + Frontend

- FastAPI REST API wrapper (`/run`, `/event/{id}`, `/approvals`, `/healthz`)
- Next.js 14 dashboard frontend with approval inbox, budget card, run-of-show card, vendor card, risk card
- MCP HTTP handler exposed via `McpHttpHandler`
- Firebase Hosting config (`firebase.json`)
- Cloud Run Dockerfile and Cloud Build pipeline (`cloudbuild.yaml`)
- Dev-only API proxy route (`web/pages/api/[...proxy].ts`)

---

## [0.3.0] - 2026-06-21

### P3 -- Agent Crew + Orchestrator Wiring

- Role agents: `brief_scope`, `budget_manager`, `production_manager`, `vendor_coordinator`, `risk_flagger`
- `orchestrator.py` top-level coordinator with reason->formatter splits
- `EventSpec`, `ScopeItem`, `Vendor`, `VendorMessage`, `RiskFlag`, `Approval`, `RunOfShow` Pydantic schemas
- `InMemoryEventStore` with full CRUD for all entity types
- `InMemoryVendorSourcer` with seed vendor data
- `AuditLog` with immutable append-only entries
- `EventProducerApp.run_event()` composition root wiring all agents + engines + security

---

## [0.2.0] - 2026-06-21

### P2 -- CPM Scheduler (Deterministic Core #2)

- `scheduler.py`: Critical Path Method scheduler with forward/backward pass
- Dependency resolution with cycle detection (returns conflict report)
- Lead-time validation (flags tasks arriving after their dependency finishes)
- Anchor-time validation (flags fixed-time tasks that violate dependency constraints)
- `SchedulerConflictReport` with `lead_time_conflicts`, `anchor_conflicts`, `cycle`
- `ScheduleResult` with `ordered_tasks` and `critical_path`
- `ScheduleTask` / `ScheduledTask` / `CallSheetEntry` Pydantic schemas
- Full test suite: cycle detection, anchor conflicts, lead-time conflicts, happy-path scheduling

---

## [0.1.0] - 2026-06-21

### P1 -- Budget Engine (Deterministic Core #1)

- `budget.py`: Pure-Python, Decimal-only budget reconciliation engine
- Zero-sum invariants: `budget_cap - contingency_reserve - spendable == 0` and `spendable - included_totals - headroom == 0`
- Tier-gating: must/should/could/wow greedy allocation
- Multi-currency normalization via `FxRateProvider` interface
- Receipt-vs-plan variance tracking with running burn
- `BudgetLine`, `BudgetSummary`, `BudgetVariance`, `Receipt` Pydantic schemas with strict mode (float rejection)
- `FxRateProvider` / `InMemoryRateCard` provider seam
- Full test suite: tier gating, contingency reservation, FX normalization, receipt variance, input validation

---

## [0.0.1] - 2026-06-21

### Added
- P0 scaffold: repo init, CC-BY-4.0 LICENSE, .gitignore (secrets-first), README skeleton, CLAUDE.md, docs/REPO_SITEMAP.md, CHANGELOG.md
- Three-document documentation system
- Gitignored `project_documents/` and `temp/` directories
- Spec artifacts copied to `project_documents/`
