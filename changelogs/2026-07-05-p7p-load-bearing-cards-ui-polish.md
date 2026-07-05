# P7P — Load-bearing skill cards + submission UI polish (2026-07-05)

Branch: `feat/p7p-hosted-demo-submission`.

## Why

Final pre-submission sprint (deadline 2026-07-06 23:59 PT). Two goals:
(1) upgrade the "Agent skills" claim from runtime-loaded *contracts* to
runtime-loaded *skills* by making the card registry drive live agent
behavior; (2) clear the UI feedback from the post-P7O review so the demo
video can be recorded (compact specialist outputs, info hints, vendor
declutter, nav rebrand).

## What changed

### 1. Skill cards became load-bearing (backend)

- `event_producer/agents/cards.py` gained `get_agent_card(name)` and
  `assemble_system_prompt(card_name, base_prompt)` — the single seam that
  appends a card's markdown instruction body (with name + card_version
  provenance) to the versioned prompt.
- All 5 LLM reason steps assemble their live system prompt through the seam:
  orchestrator, brief_intake, creative_concept, scope_strategy,
  vendor_coordinator (card `vendor_copy`). The contract served by
  `GET /agents` is now literally the doctrine the model runs under.
- `tests/test_p7p_load_bearing_cards.py` pins it: every assembled prompt
  contains the versioned prompt AND the card body; an end-to-end test
  captures the provider call and asserts the card doctrine reached it.

### 2. Card doctrine enrichment (global, honest)

- The 5 LLM cards' instruction bodies gained real event-production doctrine:
  triage order + headroom ladder (orchestrator), market-realism +
  money-critical facts (brief intake), hero-moment/cost-gravity craft rules
  (creative concept), allocation bands + savings levers ranked by
  savings-per-pain (scope strategy), standard negotiation asks
  (vendor copy). All market-neutral per submission guidance — no
  city-specific price assumptions; the one SGD-specific example was
  generalized. `card_version` 1.0.0 → 1.1.0 on all five.

### 3. Mission Control compact outputs (web)

- Purpose-made `ConceptOutput` / `StrategyOutput` renderers inside
  `AgentMissionControl.tsx` replace the `<details>` embeds of the legacy
  full-page `CreativeConcept` / `ScopeStrategy` components (both deleted,
  along with their orphaned CSS and the `.mission-embed` chrome-stripping).
- Cards read the freshest saved artifact payload first (direct-run payloads
  win over the last pipeline-run props). `handleRun` marks the just-run
  agent so re-hydration skips its redundant artifact fetch (evaluator minor
  from P7O).

### 4. Info hints, vendor declutter, nav rebrand (web)

- New `InfoHint` component (hover "i", native title tooltip + aria-label):
  Overview panels, Budget, Run of Show, Approvals, Vendor Copy, producer
  console, Production Crew header, and every mission card (kind explained
  honestly: LLM vs rule-based vs deterministic engine vs structural gate).
- Vendor Copy: persistent "Draft only — not sent from the app" badge on the
  header; "Response fields & risk notes" collapse into a
  collapsed-by-default `<details>` band with a count.
- Side nav brand: "Event Producer / Your AI production crew / v{version}",
  version imported from `web/package.json` (not hardcoded).

### 5. Dev harness

- `web/next.config.js`: env-driven `distDir` (`NEXT_DIST_DIR`, default
  `.next`) so a second verify dev server cannot corrupt the primary dev
  server's build dir; `.next-verify/` gitignored.

### 6. Vendor Notebook (persistent per-vendor workspace)

Diagnosis (Zyane, 2026-07-05): the Vendors route was too thin to be useful —
one casefile-level draft, session-only vendor rows, no history, no statuses.
Rebuilt as a solo producer's chase list, scoped down from ChatGPT's P7M2
brief (single `vendor-notebook` artifact over the existing store seam
instead of per-vendor file trees; one current draft per vendor with history
in the log):

- `event_producer/storage/vendor_notebook.py` — vendor records (workflow
  status, payment planning fields, contacts), append-only logs (capped at
  200/vendor), current draft with copied/manually-sent tracking,
  forward-only status auto-advance, injection screening of vendor replies
  on entry, and `prompt_context_for()` which yields the selected vendor's
  context only, withholding flagged reply bodies.
- Endpoints: vendors CRUD, `/log`, `/draft`, `/draft/mark-copied`,
  `/draft/mark-manually-sent` under `/casefiles/{id}/vendors`;
  `SpecialistAgentRequest.vendor_id` scopes `vendor_copy` runs; scoped runs
  save onto the vendor record (draft_generated / follow_up_generated log
  entries) instead of the legacy casefile-level artifact, which remains
  fully supported for scope-less runs.
- Fixed a real pre-existing gap: the refine `instruction` never reached the
  vendor draft prompt (`_draft_context` dropped it). It now flows to live
  and fallback paths; the deterministic fallback writes instruction-aware
  follow-up copy addressed to the vendor contact.
- Risk Review now surfaces a deterministic chase list from the notebook:
  vendors awaiting replies and user-recorded payment due dates.
- `web/components/VendorNotebook.tsx` — master-detail UI: vendor list with
  workflow/payment/due badges; status selects that PATCH-and-log on change;
  quick actions (mark deposit paid / paid in full / settled — recorded
  only); per-vendor draft panel (generate/refine, save, copy, mark manually
  sent); activity log with vendor-response input and a visible
  `injection-flagged` badge; collapsible profile & payment editor; optional
  import of run-fixture vendor suggestions (user-initiated, labeled).
  Session-only `VendorsCard` deleted; the legacy casefile-level
  `VendorCopyPanel` stays reachable under a collapsed details when that
  artifact exists.
- 14 new API tests: persistence across app instances, payment/settled
  logging, injection flags, per-vendor draft isolation (vendor B's log
  never reaches vendor A's prompt; flagged text withheld; instruction
  present), copied/sent/follow-up flow, 409 without draft, legacy
  compatibility, and risk-review chase signals.

## Docs

README, CLAUDE.md §7, and docs/REPO_SITEMAP.md updated to the load-bearing
claim and the current component list.

## QA

`pytest` 318 passed · `mypy` clean · `ruff` clean · `pnpm -C web run lint`
clean (pre-existing font warning only) · `pnpm -C web run build` green ·
`git diff --check` clean. UI verified in-browser against a live backend
(registry board, compact outputs from saved artifacts, vendor chip +
collapse, rebrand, info hints).
