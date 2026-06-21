# Event Producer

> AI-assisted event production — rule-based role-agent crew, deterministic
> budget/schedule engines, structural human approval wall, scripted security
> beat.

## What this is

Event Producer is a **capstone prototype** for AI-assisted event production.
It demonstrates how an event can be taken from a messy brief to a scoped,
costed, scheduled, and approval-gated run-of-show — without any live LLM
calls, live vendor messaging, or production persistence.

It was built as a Google x Kaggle 2026 capstone project under **Agents for
Business**.

## Current status

**Post-P6F Rescue Hardening** · Branch: `main` · [CHANGELOG](CHANGELOG.md)

- **177 tests passing.** Deterministic Budget Engine (zero-sum, Decimal-only)
  and CPM Scheduler (dependency/lead-time/anchor/cycle validation).
- **Security action-gate is structural** — enforced in code (`action_gate.py`),
  not in prompts. No financial or state-changing action executes without a
  human-approved `Approval` object.
- **Scripted deterministic security beat** — 3 vendor/payment-change fixtures
  treated as untrusted data; no external action executed, no state mutation
  executed.
- **Mission-control frontend** — Next.js 14 static export on Firebase Hosting,
  FastAPI backend on Cloud Run.
- **Agent crew** — rule-based role agents (brief/scope, budget manager,
  production manager, vendor coordinator, risk/gap flagger) with
  reason->formatter splits. **No live Gemini or ADK runtime.**
- **Honest-claims rule:** all public docs distinguish implemented, scripted
  deterministic demo, structural seam, and deferred work.

## Demo spine

```text
Messy event brief
  -> rule-agent crew parses and routes work
  -> scope catalogue proposes event-production line items
  -> Budget Engine computes contingency / spendable / headroom (reconciles to zero)
  -> CPM Scheduler creates run-of-show and critical path
  -> Vendor Coordinator drafts an outbound action
  -> structural approval wall blocks vendor-facing execution
  -> scripted security beat shows vendor/payment-change text treated as untrusted data
  -> mission-control UI renders the state for human review
```

## What is implemented

- **Budget Engine** — Pure Python, Decimal arithmetic, deterministic. Budget
  reconciles to zero (inflows minus outflows minus contingency). Tier-gating
  (must/should/could/wow). Multi-currency with line-total-first FX rounding.
  Receipt variance aggregation. 30+ tests.
- **CPM Scheduler** — Pure Python, deterministic. Forward/backward pass,
  dependency resolution, lead-time validation, anchor constraints, cycle
  detection, conflict reporting. 25+ tests.
- **Agent crew** — 5 role agents + orchestrator with reason->formatter splits.
  Rule-based (not live Gemini). 15+ tests.
- **Agent trace** — 5 structural role-agent steps recorded during the run
  (`AgentTraceStep` schema). Rendered in the frontend.
- **Security action-gate** — `enforce()` blocks 8 gated actions
  (`change_payment_details`, `mark_paid`, `reschedule`, `change_scope`,
  `send_vendor_message`, `approve_budget`, `lock_scope`, `release_funds`)
  without a human-approved `Approval`. Tested end-to-end.
- **REST API** — FastAPI with `/run`, `/event/{id}`, `/approvals`,
  `/approvals/{id}`, `/chat`, `/healthz`. HITL approval flow with action-gate
  integration. Consistent error envelope. CORS driven by `ALLOWED_ORIGINS`.
- **Frontend mission-control dashboard** — 11 React components (AgentCrewTrace,
  ApprovalInbox, BudgetCard, ChatPane, ConflictReportCard, EventCommandHeader,
  RiskCard, RunOfShowCard, ScopeCard, SecurityBeat, VendorsCard). Two-column
  responsive grid, design token system, accessibility landmarks. Static export.
- **MCP event-store wrapper** — `McpServer` wraps the `EventStore` ABC. Honest
  CRUD/list/delete via the provider seam. No private introspection.
- **Deployment lane** — Cloud Run (FastAPI) + Firebase Hosting (static export).
  Cloud Build pipeline with 4 QA gates (mypy + ruff + pytest + build).

## What is scripted / deterministic demo

- **Scripted security beat** — 3 seeded vendor-message fixtures (crude payment
  change, subtle IBAN change, image-channel seeded text). All fixtures record
  `external_action_executed: false` and `state_mutation_executed: false`.
  Injection flags are **advisory only** — the structural action gate is the
  load-bearing control.
- **Vendor messages** — `InMemoryVendorSourcer` returns 5 hardcoded vendors.
  Vendor coordinator drafts RFPs from templates. No live outbound messaging.
- **Agent reasoning** — Rule-based, not live Gemini. Agents produce structured
  output via deterministic logic (catalogue lookups, engine calls).
- **Chat / production log** — Messages generated from agent step summaries,
  not from live LLM chat.
- **Demo seed data** — `scripts/seed_demo.py` runs the networking event
  pipeline against a running API server.

## What is a structural seam

- **EventStore** — `EventStore` ABC defines the persistence contract.
  `InMemoryEventStore` is the only concrete implementation. **Firestore is
  deferred** — the seam is in place but not wired to a production database.
- **FxRateProvider** — `StaticFxRateProvider` returns seeded rates. Live FX feed
  is deferred.
- **VendorSourcer** — `InMemoryVendorSourcer` returns hardcoded vendors. Live
  vendor directory lookup is deferred.
- **Model routing / agent skills** — Reason/formatter split is represented
  structurally. Live Gemini/Flash routing and formal ADK Agent Skills
  packaging are deferred.

## What is deferred / not implemented

- Firestore persistence (in-memory only)
- Live Gemini / ADK integration (rule-based agents only)
- Live Telegram relay (scripted fixtures only)
- Production auth / multi-user (`X-Demo-User` is a demo-time header gate)
- Receipt OCR (image-channel fixture is seeded text with `ocr_implemented: false`)
- Live FX feed (static seeded rates only)
- Calendar write-back
- Formal ADK Agent Skills packaging (only skill-like role modules)

## Architecture

```text
ADK-style multi-agent (Python, rule-based) on Cloud Run
  -> role agents (brief/scope, budget, production, vendor, risk) + orchestrator
  -> reason->formatter splits per agent
  -> deterministic Budget Engine + CPM Scheduler (called from code, not LLM tools)
  -> structural action gate (enforce() blocks gated actions without approval)
  -> security beat (3 deterministic fixtures, advisory injection flags)
  -> MCP wrapper over event-store (honest CRUD via provider seam)
Frontend:       Next.js 14 static export on Firebase Hosting
Backend:        FastAPI on Cloud Run
Persistence:    InMemoryEventStore (Firestore-ready provider seam)
Validation:     Pydantic (strict mode, float rejection for monetary fields)
Contracts:      Typed Pydantic JSON
```

The Budget Engine and Scheduler are **plain Python called from code** — never
registered as LLM tools. Agents that both reason and emit typed JSON use a
**reason->formatter split** to maintain this boundary.

## Run locally

```bash
# Backend (run the pipeline directly)
pip install -r requirements.txt
python3 -m event_producer.main

# API server
python3 -m uvicorn event_producer.main:create_app --factory --host 127.0.0.1 --port 8080 --reload

# Frontend
pnpm -C web install --frozen-lockfile
NEXT_PUBLIC_API_BASE_URL=http://localhost:8080 pnpm -C web run dev
```

For the frontend to reach the backend at build/runtime, set:

```bash
export NEXT_PUBLIC_API_BASE_URL=http://localhost:8080
```

### Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `ALLOWED_ORIGINS` | CORS allowed origins (comma-separated) | No (defaults to `http://localhost:3000,http://localhost:8080`) |
| `NEXT_PUBLIC_API_BASE_URL` | Frontend API base URL | For frontend build against backend |

> **Secrets rule:** Never commit `.env*`, `*.key`, or service-account JSON.
> These are gitignored.

## Default demo input

```json
{
  "brief": "1 day AI networking event",
  "budget_cap": "10000",
  "contingency_pct": "10",
  "attendees": 50,
  "event_type": "corporate",
  "venue_type": "indoor",
  "date": "2026-06-30"
}
```

Run it:

```bash
curl -X POST http://localhost:8080/run \
  -H "Content-Type: application/json" \
  -H "X-Demo-User: demo-user" \
  -d '{
    "brief": "1 day AI networking event",
    "budget_cap": "10000",
    "contingency_pct": "10",
    "attendees": 50,
    "event_type": "corporate",
    "venue_type": "indoor",
    "date": "2026-06-30"
  }'
```

### Expected output summary

- **scope_items**: 6 (3 must, 2 should, 1 could)
- **budget_summary**: populated lines, category rollups, tier rollups,
  contingency reserve, spendable, included totals, headroom, zero-sum holds
- **schedule_result**: 6 ordered tasks with dependencies and critical path
- **agent_trace**: 5 role-agent steps
- **approvals**: 1 pending approval (human-required before vendor send)
- **chat_log**: 6 production messages explaining pipeline steps
- **security_beat**: `scripted_demo_ready`, 3 fixtures,
  `external_action_executed: false`, `state_mutation_executed: false`

## Security model

- **Structural action gate** (`event_producer/security/action_gate.py`):
  `enforce()` blocks any gated action (`change_payment_details`, `mark_paid`,
  `reschedule`, `change_scope`, `send_vendor_message`, `approve_budget`,
  `lock_scope`, `release_funds`) without a human-approved `Approval` object
  (`status == "approved"` and `approved_by` set). Enforced in code, not in
  prompts.
- **Injection flagging** (`event_producer/security/injection_flag.py`):
  heuristic detection of instruction overrides, role changes, payment-change
  language, credential requests, urgency pressure, authority pressure, and
  boundary markers. Flags are **advisory** — the structural action gate is
  the load-bearing control.
- **Audit log** (`event_producer/security/audit_log.py`): append-only trail for
  gated actions.
- **Data-not-instruction boundary**: vendor-supplied data is treated as
  untrusted. It is never executed and never interpolated into instructions.

This is a scripted, deterministic, test-backed security demo — not live
Telegram, not live OCR, and not LLM-generated.

## Frontend mission control

The frontend (`web/`) is a Next.js 14 static export rendered in the browser
and served by Firebase Hosting. It calls the backend via
`NEXT_PUBLIC_API_BASE_URL`.

Modules:
- **EventCommandHeader** — event identity, Run button, collapsible input form
  with 7 field-level validation rules
- **AgentCrewTrace** — 5-step timeline of role-agent steps with statuses,
  deterministic cores, artifacts
- **BudgetCard** — lines, category rollups, tier pills, headroom, variance
- **RunOfShowCard** — ordered tasks, critical path, anchor highlighting
- **ApprovalInbox** — approvals auto-expanded when pending; structural gate
  banner
- **SecurityBeat** — 3 scripted fixtures, blocked actions, no-execution status
- **ScopeCard** — tier-grouped scope items
- **RiskCard** — risk/gap flags
- **VendorsCard** — vendor cards with lock status
- **ChatPane** — production log (read-only) from `chat_log`
- **ConflictReportCard** — schedule conflicts when present

Layout: two-column responsive grid (60/40), single-column on mobile, semantic
landmarks, `aria-label`/`aria-labelledby`, `prefers-reduced-motion` support.

## Tests and quality gates

| Gate | Command |
|------|---------|
| Tests | `python3 -m pytest tests/ -v` |
| Lint | `python3 -m ruff check .` |
| Type check | `python3 -m mypy event_producer` |
| Frontend build | `pnpm -C web install --frozen-lockfile && pnpm -C web run build` |

177 tests: budget engine, CPM scheduler, agents, API, security action-gate,
injection flag, audit log, MCP server, FX rates, default demo contract, P6F
security demo. 9 Gherkin eval cases under `tests/eval_cases/`.

## Repository map

```text
event_producer/
├── agents/          # Role agents + reason->formatter splits
├── engines/         # Deterministic cores (budget, scheduler)
├── models/          # Pydantic schemas
├── providers/       # Moat-seam interfaces (abstract)
├── security/        # Action-gate, injection flag, audit log
├── mcp/             # MCP wrapper over event-store (honest CRUD)
└── main.py          # Composition root + InMemoryEventStore
```

See [docs/REPO_SITEMAP.md](docs/REPO_SITEMAP.md) for the full folder-by-folder
breakdown.

## QA Commands

| Gate | Command |
|------|---------|
| Tests | `python3 -m pytest tests/ -v` |
| Lint | `python3 -m ruff check .` |
| Type check | `python3 -m mypy event_producer` |
| Frontend build | `pnpm -C web install --frozen-lockfile && pnpm -C web run build` |

## Deployment lane

- **Backend**: Cloud Run (FastAPI + uvicorn). Container built via
  `deploy/Dockerfile`, CI/CD via `deploy/cloudbuild.yaml` (4 QA gates:
  mypy + ruff + pytest + build) `waitFor` all build/deploy steps.
- **Frontend**: Firebase Hosting serves `web/out/` (static export, configured
  in `deploy/firebase.json`). No server-side rendering.
- Run commands: `python3 -m uvicorn event_producer.main:create_app --factory`
  (backend), `pnpm -C web run build` (frontend).

## Capstone notes

This project demonstrates:
- **ADK-style multi-agent architecture** — role agents with
  reason->formatter splits (rule-based, not live ADK runtime)
- **Deterministic correctness** — Budget Engine and CPM Scheduler are pure
  Python, Decimal-only, fully testable
- **Structural security** — action-gate enforced in code, not prompts
- **HITL approval flow** — pending approval blocks vendor-facing actions
- **MCP wrapper** — stable CRUD interface over the EventStore provider seam
- **Eval framework** — Gherkin scenario files + unit tests
- **Deployment** — Cloud Run + Firebase Hosting with QA-gated Cloud Build

Honesty boundaries: this is a capstone prototype. Production auth, live Gemini,
Firestore, Telegram, OCR, and calendar write-back are **not implemented**.

## Concepts Demonstrated

| Concept | Where |
|---------|-------|
| ADK-style multi-agent | `event_producer/agents/` -- role agents + reason->formatter splits (rule-based) |
| Skill-like role modules | Reusable role modules with typed inputs/outputs; formal Agents CLI skill packaging is deferred |
| Security / context hygiene | `event_producer/security/` -- structural action-gate + injection flag |
| Deployment | Cloud Run + Firebase Hosting |
| MCP | `event_producer/mcp/` -- wrapper over event-store via provider seam |
| Eval framework | `tests/` -- Gherkin eval cases + unit tests |
| Separated evaluation | Build itself runs planner->generator->evaluator |
| Model-routing seam | Reason/formatter split is represented structurally; live Gemini/Flash routing is deferred |

## Safety Rules

- **No secrets in code.** Ever. `.env*` is gitignored.
- **No force-push.** Ever.
- **Stage explicitly.** Never `git add -A`.
- **`main` stays green.** Branch per phase -> QA gate -> merge --no-ff -> push.

## License

CC-BY-4.0. See `LICENSE`.
