---
name: risk_review
title: Risk Review Agent
kind: rule_based_agent
order: 7
card_version: "1.0.0"
purpose: >
  Inspects the whole event state — budget, schedule, vendors, scope, and
  casefile notices — and produces risk flags plus recommended next actions.
  Deliberately deterministic: risk detection is rule-driven so the same
  state always yields the same flags.
capabilities:
  - Flag budget realism, missing vendors, and lead-time hazards
  - Convert missing/conflicting casefile requirements into gap findings
  - Recommend next actions before vendor outreach
  - Run on direct user request with the saved casefile as context
input:
  required: [event_spec, budget_summary, schedule_result]
  optional: [vendors, vendor_messages, casefile_notices, instruction]
output:
  artifact: risk-review
  format: structured_json
  schema: RiskFlag
boundaries:
  proposes_only: true
  mutates_critical_facts: false
  external_actions: none
  requires_human_approval_for: []
model_routing: null
runtime:
  module: event_producer/agents/risk_flagger.py
  mode_key: null
  trace_role: Risk/Gap Flagger
  direct_agent_id: risk_review
ui:
  route: ai-crew
---

# Risk Review Agent

## Purpose
The crew's safety officer. Its direct runs report `deterministic_engine`
mode because it never calls a model — reproducibility matters more than
prose for risk findings.

## Operating doctrine
1. Read the full state, not a summary: budget, schedule, vendors, messages,
   and casefile notices.
2. Prefer concrete, actionable flags ("no AV vendor with a 14-day lead
   time") over generic warnings.
3. Surface unresolved missing/conflict requirements as blockers before
   vendor outreach.
4. Review only — it never mutates state and never executes actions.
