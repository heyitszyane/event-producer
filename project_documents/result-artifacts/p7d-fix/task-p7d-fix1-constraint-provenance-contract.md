# P7D-FIX Task 1 — Constraint Provenance Contract

## What Changed

- Added `ManualConstraintFlags` so UI/manual clients can distinguish active overrides from placeholder/default values.
- Updated `/run` request handling to pass `manual_constraints` into `EventProducerApp.run_event`.
- Added `constraint_resolution` response data with `brief_value`, `manual_value`, `resolved_value`, and `source` per key.
- Updated frontend defaults so Budget Cap, Contingency %, Attendees, Event Type, Venue Type, and Date are inactive/blank by default.
- Updated Extracted Requirements to show resolved basis and provenance badges: `from brief`, `manual override`, `fallback default`, and `missing / needs follow-up`.
- Added natural-language date parsing for `10 July 2026`.

## Stress-Test Outcome

- Brief-extracted attendees: `100`
- Event spec attendees: `100`
- Inactive manual attendee value `50`: ignored
- Active manual attendee value `50`: applied with `manual_override`
- Date resolves to `2026-07-10`

## Tests

- Updated `tests/test_p7d_constraint_overrides.py`.
- Coverage includes inactive manual 50, active manual 50, no default-50 leakage, source map, and budget basis.
