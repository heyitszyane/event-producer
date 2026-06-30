# Manual Screenshot Required

Actual PNG screenshots could not be captured in this Codex environment.

## Why Capture Failed

- Backend command attempted:
  `ALLOWED_ORIGINS=... .venv/bin/python -m uvicorn event_producer.main:create_app --factory --host 127.0.0.1 --port 8080`
- Frontend command attempted:
  `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8080 pnpm -C web exec next dev -p 3002`
- Both commands were blocked by sandbox port-binding restrictions.
- Escalation to start the backend server was rejected by the environment with a usage-limit approval failure, so runtime browser smoke and screenshot capture could not proceed.

## Manual Runtime Commands

Backend:

```bash
cd /Users/finder/claude-code/event-producer
source .venv/bin/activate
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:3001,http://localhost:3002,http://127.0.0.1:3000,http://127.0.0.1:3001,http://127.0.0.1:3002 \
python -m uvicorn event_producer.main:create_app \
  --factory \
  --host 127.0.0.1 \
  --port 8080
```

Frontend:

```bash
cd /Users/finder/claude-code/event-producer
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8080 pnpm -C web exec next dev -p 3002
```

Open:

```text
http://localhost:3002
```

## Stress-Test Brief

```text
1 night AI industry networking event with $10000 budget.
Event will be held in an indoor bar or restaurant in Singapore,
on 10 July 2026 between 6pm to 10pm.
Open bar with canapes.
Expected turnout 100 pax.
Need basic AV system and banners.
If budget permits, include some free merch such as branded t-shirts, caps and notebooks.
```

## Manual Browser Steps

1. Load `http://localhost:3002`.
2. Paste the stress-test brief into the messy brief field only.
3. Leave manual Budget Cap, Contingency %, Attendees, Event Type, Venue Type, and Date inactive/blank.
4. Run the event.
5. Confirm the header says `100 attendees`.
6. Confirm manual Attendees is inactive/blank, not `50`.
7. Confirm Extracted Requirements shows attendee basis `100` with `from brief`.
8. Confirm Budget shows a prominent budget realism warning and not a clean green-only state.
9. Confirm AI Production Crew cards appear near the top.
10. Confirm Ask the AI Producer prompt chips appear near the top.
11. Click `Suggest cuts to stay under budget` or `Make this feel more premium`.
12. Confirm a proposal appears with Apply and Dismiss.
13. Apply one proposal and confirm the recompute notice appears.
14. Open `+ Add rental / service / vendor`, fill a scope item, add it, and confirm budget recompute feedback.
15. Confirm Approval/Security wall remains visible and honest.
16. Repeat at a narrow/mobile viewport.

## Required Screenshot Filenames

- `p7d-fix-01-post-run-100-pax-header-and-crew.png`
- `p7d-fix-02-requirement-provenance-no-manual-override.png`
- `p7d-fix-03-budget-realism-warning.png`
- `p7d-fix-04-ask-ai-producer-prompt-chips.png`
- `p7d-fix-05-proposal-returned-apply-dismiss.png`
- `p7d-fix-06-after-apply-budget-recomputed.png`
- `p7d-fix-07-add-scope-item-form.png`
- `p7d-fix-08-approval-security-wall.png`
- `p7d-fix-09-mobile-narrow-viewport.png`

## P8 Status

P7D-FIX implementation cannot be considered P8-green until actual PNG screenshots are captured and reviewed.
