# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### P7D-FIX / 21B — Constraint provenance + demo-surface acceptance

Repairs the P7D acceptance blocker where extracted brief truth could disagree
with event header/manual defaults.

- Fixed messy-brief/manual-override contradiction: inactive/default manual
  values no longer override extracted requirements, and `constraint_resolution`
  exposes brief/manual/resolved provenance.
- Stress-test brief now resolves to `100` attendees end-to-end, parses
  `10 July 2026`, and prices attendee-scaled scope at quantity `100`.
- Added/strengthened the Singapore 100-pax open-bar/canapes budget realism
  warning; budget UI no longer presents a clean green state for this case.
- Promoted AI Production Crew cards and moved Ask the AI Producer prompt chips
  plus proposal Apply/Dismiss into a top post-run surface.
- Improved scope customization with add/edit/delete/toggle/retier controls and
  visible recompute notices showing headroom before/after and schedule status.
- Updated README and repo sitemap to reflect P7D-FIX behavior and 225-test QA
  count.

### P7D — Interactive agentic demo surface

Makes Event Producer visibly behave like an interactive AI co-producer, not a static dashboard with AI labels.

#### Constraint override semantics fix
- `attendees` and `contingencyPct` fields are now blank by default (not pre-filled)
- Brief extraction is primary; manual constraints require explicit user input
- Source map tracks where each value came from for honest display

#### Requirement provenance display
- Added `BriefIntakeSourceMap` schema with `RequirementSource` enum
- Fields show "Manual override" or "Fallback default" badges when applicable
- `ExtractedRequirements.tsx` displays source badges on field values

#### AI Production Crew above the fold
- Created `AIProductionCrew.tsx` component with visible agent cards
- Shows mode badges: Gemini live, rule-based fallback, deterministic engine, approval-gated, scripted fixture
- Prompt chips added for quick orchestrator interaction

#### Orchestrator prompt chips
- Added quick-action chips: "Make this feel more premium", "Suggest cuts to stay under budget", etc.
- Chips route through `/event/{id}/chat` endpoint
- Proposals render with Apply/Dismiss controls

#### Manual scope customization
- Added "+ Add" button to `ScopeCard.tsx`
- Inline form allows name, category, cost, tier entry
- Budget recalculates after mutation

#### Budget realism warnings (fallback)
- Added heuristic for Singapore open-bar contradiction warning
- Triggers when: Singapore location + 80+ attendees + open bar + budget <= 10000 SGD
- Warning suggests drink coupons or increased budget

#### Visual hierarchy rebalancing
- AI Production Crew promoted to above-the-fold primary view
- Agent trace moved to collapsed `<details>` panel
- Orchestrator chat renamed to "Ask the AI Producer"

### P7B — Editable scope + orchestrator proposals

Extends P7A with editable scope items and orchestrator chat for AI-driven
proposals. All proposals require explicit human apply before state mutation.

#### Scope mutation endpoints
- `POST /event/{id}/scope-items` — add a new scope item
- `PATCH /event/{id}/scope-items/{idx}` — update an existing scope item
- `DELETE /event/{id}/scope-items/{idx}` — delete a scope item
- `POST /event/{id}/scope-items/{idx}/toggle` — toggle selected flag
- `POST /event/{id}/scope-items/{idx}/retier` — change tier

#### Orchestrator chat
- `POST /event/{id}/chat` — returns proposed actions without mutating state
- `POST /event/{id}/proposals/{id}/apply` — applies a pending proposal
- `POST /event/{id}/proposals/{id}/dismiss` — dismisses without mutation

#### Contingency preservation fix
- `BudgetSummary` now includes `contingency_pct` to preserve the original
  percentage across scope mutations. Post-mutation recompute uses the stored
  percentage instead of a hardcoded fallback.

#### Docs
- Updated README with P7B features and test count (211 tests).

## [0.7.0] - 2026-06-22

### P7A — Agentic intake + live Gemini provider seam + model-mode telemetry

Moves Event Producer from a form-first deterministic dashboard to a real,
cloneable AI co-producer surface, while preserving the deterministic core and
the structural approval-gate.

#### AI intake pipeline (read-only / extractive in front of the engines)
- `Brief Intake Agent` interprets a messy brief: requirements, assumptions,
  missing questions, contradictions, market-realism warnings, confidence. Does
  **not** invent money-critical or schedule-critical values silently.
- `Creative Concept Agent` proposes an event direction + ideas + suggested
  additions/cuts as **advisory only** — proposals do not mutate scope/budget/
  schedule in P7A (now P7B applies them).
- Cooperation model: `user constraint > model extraction > safe fallback`,
  gaps surfaced in `brief_intake.missing_questions`.

#### Server-side Gemini provider seam
- New `event_producer/providers/` seam: `model_env`, `agent_model` (protocol),
  `gemini_model` (lazy, server-side, key-gated), `fallback_model` (honest,
  never claims to be Gemini), `router`.
- `google-genai==2.10.0` added, imported lazily, read only server-side.
- Honest mode reporting: the agent trace per-step `model_mode` / `fallback_reason`
  + `model_mode_summary`; the UI shows live vs fallback vs deterministic vs
  approval-gated badges.

#### Frontend reframe
- Messy-brief `IntakeHero` as the primary surface; structured fields relabeled
  "Constraints / manual overrides" (optional).
- New `ExtractedRequirements` + `CreativeConcept` read-only panels; `AgentCrewTrace`
  now renders model-mode badges. "Add to scope" control wired via P7B endpoints.

### P6C–P6F Rescue Sequence + P6G Docs/Submission Hardening

**Scope:** Rescue audit, default demo contract, mission-control UI, scripted security beat, docs honesty.

#### P6C — Audit + demo contract
- Audited all 20 original capstone requirements against repo evidence
- Defined the default demo contract (non-empty scope, budget, schedule, agent trace, approval, chat log)
- Identified and resolved root cause: `"corporate"` event type missing from scope catalogue

#### P6D — Backend demo payload
- Added `AgentTraceStep` and `ChatLogMessage` Pydantic schemas
- Added `"corporate"` entry to scope catalogue
- Generated 5-step `agent_trace` and 6-message `chat_log` in default run
- Wired real pending `Approval` creation into vendor step
- Updated 27 contract tests

#### P6E — Mission-control UI rescue
- Added `AgentCrewTrace`, `SecurityBeat`, rewritten `ApprovalInbox`, rewritten `ChatPane`
- Added 7 field-level validation rules, error parsing, backend-unreachable messaging
- Two-column responsive grid, hero strip, collapsible panels

#### P6F — Scripted security beat + evaluation hardening
- 3 deterministic security fixtures (crude, subtle, image-channel) with `external_action_executed: false`
- 31 new security demo tests
- `SecurityBeat.tsx` component rendering fixtures, gate info, blocked actions

#### P6G — Docs + submission hardening
- Public claims matrix (25 claims classified into implemented/scripted/seam/deferred)
- README rewritten: honest phase label, 177 tests, pnpm commands, security model, mission-control walkthrough
- CHANGELOG, REPO_SITEMAP, CLAUDE.md updated
- Local submission package created under `project_documents/result-artifacts/p6g/submission-package/`
- Honesty boundaries preserved: no live Gemini/Firestore/Telegram/OCR/auth claimed

#### QA
- Tests: 177 passed (was 119 before rescue)
- ruff: all checks passed
- mypy: no issues in 25 source files
- Frontend build: success
- Deploy config (cloudbuild.yaml, firebase.json): valid

---

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
