# P7I.1 Frontend Clarity Polish Results

Date: 2026-07-03
Branch: `polish/p7i1-frontend-clarity-declutter`
Base: `7d219081da9913bcca95cc29b8f2101ac484322e`

## Summary

Implemented the narrow frontend declutter pass from the P7I.1 brief without changing backend provider behavior, deterministic budget/schedule engines, approval-gate semantics, Settings diagnostics, or live/fallback model behavior.

## Changes Made

- Replaced the large event title logic with a safer display-title helper that prefers creative title options, sanitizes backend event names, falls back to the brief first sentence, and caps long titles.
- Added compact event metadata under the title when known: location, pax, budget, event type, and date.
- Removed the internal local-title/backend caveat from the main header.
- Removed the large runtime summary grid and replaced it with one compact runtime proof strip.
- Moved compact casefile status, runtime mode, and last-run time into the sidebar above Route Map.
- Removed the duplicate `AI Source` metric and adjusted the metrics grid to five columns.
- Removed the duplicate status stamp from the Overview casefile header.
- Decluttered `AIProductionCrew` by removing header runtime badges, removing `Runtime:` prefixes, showing one compact mode pill per card, limiting task summaries, and moving model/prompt metadata into per-card technical details.
- Replaced the AI Producer prompt chip row with a sample-prompt dropdown plus one `Run sample` action button.

## QA

Passed:

- `CI=1 pnpm -C web exec tsc --noEmit --pretty false`
- `CI=1 pnpm -C web run lint`
- `CI=1 NEXT_PUBLIC_API_BASE_URL=http://example.invalid pnpm -C web run build`
- `bash -n scripts/dev.sh`
- `git diff --check`

Notes:

- The first typecheck attempt had to reinstall `web/node_modules`; the sandbox could not resolve npm, so the same command was rerun with network permission and then rerun cleanly.
- Lint/build retained the existing Next font warning in `web/pages/_app.tsx`.
- Build retained a Google Fonts optimization warning because the stylesheet could not be downloaded, but compilation completed successfully.

## Manual Smoke Verification

Local smoke used:

- Backend: `.venv/bin/uvicorn event_producer.api:create_app --factory --host 127.0.0.1 --port 8081`
- Frontend: `CI=1 NEXT_PUBLIC_API_BASE_URL=http://localhost:8081 pnpm -C web exec next dev --hostname 127.0.0.1 --port 3001`

Verified:

- Demo run completed through `/run`.
- Header title after demo run was concise: `Networking Night`.
- Header metadata rendered compactly: `Singapore - 100 pax - SGD 10k - Networking Event - 2026-08-17`.
- No `Local title draft - does not mutate backend event identity` text appeared.
- No primary Provider/Model runtime grid appeared.
- Top metrics were exactly Budget Headroom, Production Status, Tasks, Approvals, Brief Basis.
- Overview did not show the duplicate status stamp.
- Sidebar showed compact status/runtime/last-run information above Route Map.
- AI Crew header had no runtime badge row.
- AI Crew cards showed compact mode pills: Fallback, Engine, Fixture.
- AI Crew primary view had no `Runtime:` prefixes; model/prompt metadata stayed in technical details.
- AI Producer used a dropdown instead of prompt chips.
- Selecting `Flag unrealistic assumptions` enabled `Run sample` and returned a producer reply without error.
- Audit still showed technical trace mode badges.
- Settings still showed Provider Settings and Current Backend Runtime diagnostics.
- Narrow viewport sanity check at 390px had no horizontal overflow.

No backend files were changed, so backend pytest/ruff/mypy were not required by the brief.
