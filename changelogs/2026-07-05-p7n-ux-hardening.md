# 2026-07-05 — P7N: UX hardening — run persistence, real recompute feedback, declutter

## Why

Post-P7M UX review (marked screenshots, 2026-07-04) surfaced three classes of
problems 1.5 days before capstone submission:

1. **Features that looked broken.** Nothing survived a page reload: loading a
   saved casefile restored only basics/brief, so Scope, Budget, Run Sheet,
   Risks, and Approvals rendered empty until a full re-run. Scope edits also
   only mutated the in-memory event store, so saved artifacts went stale and a
   backend restart 404'd every scope mutation.
2. **Theatre.** The Scope "Recompute" button set a success message without
   calling the backend. Excluding an item in an engine-excluded tier left
   headroom unchanged with no explanation, which read as "not calculating".
3. **Clutter.** Duplicate status banners (Scope recompute x2, Run Sheet
   "Schedule Valid" + drafts notice, sidebar status card + proof footer,
   Settings save + runtime callouts), a requirements table duplicating the
   Event Basics form, stacked casefile chips that do not scale, and
   all-black budget bars.

## What changed

### Backend (`event_producer/`)

- `main.py`
  - `_persist_casefile_artifacts` now also writes a `run-snapshot` artifact
    (the full sanitized run result).
  - New `get_run_snapshot`, `ensure_event_runtime` (rehydrates the in-memory
    event store — event spec, scope, budget, schedule, run-of-show, vendors,
    approvals — from the snapshot via strict JSON-mode validation), and
    `update_run_snapshot` (merges recomputed scope/budget/schedule back into
    the snapshot plus the `budget-summary` / `run-sheet` artifacts).
- `api.py`
  - New endpoints: `GET /casefiles/{id}/run-snapshot` (restores last run and
    rehydrates runtime), `GET /casefiles/{id}/artifacts/{name}` (allowlisted
    artifact payload reads; registered after the vendor-copy routes so those
    keep their draft shape), `GET /settings/storage` (casefile root, count).
  - All scope mutations, orchestrator chat, proposals, approvals, and
    `GET /event/{id}` now call `ensure_event_runtime` first, so they work on
    saved casefiles after a backend restart.
  - `_recompute_event` notice is concise, states explicitly when headroom is
    unchanged because the edit touched an excluded tier, and writes the
    recomputed state back to the casefile snapshot.
  - Local-dev CORS defaults to a localhost-any-port regex when
    `ALLOWED_ORIGINS` is unset; explicit origins are honored when set.

### Frontend (`web/`)

- Casefile nav: stacked chips replaced with a dropdown selector; most recently
  updated casefile auto-resumes on load; sidebar runtime proof footer removed.
- Reload persistence: selecting a casefile fetches the run snapshot and
  restores the full workspace (404 = not run yet).
- Scope: fake Recompute button removed; single feedback banner; per-row budget
  status ("Counted in budget" / "tier excluded by budget engine" / "excluded
  by you") plus a one-line tier-gating explainer.
- Budget: basis bar removed, status moved into the header badge, health bars
  and category bars color-coded, "Selected Scope Spend" relabeled "Included
  Scope Spend".
- Run Sheet: full-width "Schedule Valid" banner and drafts notice merged into
  header badges; conflict warning only when conflicts exist.
- Brief Intake: requirements confirmation reduced to a compact bar (status,
  notices, confirm action); the duplicate field table and edit grid removed —
  Event Basics above is the single editing surface.
- AI Crew: specialist cards hydrate saved artifact payloads (badge, summary,
  preview) via the new artifact endpoint; duplicated summary text removed from
  previews; stale recompute notices cleared on navigation.
- Vendors: two-column layout (vendor copy | vendor directory).
- Overview: "Recent artifacts" reworked into "Saved casefile artifacts" with
  per-artifact route links, local storage root, and copy-casefile-ID.
- Settings: Local Data panel (casefile root, saved count, active casefile ID,
  honest local-storage note); provider save message names the `.env` path and
  states no restart is needed; redundant runtime callout removed.

### Tests

- New `tests/test_p7n_run_snapshot.py` (7 tests): snapshot persistence,
  404-before-first-run, restart rehydration, snapshot write-back on scope
  edit, generic artifact endpoint (allowlist + missing), vendor-copy route
  shape preserved, storage info endpoint.
- `tests/conftest.py`: autouse fixture isolates every test's casefile storage
  from the developer's real `.local_state` (previous runs had leaked ~279
  blank casefiles; those were archived to
  `.local_state/event_producer/events-archived-20260705/`, not deleted).
- `tests/test_provider_diagnostics.py`: degraded-run test now patches every
  reason agent holding a provider reference, so it no longer performs real
  network calls (pre-existing flake on machines with network access).

## Invariants

Budget zero-reconciliation, contingency-first reservation, tier gating,
scheduler dependency/lead-time behavior, the structural action-gate, and HITL
approvals are unchanged. Vendor copy remains draft-only. The recompute path
still runs through the deterministic engines.

## QA

`pytest` 299 passed · `mypy` clean · `ruff` clean · `next lint` clean
(pre-existing font warning only) · `next build` success · full browser smoke
across all 11 routes including reload persistence, scope exclude with headroom
change, specialist run, requirements confirm, and HITL approve.
