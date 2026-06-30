# P7D-FIX Task 2 — Budget and Scope Realism

## What Changed

- Stress-test brief now produces a prominent realism warning for Singapore + 100 pax + open bar/canapes + $10,000.
- Networking scope now exposes attendee-scaled quantities as `qty = attendees` with per-attendee unit costs.
- Added an `Open Bar and Canapes Allowance` must-have scope item for the stress-test pattern.
- Budget card now shows budget basis and realism warnings before the numeric status.
- Header budget state displays `AT RISK` when realism warnings are present instead of a clean green-only state.

## Stress-Test Outcome

- Attendee-scaled budget lines use quantity `100`.
- Open bar/canapes is represented in selected scope.
- Budget summary is over budget for the full requested brief.
- Warning text explains that the full brief is likely above cap.

## Tests

- Updated P7D budget-realism tests to assert warning, over-budget state, warning trace status, and 100-pax budget basis.
