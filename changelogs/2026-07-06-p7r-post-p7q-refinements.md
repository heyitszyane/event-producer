# P7R — Post-P7Q screenshot refinements (2026-07-06)

Branch: `feat/p7r-post-p7q-refinements`.

## Why

A second screenshot review of the post-P7Q build (Zyane, 2026-07-06) surfaced
one architectural decision and a batch of UX defects. The headline decision:
the Scope page's **silent tier-gating** ("Not counted — tier excluded by budget
engine") confused users — the Exclude button felt pointless when items were
already not counted, and there was no way to understand or resolve it. The
review also flagged: a redundant "Open Brief Intake" button, ambiguous
create-vs-regenerate casefile controls (users created duplicate casefiles),
an opaque and non-actionable "Tasks / 6 critical" metric, a redundant
"Working title" field, missing committed demo data (`.local_state/` is
gitignored so a fresh clone has nothing to explore), plus vendor-notebook and
audit-log layout polish.

Two forks were confirmed with the reviewer before building: (1) **count every
selected item** (tiers become priority labels + an explicit Auto-fit), and
(2) casefile **Option B** (prominent New Event + rename the generate button +
persist the page title).

## What changed

### Budget model — count-all with explicit fit

- `engines/budget.py::compute_budget` gained `gate_discretionary_tiers: bool =
  True`. The default preserves the engine's greedy tier-gating (and every
  existing engine test). When `False`, every tier is included and `headroom`
  absorbs any overrun (can go negative → `over_budget`). Both zero-sum
  invariants still hold, verified with a negative-headroom test.
- `agents/budget_manager.py` passes the flag through from its request
  (`gate_discretionary_tiers`, default `True` so unit tests and the Gherkin
  spec are unchanged). The two **app** call sites — the initial pipeline run
  (`main.py`) and interactive recompute (`api._recompute_event`) — pass
  `False`, so both the first pass and scope edits count everything.
- New **Auto-fit to budget** action: `POST /event/{id}/scope-items/auto-fit`
  runs the engine in gating mode over all items to decide which whole tiers
  fit, then sets each item's `selected` flag to match (never deletes). This
  keeps the deterministic tier logic as a user-triggered tool.

### Seed casefiles — committed reference data

- New `event_producer/seeds/` package with two `SeedSpec`s: `seed-la-product-
  launch` (USD, clean happy path) and `seed-sg-networking` (SGD, brief vs.
  basics headcount conflict to exercise the provenance/conflict surface).
- `ensure_demo_casefiles(producer)` is idempotent: it skips seeds that already
  exist and runs the deterministic first pass for new ones so they arrive
  populated (scope, budget, schedule, vendor draft).
- Surfaced by `POST /casefiles/seed`, the app's **Seed Demo** button, and
  `scripts/seed_demo.py`. `LocalCasefileStore.create_casefile` accepts an
  optional stable `event_id` for reproducible seed ids.

### Frontend — casefile UX, metrics, scope, vendors, audit

- **Brief header**: removed "Open Brief Intake"; "New Casefile" → primary
  **New Event**; generate button → "Save & regenerate current event". The
  editable page title now persists to `basics.working_title` (was ephemeral),
  and the "Working title" form field was removed with "Event type" moved into
  its slot.
- **Metrics**: Budget Headroom, Schedule Tasks, and Approvals became
  keyboard-accessible links to their routes with "i" hints; "Tasks / N
  critical" → "Schedule Tasks / N on critical path"; Budget Headroom shows the
  contingency reserve inline (e.g. `computed · 12% contingency USD 4,800`).
- **Scope**: removed the "tier excluded" status and the tier-gating warn
  banner (now an "i" hint on the heading); status only shows for user-excluded
  rows; Delete buttons are red (`btn--reject`), Include/Exclude are
  color-coded (`btn--approve` / `btn--warn`); added the Auto-fit button.
- **Vendors**: Add-vendor control moved below the vendor chips; removed the
  redundant "Mark settled" quick button (Workflow selector still offers it);
  the activity log collapses to the latest 4 entries with "show all".
- **Audit Log**: the production log renders as one flat panel
  (`.production-log .chat-box/.chat-messages` borders stripped) instead of
  three nested boxes.

## Tests

- `tests/test_budget_engine.py::test_count_all_without_gating` — gating off
  counts every tier; negative headroom; zero-sum still holds.
- `tests/test_p7r_budget_count_all.py` — selected discretionary items count;
  Exclude improves headroom; Auto-fit drops an unaffordable tier.
- `tests/test_p7r_seed_casefiles.py` — seed creates two casefiles, they come
  populated, and re-seeding is idempotent.

## QA gate

`pytest` 340 passed · `mypy` clean · `ruff` clean · web `lint` clean (known
font warning) · web `build` green. Browser-verified via the verify harness
(ports 8081/3000).
