# Planner Subagent — Loop 1 Round 1 Plan

## Primary Root Causes

- `web/pages/index.tsx` still initializes `eventType='corporate'` and `venueType='indoor'`, then submits them, so defaults can behave like manual overrides.
- Provenance currently labels source, but does not clearly separate “brief extracted value” from “resolved value used by engines.”
- Scope mutation endpoints recompute budget/schedule, but `ScopeCard` only passes updated `scope_items` upward, so the frontend can drop returned budget/schedule changes.
- Budget realism warnings exist in intake, but Budget/header UI can still show plain green `ON TRACK`.

## Focused Plan

1. Backend provenance and resolved constraints
   - Touch likely files: `event_producer/main.py`, `event_producer/models/schemas.py`, `tests/test_p7d_constraint_overrides.py`.
   - Add/return a small `constraint_resolution` response object showing, per field: `brief_value`, `manual_value`, `resolved_value`, `source`.
   - Keep `brief_intake` as extracted truth; use `event_spec`/`constraint_resolution` for engine-used truth.
   - Ensure stress brief resolves attendees to `100` everywhere with no manual override.
   - Ensure explicit `attendees=50` shows `brief_value=100`, `resolved_value=50`, `source=manual_override`.

2. Budget realism and scope pricing
   - Touch likely files: `event_producer/agents/brief_intake.py`, `event_producer/agents/brief_scope.py`, `event_producer/main.py`, `web/components/BudgetCard.tsx`, maybe `web/pages/index.tsx`.
   - Preserve the Singapore/open-bar/canapes warning and surface it prominently near hero/budget.
   - Make open bar/canapes influence scope either by adding/upgrading selected catering/bar scope for the stress brief, or by explicitly tagging the generated plan as a fallback down-scope.
   - Keep deterministic budget invariants unchanged.

3. Frontend manual override behavior
   - Touch likely files: `web/pages/index.tsx`, `web/components/EventCommandHeader.tsx`, `web/components/ExtractedRequirements.tsx`, `web/types/agentic.ts`.
   - Default manual fields to blank/inactive, including event type and venue type.
   - Add placeholder options like `From brief` for selects.
   - Only submit manual fields when explicitly supplied/activated.
   - Display provenance badges for `from brief`, `manual override`, `fallback default`, and `missing / needs follow-up`.

4. Frontend demo surface
   - Touch likely files: `web/pages/index.tsx`, `web/components/AIProductionCrew.tsx`, `web/components/CreativeConcept.tsx`.
   - Keep AI Production Crew above the main grid.
   - Move/render “Ask the AI Producer” directly beside or under crew/creative concept, not below vendors/security/risks.
   - Show crew cards with role, mode, job, input summary, output summary, and warnings/actions.

5. Scope recompute and mutation feedback
   - Touch likely files: `web/components/ScopeCard.tsx`, `web/pages/index.tsx`, `event_producer/api.py`, `tests/test_p7d_scope_customization.py`, maybe `tests/test_api.py`.
   - Change `ScopeCard` callback to pass full recompute payload, not only `scope_items`.
   - Add edit support for name/category/tier/qty/unit cost/selected.
   - After add/edit/delete/toggle/retier/proposal apply, show status text: `Budget recalculated. Headroom changed from X to Y. Schedule recomputed.`
   - Include Apply/Dismiss for orchestrator proposals.

6. Tests
   - Add backend tests for the stress brief:
     - extracted attendees `100`
     - event_spec attendees `100`
     - budget/scope based on `100`
     - no fallback `50` unless no attendee data exists
     - manual override `50` is explicit and visibly sourced
     - realism warning exists
   - Add API tests for scope mutation recompute payload: scope, budget, schedule/call sheet.
   - Add frontend build/lint coverage as available through `pnpm`.

7. Docs
   - Touch likely files: `README.md`, `CHANGELOG.md`, `docs/REPO_SITEMAP.md`, `.env.example` only to verify secret-free if needed.
   - Remove/soften any already-claimed P7D fix until actual QA/screenshots prove it.
   - Update test count only after final QA.
   - Ensure no public doc claims unimplemented live ADK/Firestore/Telegram behavior.

8. QA and evidence artifacts
   - Save planner/generator/evaluator outputs under `project_documents/result-artifacts/p7d-fix/subagents/...`.
   - Save result summary under `project_documents/result-artifacts/p7d-fix/`.
   - Save actual PNGs under `project_documents/result-artifacts/p7d-fix/screenshots/`.
   - Required final commands: `pytest`, `mypy`, `ruff`, `pnpm lint`, `pnpm build`, runtime smoke, screenshot capture.

## Risks

- Date extraction currently only handles `YYYY-MM-DD`; stress brief says `10 July 2026`, so date may still fall back unless fixed.
- Adding open-bar pricing must not break budget zero-sum or tier-gating invariants.
- UI provenance can become confusing if “extracted value” and “resolved value” are not visually separated.
- Screenshot acceptance depends on actual viewport layout, not just component presence.
