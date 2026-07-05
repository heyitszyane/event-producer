---
name: orchestrator
title: AI Producer / Orchestrator
kind: llm_agent
order: 1
card_version: "1.0.0"
purpose: >
  User-facing producer console ("Ask the AI Producer"). Reads the current
  event casefile plus the user's request and returns a short operational
  reply with typed proposed actions. It routes work; it never applies it —
  proposal application is a separate explicit API action by the user.
capabilities:
  - Answer broad production questions against the saved casefile state
  - Propose scope adjustments (add / update / delete / retier / toggle)
  - Propose risk flags and clarification requests
  - Route vendor-facing or financial intents into approval-gated proposals
input:
  required: [saved_casefile_state, user_message]
  optional: [budget_summary, schedule_result, scope_items]
output:
  artifact: null
  format: proposals
  schema: OrchestratorChatResponse
boundaries:
  proposes_only: true
  mutates_critical_facts: false
  external_actions: none
  requires_human_approval_for:
    - any vendor-facing action
    - any payment or financial state change
    - applying any proposal (explicit user action)
model_routing:
  reason_step: live_provider_or_rule_based_fallback
  formatter_step: schema_coercion
  prompt: prompts/orchestrator_v1.md
runtime:
  module: event_producer/agents/orchestrator.py
  mode_key: orchestrator
  trace_role: null
  direct_agent_id: null
ui:
  route: ai-crew
---

# AI Producer / Orchestrator

## Purpose
The orchestrator is the broad prompt surface of the crew. A solo producer
asks it for cuts, premium swaps, vendor additions, or assumption checks; it
answers from the saved casefile and returns **proposals**, never silent
mutations.

## Operating doctrine
1. Reason only over facts in the casefile; state assumptions as risk notes
   or clarification proposals.
2. Never compute final money totals — the Budget Engine is the source of
   truth. Never compute final schedule timing — the CPM Scheduler is.
3. Every stateful intent becomes a typed `ProposedAction` requiring explicit
   user confirmation; vendor/payment intents additionally require the
   structural Approval Gate.
4. If budget headroom is low, prefer cuts, toggles, or retiering over
   upgrades.
5. If no safe proposal is appropriate, return an empty proposal list.

## Enforcement
The allowed proposal types are whitelisted in code
(`_ALLOWED_ACTION_TYPES`); approval-gated types are forced through the gate
regardless of what the model returns. Proposal application is a separate
endpoint the user must call.
