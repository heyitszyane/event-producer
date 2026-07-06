# P7Q — Post-P7P UI/behavior refinements (2026-07-06)

Branch: `feat/p7q-post-p7p-refinements`.

## Why

A screenshot review of the post-P7P build (Zyane, 2026-07-06) surfaced a
batch of correctness and polish defects that made the product feel like a
static demo rather than a working casefile — and left it not
video/submission ready. The headline defect was a **currency-truth bug**:
selecting SGD on intake still rendered USD everywhere downstream. The
run-of-show timing was also nonsensical (tasks days before the event, 1am
windows), scope quantities were naive (every line = pax count), and several
panels were theatre (fake edit affordances, always-zero variance, scripted
"Security Posture", legacy vendor draft).

## What changed

### Backend — correctness

- **Currency truth.** The casefile currency now threads through the whole
  pipeline: `run_event(currency=...)` → scope catalogue items carry the
  casefile currency (not a hardcoded `USD`), budget `reporting_currency`
  follows it, and `api._recompute_event` resolves the reporting currency
  from the saved casefile. New scope items added via the UI / creative
  suggestions / orchestrator proposals inherit the casefile currency too.
  Agent prose (orchestrator reply + proposal rationales) now quotes money in
  the casefile currency; the intake realism warning is stated
  currency-neutral (intake reads raw text and cannot know the reporting
  currency).
- **Intelligent scope quantities.** Each catalogue line has a `qty_basis`
  (`per_attendee` | `flat` | `per_25_attendees` | `per_50_attendees`).
  Venue/AV/decor/signage become a single lump-sum line sized to headcount
  (qty 1); catering stays per-attendee; staff/security scale in whole units.
  **Event Staffing** is now `could`-tier and **unselected by default** (venues
  usually include it), with a note saying so.
- **Day-of run-of-show.** `ProductionManagerReasonAgent` now builds a fixed
  6-step day-of template (Setup & Load-In → AV & Tech Check → Registration →
  Doors Open → Program → Strike) anchored to the **event date** with naive
  local wall-clock times (doors open 09:00). Scope lead times are no longer
  scheduled as day-of rows; they become a **vendor booking-deadlines** list
  (book-by dates counted back from the event date; venue is the earliest at a
  21-day lead). Combined "Setup" replaces the per-item setup rows.
- **Demo-jargon scrub.** Removed internal `P7A` / "messy brief" / full-brief
  dumps from the production log; the pipeline vendor draft + approval + trace
  no longer name the fixture vendor "Grand Ballroom Co." (neutral
  category-level venue inquiry). Fixture vendors are still stored so the
  Vendor Notebook can offer them as import suggestions.

### Frontend — UX

- **Loader:** centered spinner in the content area (was a left-aligned box on
  a stretched surface).
- **Overview:** removed the redundant Budget/Schedule Health panel (dup of the
  metric row), the local storage-path line, and the duplicate conflict block;
  Budget Headroom metric shows the casefile currency.
- **AI Crew:** the producer console is now a logged chat transcript (question +
  answer per turn, above the input) instead of a single replaced reply;
  "Add to scope" shows real **Added** feedback, sanitizes the cost, and uses
  the casefile currency; "Suggested cuts" relabeled **Avoid / reconsider**.
- **Scope:** per-row edit is a focused modal (was a full-width inline form that
  blew up the table); recompute status banner removed; add-form and edit-form
  cost fields are currency-labeled.
- **Budget:** the Tier Inclusion pills became an informative table
  (tier · item count · tier total · included/excluded reason); the
  always-zero Variance Details block was removed; all money is in the casefile
  currency.
- **Run Sheet:** renders the vendor booking-deadlines table and gains an
  **Add row** button (draft rows via the existing edit modal).
- **Approvals:** added a plain-English explanation of the human gate and a
  clearer empty state; removed the scripted **Security Posture** panel. The
  pending vendor approval now renders the **exact gated draft** (subject + body)
  read-only, so the human reviews the real copy before approving (restores the
  review surface lost when the legacy vendor-copy panel was deleted).
- **Vendors:** vendor chips became **cards** showing contact, quoted amount,
  and due date with a pencil that opens a **profile/payment modal** (was a
  space-hungry inline `<details>` and redundant "venue"/"draft ready" tags);
  draft body is now ≥10 rows; removed the legacy casefile-level draft section
  and the "Draft prepared" status callout.
- **Audit:** "Extraction Provenance Preview" became a **read-only Requirement
  Provenance** table (removed fake add/remove/inline-edit affordances and the
  session-draft banner); removed the scripted Security Posture panel.
- Deleted the now-unused `SecurityBeat.tsx` and `VendorCopyPanel.tsx`.

## Invariants preserved

Deterministic budget/schedule cores, the structural action-gate + HITL, the
data-not-instruction boundary (vendor replies still injection-screened, flagged
text still withheld from prompts), and the provider seam are all unchanged. The
scripted injection **defense** remains real and visible in the Vendor Notebook;
only the redundant scripted *display* panel was removed.

## QA gate

`pytest` 334 passed · `mypy` clean · `ruff` clean · web lint clean
(pre-existing font warning) · web build green. Verified live in-browser against
the running backend across every changed route (SGD casefile): scope/budget/
run-sheet/vendors/approvals/audit all render correctly.
