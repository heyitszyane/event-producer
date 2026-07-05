---
name: scope_configurator
title: Brief/Scope Configurator
kind: rule_based_agent
order: 3
card_version: "1.0.0"
purpose: >
  Seeds the editable scope ledger from the intake result using a rule-based
  scope catalogue per event type, constrained by the hard budget cap. The
  user then owns the ledger — every item can be edited, toggled, retiered,
  or removed on the Scope route.
capabilities:
  - Map event type + attendees to a catalogue of scope items with tiers
  - Propose quantities and unit costs as editable starting points
  - Keep proposals within the budget-gated tier structure (must/should/could/wow)
input:
  required: [brief_intake_result, budget_cap, attendees]
  optional: [event_type]
output:
  artifact: null
  format: structured_json
  schema: ScopeItem
boundaries:
  proposes_only: false
  mutates_critical_facts: false
  external_actions: none
  requires_human_approval_for: []
model_routing: null
runtime:
  module: event_producer/agents/brief_scope.py
  mode_key: null
  trace_role: Brief/Scope Agent
  direct_agent_id: null
ui:
  route: scope
---

# Brief/Scope Configurator

## Purpose
Provides the first draft of the scope ledger so budget/schedule computation
has real line items to work with. Deliberately rule-based: seeding the
ledger from a catalogue is predictable and reviewable, and the user edits it
directly afterwards.

## Operating doctrine
1. Seed from the catalogue for the resolved event type; unknown types get a
   conservative generic set.
2. Every seeded item is a *starting point* — the Scope route is the single
   edit surface, and edits trigger deterministic budget/schedule recompute.
3. Never bypass tier structure: items carry must/should/could/wow tiers that
   the Budget Engine gates all-or-nothing per tier.
