---
name: approval_gate
title: Structural Approval Gate (HITL)
kind: structural_gate
order: 10
card_version: "1.0.0"
purpose: >
  The human-in-the-loop security boundary. No vendor-facing, financial, or
  state-changing action executes without an explicit human approval. The
  gate is enforced in code (security/action_gate.py), not in prompts — an
  LLM cannot talk its way past it.
capabilities:
  - Block gated actions until a matching human approval exists
  - Force approval-gated proposal types through the Approvals route
  - Record every vendor interaction in an append-only audit log
  - Flag suspicious vendor-supplied text (advisory injection flag)
input:
  required: [requested_action, approvals_state]
  optional: []
output:
  artifact: null
  format: approvals
  schema: Approval
boundaries:
  proposes_only: false
  mutates_critical_facts: false
  external_actions: none
  requires_human_approval_for:
    - vendor-facing messages or commitments
    - payment or financial state changes
    - any state mutation requested by an agent
model_routing: null
runtime:
  module: event_producer/security/action_gate.py
  mode_key: security
  trace_role: null
  direct_agent_id: null
ui:
  route: approvals
---

# Structural Approval Gate (HITL)

## Purpose
Human-in-the-loop is the default here, not an afterthought. Agents propose;
humans approve; only then does anything state-changing happen.

## Enforcement model
1. `enforce()` is called in code on the action path — there is no code path
   that executes a gated action without an approval record.
2. Vendor-supplied data is treated as untrusted input (data-not-instruction
   boundary); an advisory injection flagger marks suspicious content, and
   flagged content still cannot trigger actions because the gate is
   structural.
3. Every vendor interaction is written to an immutable audit log
   (`security/audit_log.py`) rendered on the Audit route.
4. This build intentionally has no outbound integrations; even so, the gate
   exists so that adding one later cannot bypass human approval.
