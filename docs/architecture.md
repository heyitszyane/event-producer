# Event Producer Architecture

## System purpose

Event Producer is a local-demo event-production casefile system. It uses agents
for reasoning and drafting, deterministic engines for budget and schedule
invariants, and a structural approval wall for consequential actions.

## High-level architecture

```text
Next.js Paper War Room
  |
  +- Event Basics / Brief Intake
  +- Requirements Confirmation
  +- Agent Mission Control
  +- Scope / Budget / Run Sheet
  +- Vendor Notebook
  +- Approvals
  +- Audit / Settings
        |
        v
FastAPI backend
  |
  +- LocalCasefileStore
  |    +- casefile.json
  |    +- timeline.jsonl
  |    +- artifacts/*.json
  |
  +- Agent crew
  |    +- AI Producer / Orchestrator
  |    +- Brief Intake Agent
  |    +- Creative Concept Agent
  |    +- Scope Strategy Agent
  |    +- Vendor Copy Agent
  |    +- Risk Review Agent
  |
  +- Agent skill-card registry
  |    +- YAML frontmatter contracts
  |    +- markdown instruction bodies
  |    +- runtime prompt assembly
  |
  +- Deterministic engines
  |    +- Budget Engine
  |    +- Run Sheet / CPM Scheduler
  |
  +- Vendor Notebook
  |    +- vendor profiles
  |    +- workflow/payment planning status
  |    +- draft records
  |    +- injection-screened logs
  |
  +- Security / HITL
       +- action gate
       +- approval object validation
       +- data-not-instruction boundary
```

## Core state flow

1. User creates a casefile.
2. Backend writes a local `casefile.json` immediately.
3. User saves structured event basics and event notes.
4. Backend resolves state with structured fields first.
5. Agent run generates typed artifacts.
6. Deterministic engines compute budget and run-sheet outputs.
7. Agent outputs and engine results are saved under `artifacts/`.
8. Vendor work is saved in a `vendor-notebook` artifact.
9. Timeline events append to `timeline.jsonl`.

## Source precedence

Resolved event state uses this order:

1. User-entered structured fields.
2. User-edited saved casefile values.
3. Extracted values from event notes only when structured field is blank.
4. Missing/unknown state.
5. Seeded demo defaults only inside seeded demos.

This prevents defaults or LLM extraction from silently overriding the casefile.

## Agent/engine separation

| Component type | Owns | Does not own |
|---|---|---|
| LLM agents | judgment, language, proposals, drafts, risk framing | money invariants, schedule mechanics, external action |
| Deterministic engines | arithmetic, budget headroom, contingency, schedule mechanics | vendor prose, creative framing |
| Approval wall | permission to execute gated actions | model reasoning |
| Casefile store | durable local state and artifacts | production multi-user persistence |

## Deployment shape

- Backend: FastAPI, Cloud Run-compatible.
- Frontend: Next.js static export, Firebase/Vercel-compatible when built with
  `NEXT_PUBLIC_API_BASE_URL`.
- Storage: local JSON for capstone demo.
- Live model mode: optional provider seam.
- Fallback mode: deterministic/degraded behavior for clone reviewers without
  API keys.

## Deliberate non-goals

- production auth;
- multi-user tenancy;
- production cloud database;
- live vendor messaging;
- payment execution;
- autonomous vendor negotiation;
- calendar writeback;
- OCR;
- live vendor directory.
