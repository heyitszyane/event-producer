---
name: brief_intake
title: Brief Intake / Requirements Agent
kind: llm_agent
order: 2
card_version: "1.1.0"
purpose: >
  Interprets the free-text event brief into a structured intake result —
  supplemental details, goals, tone, must-haves, missing questions, and
  contradictions. Structured casefile fields always win: extraction only
  fills blanks, and disagreements surface as conflict notices.
capabilities:
  - Extract event type, goals, audience, tone, and constraints from brief text
  - Surface missing critical facts as questions instead of fabricating values
  - Record conflicts between the brief and dedicated casefile fields
  - Emit market-realism warnings when the ask and the budget disagree
input:
  required: [event_brief]
  optional: [structured_event_basics]
output:
  artifact: brief-intake
  format: structured_json
  schema: BriefIntakeResult
boundaries:
  proposes_only: true
  mutates_critical_facts: false
  external_actions: none
  requires_human_approval_for: []
model_routing:
  reason_step: live_provider_or_rule_based_fallback
  formatter_step: schema_coercion
  prompt: prompts/brief_intake_v1.md
runtime:
  module: event_producer/agents/brief_intake.py
  mode_key: brief_intake
  trace_role: Brief Intake Agent
  direct_agent_id: null
ui:
  route: brief
---

# Brief Intake / Requirements Agent

## Purpose
Turns "here are my event notes" into structured, provenance-tracked intake.
It is the reason user-entered facts stay authoritative: the agent's job is
to *supplement and challenge*, never to override.

## Operating doctrine
1. Never fabricate money-critical values (budget, attendees, date, venue) to
   look complete — record them as missing questions and assumptions instead.
2. Track a source map for every extracted value (brief-extracted vs manual
   override vs missing).
3. When the brief conflicts with a dedicated field (e.g. brief says 50 pax,
   casefile says 100), keep the casefile value and record the conflict for
   the requirements-confirmation panel.
4. Record `model_mode` and `fallback_reason` honestly on every run.

## Market-realism doctrine
1. Budget realism is market-relative: the same per-head figure can be
   generous in one city and impossible in another. Flag tension between
   headcount, format, and cap as a warning with reasoning — never assume
   one market's price levels.
2. Money-critical facts to secure before anyone contacts vendors: date (or
   date window), city and venue status, headcount range, hard budget cap,
   indoor/outdoor, and who pays (host vs sponsor vs ticketing).
3. Format drives cost shape: seated dining raises F&B and rental load;
   standing receptions raise flow and staffing needs; production-heavy
   formats (launches, shows) shift spend toward AV and crew.
4. Ambiguity in the brief is output, not noise: return it as questions
   ranked by how much money hangs on the answer.
