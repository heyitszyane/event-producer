# Agent Skill Cards — Production Crew Registry

This directory is the **machine-readable contract layer** for the Event
Producer multi-agent crew. Each `*.md` file is one **agent skill card**: a
YAML frontmatter contract (what the role can do, what it consumes and
produces, and what it is structurally forbidden from doing) plus a markdown
instruction body (the role's operating doctrine).

The cards are not documentation-only. They are **loaded at runtime** by
`event_producer/agents/cards.py`, validated by `tests/test_p7o_agent_cards.py`,
served to the frontend by `GET /agents`, and rendered as the crew board on
the AI Crew (Mission Control) route. The directory of files *is* the
registry — there is no database.

The schema is adapted from a harness-agnostic personal agent-card registry
(capability contracts usable by any orchestrator harness), specialized here
for the event-production domain.

## Honest-claims rule

Every statement in a card must match what the code actually does. Cards
distinguish four kinds honestly:

| `kind` | Meaning |
|---|---|
| `llm_agent` | Reason step calls the live model provider seam (Gemini or OpenAI-compatible); formatter step coerces output to a typed Pydantic schema; rule-based fallback when no provider is available. |
| `rule_based_agent` | Deterministic, rule-driven logic (no model call). |
| `deterministic_engine` | Pure computational core (Decimal math / CPM), called from code — never invoked as an LLM tool. |
| `structural_gate` | A security boundary enforced in code, not in prompts. |

## Frontmatter contract fields

```yaml
name:            # unique slug; direct specialists match SpecialistAgentId
title:           # display title
kind:            # llm_agent | rule_based_agent | deterministic_engine | structural_gate
order:           # display order on the crew board
card_version:    # semver; bump on contract change
purpose:         # one-paragraph role summary
capabilities:    # list of verifiable abilities
input:
  required: []   # context the runtime supplies from the saved casefile
  optional: []
output:
  artifact:      # casefile artifact name written under artifacts/, or null
  format:        # structured_json | proposals | approvals
  schema:        # Pydantic model name, or null
boundaries:      # structural limits — enforced in code, asserted in tests
  proposes_only:
  mutates_critical_facts:
  external_actions:            # always "none" in this build
  requires_human_approval_for: []
model_routing:   # llm_agent only; null otherwise
  reason_step:
  formatter_step:
  prompt:        # path under event_producer/agents/ to the versioned prompt
runtime:
  module:        # implementing module path
  mode_key:      # key in model_mode_summary, or null
  trace_role:    # role string used in the pipeline agent trace, or null
  direct_agent_id: # SpecialistAgentId for user-directed runs, or null
ui:
  route:         # war-room route where this role's output lives
```

## The crew workflow

**First pass** (`EventProducer.run_casefile` → `run_event`): the pipeline
runs the crew in a fixed order — Brief Intake interprets the event brief
(structured casefile fields always win; conflicts are surfaced, never
overwritten) → Brief/Scope seeds the scope ledger → Creative Concept and
Scope Strategy propose direction (advisory artifacts) → **Budget Engine**
and **CPM Scheduler** compute the deterministic money/time truth → Vendor
Copy drafts reviewable text → Risk Review inspects the whole state. Every
output is saved as a casefile artifact under
`.local_state/event_producer/events/<id>/artifacts/`.

**Direct specialist runs** (`POST /casefiles/{id}/agents/{agent_id}/run`):
the user can task Creative Concept, Scope Strategy, Vendor Copy, or Risk
Review directly with an instruction. The runtime loads the saved casefile as
context (never a bare prompt), saves the output as an artifact, and raises
if the run attempted to mutate critical casefile basics.

**Structural safety**: any vendor-facing, payment, or state-changing action
must pass the Approval Gate (`security/action_gate.py`) — human approval is
enforced in code. Vendor-supplied text is treated as data, never as
instructions. All vendor interactions are audit-logged.

## Adding or changing a card

Keep one role per card; bump `card_version` on any contract change; run
`python3 -m pytest tests/test_p7o_agent_cards.py` — the tests reject cards
that drift from the runtime (unknown artifact names, missing prompt files,
dishonest boundary claims).
