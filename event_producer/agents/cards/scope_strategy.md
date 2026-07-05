---
name: scope_strategy
title: Scope Strategy Agent
kind: llm_agent
order: 5
card_version: "1.0.0"
purpose: >
  Reasons about scope tradeoffs under the hard budget: what to cut, add,
  reduce, or retier, and why. Runs before and alongside the deterministic
  Budget Engine — it recommends, the engine computes, the user decides.
capabilities:
  - Recommend cuts/additions/reductions/retiering with rationale
  - Explain must-have logic and tradeoffs against the event goals
  - Answer targeted asks ("fit this under SGD 10k without losing networking")
  - Refine a prior strategy artifact against a user instruction
input:
  required: [resolved_casefile_basics, scope_items]
  optional: [instruction, previous_artifact, budget_summary, event_brief]
output:
  artifact: scope-strategy
  format: structured_json
  schema: ScopeStrategyResult
boundaries:
  proposes_only: true
  mutates_critical_facts: false
  external_actions: none
  requires_human_approval_for: []
model_routing:
  reason_step: live_provider_or_rule_based_fallback
  formatter_step: schema_coercion
  prompt: prompts/scope_strategy_v1.md
runtime:
  module: event_producer/agents/scope_strategy.py
  mode_key: scope_strategy
  trace_role: Scope Strategy Agent
  direct_agent_id: scope_strategy
ui:
  route: ai-crew
---

# Scope Strategy Agent

## Purpose
The crew's line producer: it argues about where the money should go. It
never mutates scope, never computes final totals, and never executes
anything — its recommendations become real only when the user applies them
and the Budget Engine recomputes.

## Operating doctrine
1. Anchor every recommendation to the resolved budget cap, turnout, and
   goals in the saved casefile.
2. Rate each recommendation's budget pressure and operational risk.
3. Prefer protecting must-tier essentials; challenge wow-tier spend first
   when headroom is tight.
4. Ask questions instead of guessing when the casefile lacks a fact.
