# P7D-FIX Final Verdict

## Final Status

partial

## Branch / Commits

- implementation branch: `fix/p7d-constraint-provenance-and-demo-surface`
- implementation commit: not created; `.git` write/escalation became blocked by environment usage-limit rejection
- merge commit, if merged: not merged
- origin/main commit after push: not pushed; baseline public `origin/main` was `e914760b444fc5448c80b685ba4c438315248038`

## What Was Fixed

- constraint provenance: added explicit manual constraint flags and `constraint_resolution`; inactive defaults/placeholders no longer override brief extraction
- header/event spec/budget basis alignment: stress brief resolves to 100 attendees, event spec uses 100, and budget lines use attendee-scaled quantity 100
- budget realism warning: Singapore 100-pax open-bar/canapes budget risk is flagged, and full requested scope is over budget
- AI Production Crew surface: top-level crew cards show mode, input, output, and warning/action summaries
- Ask AI Producer prompt chips: promoted near the crew panel and wired to `POST /event/{id}/chat`
- scope customization/recompute: add/edit/delete/toggle/retier controls update full scope/budget/schedule state and display recompute notices
- docs/public claims: README, CHANGELOG, and REPO_SITEMAP updated locally for P7D-FIX / 21B and 225 tests
- screenshots: blocker file created because server/browser capture was blocked

## Stress-Test Result

Brief:

```text
1 night AI industry networking event with $10000 budget.
Event will be held in an indoor bar or restaurant in Singapore,
on 10 July 2026 between 6pm to 10pm.
Open bar with canapes.
Expected turnout 100 pax.
Need basic AV system and banners.
If budget permits, include some free merch such as branded t-shirts, caps and notebooks.
```

Expected attendee basis: 100
Actual attendee basis: 100
Header attendee display: expected to show 100 via `event_spec.attendees`; browser screenshot not captured
Manual override active? no for the smoke run
Budget realism warning visible? API result yes; browser screenshot not captured
Prompt chips visible? frontend build contains promoted surface; browser screenshot not captured
Proposal apply tested? yes by API tests
Scope add tested? yes by API tests
Approval wall visible? frontend build contains existing Approval/Security components; browser screenshot not captured

## QA Results

- pytest: pass, `225 passed, 1 warning`
- ruff: pass
- mypy: pass
- frontend install: pass
- frontend lint: blocked; `next lint` prompts for first-run ESLint setup because ESLint/config is absent, and dependency install approval was rejected by the environment usage limit
- frontend build: pass, with non-fatal Google font download and static-export warnings
- git diff --check: pass
- API-level runtime smoke: pass for stress brief
- browser/server runtime smoke: blocked by sandbox port-binding restrictions and usage-limit rejection on escalation

## Screenshot Evidence

Actual PNG screenshots are missing.

Blocker file:

```text
project_documents/result-artifacts/p7d-fix/screenshots/MANUAL_SCREENSHOT_REQUIRED.md
```

## Public Repo Verification

- origin/main baseline: `e914760b444fc5448c80b685ba4c438315248038`
- README current locally? yes
- CHANGELOG current locally? yes
- REPO_SITEMAP current locally? yes
- Public `main` current? no; merge/push blocked in this session

## P8 Recommendation

not greenlit for P8 until screenshots are captured and reviewed, lint setup is completed, and the fix branch is committed/merged/pushed to public `main`

## Remaining Risks

- Browser screenshots were not captured, so visual acceptance is not proven.
- `pnpm -C web run lint` remains non-interactive-blocked until ESLint dependencies/config are added.
- Git commit/merge/push still needs to be completed when `.git` write and network approvals are available.
