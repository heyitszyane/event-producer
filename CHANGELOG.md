# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### P7N — UX hardening: run persistence, real recompute feedback, declutter

- Persisted a `run-snapshot` casefile artifact after every pipeline run and
  after every scope edit, so the last run (scope, budget, schedule, approvals,
  trace) is restored on page reload and after backend restart.
- Rehydrated the in-memory event runtime from the saved snapshot, keeping scope
  edits, orchestrator chat, proposals, and approvals working against saved
  casefiles across backend restarts.
- Removed the non-functional Scope "Recompute" button (every edit already
  recomputes server-side) and de-duplicated the recompute banners into a single
  clear notice that also explains when headroom is unchanged due to tier gating.
- Added per-row budget status on the Scope ledger ("Counted in budget",
  "tier excluded by budget engine", "excluded by you") plus a tier-gating
  explainer, so exclusions no longer look like silent no-ops.
- Replaced stacked casefile chips in the side nav with a compact dropdown
  selector; the most recently updated casefile is auto-resumed on load.
- Made specialist agent cards hydrate from saved artifacts (mode badge,
  summary, detail preview) instead of only in-session responses, and removed
  duplicated summary text in previews.
- Reworked Overview "Recent artifacts" into "Saved casefile artifacts" with
  route links, the local storage path, and a copy-casefile-ID action.
- Added `GET /casefiles/{id}/run-snapshot`, `GET /casefiles/{id}/artifacts/{name}`,
  and `GET /settings/storage` endpoints; Settings now shows a Local Data panel
  (casefile root, count, active ID) and clearer provider-save messaging.
- Decluttered per-route statuses: Budget basis bar removed and status moved to
  a header badge, budget/category bars color-coded, Run Sheet banners merged
  into header badges, requirements confirmation reduced to a compact bar
  (facts live in Event Basics), and the sidebar runtime proof footer removed.
- Defaulted local-dev CORS to a localhost-any-port regex when `ALLOWED_ORIGINS`
  is unset (explicit origins still honored when set).
- Isolated all tests from the developer's real `.local_state` casefile root via
  an autouse fixture, and fixed a provider-diagnostics test that made real
  network calls.

### P7M — Vendor copy artifact UX

- Added editable vendor-copy artifacts with subject/body, save draft,
  copy-to-clipboard, last-saved timestamp, and refinement prompts.
- Reframed vendor workflow as "review before external use" and removed primary
  UX language implying real outbound sends.
- Persisted edited vendor drafts in the local casefile artifact store with
  timeline events.
- Added tests proving vendor copy saves/reloads and no contact/execution
  semantics are exposed by the save endpoint.

### P7L — Direct specialist-agent workspace/actions

- Added saved-casefile direct actions for Creative Concept, Scope Strategy,
  Vendor Copy, and Risk Review agents.
- Saved each specialist output as a casefile artifact and appended timeline
  events.
- Made AI Production Crew cards actionable entry points rather than proof
  badges.
- Added tests proving direct agent calls use saved casefile context and do not
  mutate critical event basics automatically.

### P7K — Requirements confirmation and next-step guidance

- Added requirements confirmation for saved casefiles, including structured
  missing/conflict notices, confirmation metadata, and edit/save/confirm flow.
- Added Next Best Step guidance derived from saved casefile state and exposed it
  through the casefile API and `/run` response.
- Simplified Overview around current event identity, confirmation state,
  critical facts, budget/schedule health, artifacts, and the next action.
- Added tests for confirmation persistence, next-step transitions, edit-driven
  reconfirmation, conflict retention, and no silent mutation of casefile facts.

### P7J — State truth and local file-backed casefiles

- Added local JSON casefile persistence under `.local_state/event_producer/events/`
  with an index, per-event `casefile.json`, timeline JSONL, and named artifacts.
- Added casefile schemas, resolved state notices, source precedence, and API
  endpoints for creating, listing, loading, and updating saved casefiles.
- Updated `/run` so casefile runs save/load canonical basics first, preserve
  legacy request compatibility, return `casefile` and `resolved_event_state`,
  and persist generated artifacts back into the casefile.
- Updated the frontend around saved Event Basics, a casefile selector, dedicated
  country/city/currency/date/turnout fields, and conflict/missing notices.
- Added regression tests proving 100-pax structured casefile state survives a
  conflicting 50-pax brief, missing turnout remains missing, timeline events
  append, and local state is gitignored.

### P7H.5 — Structured-output hardening for live agentic demo

- Added JSON Schema response format for OpenRouter/OpenAI-compatible live
  calls, with a one-time JSON object retry when the provider rejects schema
  response-format parameters.
- Added Gemini `response_schema` support when the installed `google-genai` SDK
  accepts it, while preserving fallback behavior for older/test installs.
- Added provider-side safe schema repair before Pydantic validation for
  recoverable live-output shape drift, including missing brief text, numeric
  string fields, missing optional lists, and object values in string lists.
- Added non-secret diagnostics for `response_format_mode`, `repaired_schema`,
  and `repaired_fields` on runtime provider tests and strict-live errors.
- Added compact schema examples to live prompts so ordinary OpenRouter/Gemini
  responses are less likely to drift away from the typed contracts.
- Added tests for OpenRouter schema-first payloads, JSON object retry,
  Brief Intake repair, strict-live invalid-output failure, and Gemini
  response-schema fallback behavior.

### P7H.4 — UI runtime visibility and docs honesty

- Added a Settings **Test provider** control that calls
  `POST /runtime/model/test` and renders provider, model, effective mode,
  success/failure, latency, sanitized error, and response preview without
  exposing secrets.
- Added a compact post-run runtime summary showing provider/model, live/fallback
  mode for live-capable agents, deterministic budget/schedule cores, and the
  human Approval Wall; degraded agent fallbacks now surface near the top.
- Updated AI Production Crew and strict-live error UX so model names,
  fallback reasons, provider/model/agent failures, and the Settings diagnostic
  path are visible from the UI.
- Updated public docs to frame live provider mode as the intended capstone demo,
  deterministic fallback as degraded/resilience mode, and budget/scheduler/
  approval components as source-of-truth controls.

### P7H.3 — Live scope strategy and vendor draft surfaces

- Added a live/fallback Scope Strategy Agent with prompt, typed schema,
  trace entry, `model_mode_summary.scope_strategy`, and visible frontend module
  for strategy summary, tradeoffs, recommendations, and fallback reasons.
- Added live/fallback Vendor Draft output with subject/body/approval diff,
  `model_mode_summary.vendor_draft`, vendor-area preview, and pending
  approval notes while preserving the structural Approval Wall.
- Added safety tests proving Scope Strategy does not mutate budget/schedule,
  vendor drafts stay pending and unsent, strict provider failures surface
  clearly, and LLM-supplied payment instructions are scrubbed rather than
  bypassing the action gate.

### P7F — Consolidated external-audit fix pass

Closes the highest-priority post-P7E audit blockers without adding production
auth, Firestore persistence, live Telegram, OCR, or autonomous execution.

- Added event-scoped approval list/update routes:
  `GET /event/{event_id}/approvals` and
  `POST /event/{event_id}/approvals/{approval_id}`. Legacy `/approvals`
  routes remain sample `demo-event` compatibility routes.
- Fixed selected-scope budget semantics: when every interactive scope item is
  explicitly deselected, included budget lines are zero rather than falling
  back to all items.
- Fixed schedule recompute robustness for repeated categories by generating
  unique scope-derived task IDs, and preserved scheduler lead-time behavior by
  making lead time part of CPM scheduling.
- Aligned scripted security blocked-action names with action-gate constants
  (`mark_paid`) and kept user-facing labels separate.
- Extracted demo fallback constraints into a shared defaults module.
- Added a Cloud Build static frontend guard requiring
  `_NEXT_PUBLIC_API_BASE_URL` and checking that local backend URLs are not
  baked into `web/out`.
- Added optional OpenAI-compatible live model provider support for OpenRouter
  and local endpoints while keeping Gemini as the default live provider and
  deterministic fallback as the default runtime.
- Added a non-secret `/runtime/model` API diagnostic so local live-provider
  testing can confirm the loaded provider, mode, model, base URL, and fallback
  reason.
- Adjusted local OpenAI-compatible routing so LM Studio/Ollama/local servers do
  not receive a fake `Bearer local` token; local auth is optional and uses
  `OPENAI_COMPATIBLE_API_KEY` when configured.
- Added a local provider Settings page (`10 Settings`) plus `/settings/model`,
  allowing clone reviewers to choose Gemini, OpenRouter, LM Studio/Ollama/local
  OpenAI-compatible providers, save a gitignored `.env`, and refresh the
  running backend provider from the UI.
- Added `./scripts/dev.sh` as a one-command local launcher for backend and
  frontend dev servers.
- Aligned local backend CORS defaults and `/run` frontend API handling so
  127.0.0.1 development ports use the same shared API base/error path.
- Tightened Paper War Room behavior with event-scoped approval actions, local
  event-title draft labeling, local-only vendor draft row copy, shared API
  error handling, display-label helpers, scope delete confirmation, and
  component-local mutation errors.
- Added accessibility and copy polish for skip-link navigation, live regions,
  icon semantics, display labels, and non-exporting casefile copy.
- Backend QA now reports `241 passed, 1 warning`. Frontend lint now runs
  non-interactively via a checked-in Next ESLint config and pinned lint
  dependencies.

### P7E — Paper War Room frontend redesign

Redesigns the frontend from a single scrolling dashboard into a Paper War Room
mission-control shell. Backend contracts and P7D-FIX messy-brief precedence are
unchanged.

- Added persistent side navigation and route-like sections for Overview, Brief
  Intake, AI Crew, Scope, Budget, Run Sheet, Approvals, Vendors, Risks, and
  Audit Log.
- Added editable frontend-session provenance preview rows in Brief Intake;
  manual edits are visibly marked and do not silently mutate backend canonical
  state.
- Updated AI Crew to show trace-derived task summaries and clear Runtime
  labels instead of bare mode labels.
- Updated Scope with user-facing tier labels, direct item/category inline
  editing, no visible Selected column, and clearer Recompute feedback.
- Added clamped budget health bars with dollar metrics and over-budget labels.
- Added run-sheet draft edit modal with Save/Delete/Cancel while documenting
  that backend schedule recompute remains canonical.
- Refined the Paper War Room UI with an editable generated event name, cleaner
  manual-constraints/provenance copy, user-facing category/dependency labels,
  editable vendor draft rows, and reduced duplicated audit/AI prompt surfaces.
- Preserved the approval/security wall and scripted fixture honesty boundaries;
  no live Telegram, Firestore, auth, or production SaaS claim was added.

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
