# P7O — Agent skill cards, Mission Control, contingency input (2026-07-05)

Branch: `feat/p7o-agentic-mission-control` → merged `--no-ff` to `main`, tag `p7o`.

## Why

Post-P7N review: the build looked functional but the AI Crew route read as
"agentic theatre" — the real multi-agent engineering (direct specialist runs
over saved casefile context, structural gates, deterministic engines) was
not inspectable, and the competition's "Agent skills" concept had no
code-level artifact. P7O makes the agent system a first-class, contract-
backed, user-operable surface.

## What changed

### 1. Agent skill-card registry (backend)

- `event_producer/agents/cards/` — 10 versioned role contracts, one file per
  crew member: orchestrator, brief intake, scope configurator, creative
  concept, scope strategy, vendor copy, risk review, budget engine, CPM
  scheduler, approval gate. Each card is YAML frontmatter (name, kind,
  purpose, capabilities, input/output incl. owned casefile artifact,
  structural boundaries, model routing/prompt ref, runtime wiring, UI route)
  plus a markdown instruction body. Schema adapted from a harness-agnostic
  personal agent-card registry, specialized for event production.
- Kinds stay honest: `llm_agent` (reason step through the provider seam with
  rule-based fallback), `rule_based_agent`, `deterministic_engine`,
  `structural_gate`.
- `event_producer/agents/cards.py` — loader that parses frontmatter and
  rejects contract drift: unknown kinds, unknown artifact names, unknown
  direct-agent ids, missing prompt files, model-routing claims on non-LLM
  cards, duplicate names.
- `GET /agents` (api.py) serves the parsed registry.
- `tests/test_p7o_agent_cards.py` — 7 contract tests, including honest-
  boundary assertions (orchestrator proposes-only; vendor copy approval-
  gated before external use; engines/gate not LLM-labeled).
- `requirements.txt` — PyYAML + types-PyYAML pinned explicitly (previously
  transitive).

### 2. Agent Mission Control (frontend)

- `web/components/AgentMissionControl.tsx` — single registry-driven crew
  board replacing SpecialistAgentWorkspace + AIProductionCrew +
  ScopeStrategy + CreativeConcept stack (the latter two components survive,
  embedded inside their agents' cards). Per card: kind chip, honest mode
  badge (live artifact payload → model-mode summary → trace → kind default),
  last-activity line, direct ask/refine for the four specialists, embedded
  full concept/strategy output (with Add-to-scope preserved), deep links for
  pipeline roles, expandable role-card contract (capabilities, boundaries,
  source file, prompt version).
- `web/pages/index.tsx` — ai-crew route reordered: producer console first
  (with an empty-state hint pre-run), then the crew board. Route header
  renamed to "Agent Mission Control".
- CSS: `.mission-*` styles; `.war-room .btn--sm/.btn--xs` compaction (the
  base war-room button rule was overriding small sizes — root cause of the
  oversized card buttons).

### 3. Contingency % (delegated generator task)

- `EventBasics.contingency_pct` (Decimal, 0–100, optional, float-rejected)
  → `resolve_event_state` source tracking (never blocks confirmation) →
  `run_casefile` manual-constraint override → existing `run_event`
  resolution → Budget Engine (untouched; it always took the parameter).
- Event Basics form field + validation; Budget route contingency reserve
  health row. `tests/test_p7o_contingency.py` (5 tests incl. zero-sum).

### 4. Vendors + header polish (delegated generator task)

- Removed both draft-status info banners (eyebrow + badges keep the safety
  framing).
- Fixed `.war-room textarea` specificity clamp (32px) that silently defeated
  `.vendor-copy-body` min-height; body now ~5 rows.
- Panel/card header rows filled with the `--paper-2` band for first-glance
  hierarchy.

## QA

- pytest 311 passed; mypy clean; ruff clean; web lint clean (pre-existing
  font warning); web build success.
- Browser smoke on an isolated stack (backend :8081 with scratchpad casefile
  root): registry board renders all 10 cards; seeded demo run; direct Risk
  Review run from a mission card saved an artifact and rendered flags;
  Budget shows "Contingency reserve (15.0%)" with zero-sum intact; Vendors
  declutter + 107px body verified; header bands applied.
- Independent evaluator subagent reviewed the phase diff (verdict artifact
  under `project_documents/result-artifacts/p7o/subagents/evaluator/`).

## Invariants

Budget zero-sum, contingency-first reservation, tier gating, scheduler
dependency/lead-time respect, structural action gate + HITL, and vendor
draft-only semantics are unchanged. `engines/budget.py`,
`engines/scheduler.py`, and `security/` were not modified.
