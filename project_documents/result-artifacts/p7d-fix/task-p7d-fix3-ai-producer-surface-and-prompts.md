# P7D-FIX Task 3 — AI Producer Surface and Prompts

## What Changed

- Kept AI Production Crew as a promoted top-level post-run panel.
- Expanded crew cards with role, mode badge, job label, input summary, output summary, and warning/action details.
- Moved Ask the AI Producer into a top post-run card directly under the crew panel.
- Added required prompt chips:
  - Flag unrealistic assumptions
  - Suggest cuts to stay under budget
  - Rebalance scope under budget
  - Make this feel more premium
  - Add low-cost networking mechanics
  - Suggest vendor/service additions
  - Make this more brand/photo-ready
- Prompt chips call `POST /event/{id}/chat`.
- Proposal cards show title, rationale, tier/type, budget impact when available, Apply, and Dismiss.
- Technical Agent Trace remains secondary in a collapsed details panel.

## Verification

- Frontend build passed.
- Runtime screenshot capture was blocked by sandbox port-binding restrictions; manual screenshot steps are saved in `screenshots/MANUAL_SCREENSHOT_REQUIRED.md`.
