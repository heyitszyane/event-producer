# Event Producer

> Live-agentic event production when a provider is configured — deterministic
> budget/schedule engines, structural human approval wall, and honest degraded
> fallback when live calls are unavailable.

## What this is

Event Producer is a **capstone prototype** for agentic event production.
It demonstrates how an event can be taken from a messy brief to a scoped,
costed, scheduled, and approval-gated run-of-show. The intended capstone demo
uses a configured live provider for the AI agents, while deterministic fallback
is treated as degraded/resilience mode for clone setups without a working key.

It was built as a Google x Kaggle 2026 capstone project under **Agents for
Business**.

## Current status

**P7H — Live-agentic showcase upgrade** · Branch: `codex/p7h5-structured-output-hardening` · [CHANGELOG](CHANGELOG.md)

- **268 backend tests passing.** Deterministic Budget Engine (zero-sum, Decimal-only)
  and CPM Scheduler (dependency/lead-time/anchor/cycle validation).
- **Messy-brief hero.** The primary product input is a messy event brief; the
  structured fields are optional manual overrides. Placeholder/default values
  do not win unless explicitly submitted as manual constraints; the response
  exposes provenance via `source_map` and `constraint_resolution`.
- **Stress-brief realism.** The Singapore 100-pax open-bar/canapes scenario
  resolves to 100 attendees end-to-end, costs per-attendee scope at quantity
  100, and flags the budget as at risk/over budget instead of showing a clean
  green plan.
- **Live model provider seam** (P7A/P7F/P7H). Server-side, lazy-loaded, and
  selectable through Settings or `.env`. Gemini, OpenRouter, hosted
  OpenAI-compatible endpoints, LM Studio, Ollama, and local OpenAI-compatible
  servers are supported. Provider diagnostics expose non-secret status and a
  one-click provider test from the UI. OpenRouter/OpenAI-compatible calls use
  JSON Schema response format where supported and retry JSON object mode if the
  provider rejects that parameter; Gemini uses response schemas when the
  installed SDK supports them.
- **Structured-output hardening** (P7H.5). Live provider JSON is repaired only
  for safe deterministic shape issues before Pydantic validation: missing brief
  text can be filled from the original brief, numeric-as-string fields can be
  stringified, missing optional lists become `[]`, and object values inside
  string lists become compact strings. The repair layer does not invent
  attendees, money, dates, vendors, or executable state-changing actions.
- **Editable scope + orchestrator proposals** (P7B/P7D-FIX). Scope items can be
  added, edited, deleted, toggled, and retiered via API endpoints. Recompute
  responses include before/after headroom, schedule status, and a notice when
  risk/trace data still reflects the last full run. Explicit deselect-all
  budgets zero included spend. The top "Ask the AI Producer" surface returns
  proposals that can be applied or dismissed.
- **Security action-gate is structural** — enforced in code (`action_gate.py`),
  not in prompts. No financial or state-changing action executes without a
  human-approved `Approval` object.
- **Scripted deterministic security beat** — 3 vendor/payment-change fixtures
  treated as untrusted data; no external action executed, no state mutation
  executed.
- **Paper War Room frontend** — Next.js 14 static export with a persistent
  side nav and route-like sections for Overview, Brief Intake, AI Crew, Scope,
  Budget, Run Sheet, Approvals, Vendors, Risks, and Audit Log. FastAPI backend
  remains the API source. Event title edits and vendor rows are
  frontend-session drafts only; they do not mutate backend event identity or
  persist vendor records.
- **AI Production Crew surface** — Brief Intake, Creative Concept, Scope
  Strategy, AI Event Producer/Orchestrator, Vendor Draft, Budget
  Engine/Manager, Run-of-Show/Production Manager, Approval Wall/Vendor
  Coordinator, and Risk/Gap Flagger are visible as crew cards with Runtime
  badges, model names, fallback reasons, and trace-derived task summaries.
- **Honest-claims rule:** all public docs distinguish implemented, scripted
  deterministic demo, structural seam, and deferred work.

## Demo spine

```text
Messy event brief
  -> live/fallback Brief Intake extracts requirements
  -> live/fallback AI Event Producer reasons over the casefile
  -> scope catalogue proposes event-production line items
  -> live/fallback Scope Strategy Agent reasons about tradeoffs without mutating scope
  -> Budget Engine computes contingency / spendable / headroom (reconciles to zero)
  -> CPM Scheduler creates run-of-show and critical path
  -> live/fallback Vendor Draft Agent drafts outbound copy
  -> structural approval wall blocks vendor-facing execution
  -> scripted security beat shows vendor/payment-change text treated as untrusted data
  -> Paper War Room UI renders the state for human review
```

## Demo Modes

| Mode | What happens | Intended use |
|---|---|---|
| Live provider | AI agents call the selected provider; Budget Engine, CPM Scheduler, and Approval Wall remain deterministic/source-of-truth controls. | Primary capstone demo |
| Strict live failure | The API returns a clear provider/model/agent error instead of silently falling back. Settings -> Test provider shows non-secret diagnostics, response format mode, and safe-repair fields. | Debugging and reviewer honesty |
| Fallback | Live-capable agents use deterministic degraded behavior and record fallback reasons in the UI. | Resilience/no-key clone path |

## What is implemented

- **Budget Engine** — Pure Python, Decimal arithmetic, deterministic. Budget
  reconciles to zero (inflows minus outflows minus contingency). Tier-gating
  (must/should/could/wow). Multi-currency with line-total-first FX rounding.
  Receipt variance aggregation. 30+ tests.
- **CPM Scheduler** — Pure Python, deterministic. Forward/backward pass,
  dependency resolution, lead-time validation, anchor constraints, cycle
  detection, conflict reporting. 25+ tests.
- **Agent crew** — role agents + orchestrator with reason->formatter splits.
  Brief Intake, Creative Concept, Scope Strategy, Vendor Draft, and the
  Orchestrator surface call the configured provider in live mode and degrade
  with explicit fallback reasons when live mode is unavailable or non-strict
  provider calls fail. Live providers request schema-shaped JSON where the
  upstream supports it, and a conservative provider-side repair layer handles
  recoverable type/shape drift before validation.
- **Agent trace** — 8 structural role-agent steps recorded during the run
  (`AgentTraceStep` schema). Rendered as a secondary technical trace.
- **Security action-gate** — `enforce()` blocks 8 gated actions
  (`change_payment_details`, `mark_paid`, `reschedule`, `change_scope`,
  `send_vendor_message`, `approve_budget`, `lock_scope`, `release_funds`)
  without a human-approved `Approval`. Tested end-to-end.
- **REST API** — FastAPI with `/run`, `/runtime/model`,
  `/runtime/model/test`, `/settings/model`, `/event/{id}`,
  `/event/{id}/chat`,
  `/event/{id}/proposals/{id}/apply`, `/event/{id}/proposals/{id}/dismiss`,
  `/event/{id}/scope-items`, `/event/{id}/scope-items/{id}`, `/approvals`,
  `/approvals/{id}`, `/event/{id}/approvals`,
  `/event/{id}/approvals/{approval_id}`, `/chat`, `/healthz`. HITL approval
  flow with action-gate integration. The `/approvals` routes are legacy
  sample-demo routes; the main run path uses event-scoped approvals.
  Consistent error envelope. CORS driven by `ALLOWED_ORIGINS`.
- **Frontend Paper War Room** — React components for intake, runtime summary,
  provider Settings/test diagnostics, editable requirements provenance preview,
  AI Production Crew, creative concepts, Scope Strategy, scope, budget, run
  sheet, approvals, vendor draft/approval wall, security, vendors, risks, and
  audit log. The shell uses a persistent side nav and route-like sections.
  Static export.
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
  Vendor Draft can draft copy through the live/fallback model seam, but no live
  outbound messaging occurs.
- **Agent reasoning fallback** — Brief Intake, Creative Concept, Scope
  Strategy, Vendor Draft, and Orchestrator can call a configured live model
  provider. If live mode is disabled or a non-strict provider call fails, the
  UI marks the affected agent as degraded fallback. Deterministic
  budget/schedule engines remain the source of truth.
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
  structurally. Live provider routing exists for Gemini plus
  OpenAI-compatible endpoints; formal ADK Agent Skills packaging is deferred.

## What is deferred / not implemented

- Firestore persistence (in-memory only)
- Fully managed production live-provider operations beyond the local `.env` /
  Settings harness. ADK integration remains deferred.
- Live Telegram relay (scripted fixtures only)
- Production auth / multi-user (`X-Demo-User` is a demo-time header gate)
- Receipt OCR (image-channel fixture is seeded text with `ocr_implemented: false`)
- Live FX feed (static seeded rates only)
- Calendar write-back
- Formal ADK Agent Skills packaging (only skill-like role modules)
- Live autonomous proposal execution (all proposals still require human Apply)

## Architecture

```text
ADK-style multi-agent (Python, live/fallback role agents) on Cloud Run
  -> role agents (brief/scope, budget, production, vendor, risk) + live-capable orchestrator
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
# One-command local dev harness
./scripts/dev.sh
```

Then open the frontend, go to **10 Settings**, choose Gemini, OpenRouter,
LM Studio, Ollama, or another OpenAI-compatible provider, paste the provider
key if needed, save, then click **Test provider**. The app writes only your
local gitignored `.env`, refreshes the running backend provider, and shows
provider/model/effective mode, success/failure, latency, sanitized error, and
response preview.

Manual commands are still available:

```bash
# API server
python3 -m uvicorn event_producer.main:create_app --factory --host 127.0.0.1 --port 8080 --reload

# API server with local secrets from .env
python3 -m uvicorn event_producer.main:create_app --factory --host 127.0.0.1 --port 8080 --reload --env-file .env

# Frontend
pnpm -C web install --frozen-lockfile
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8080 pnpm -C web run dev
```

For the frontend to reach the backend at build/runtime, set:

```bash
export NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8080
```

Local development may use `http://127.0.0.1:8080` or `http://localhost:8080`.
Firebase/static deployment must set `NEXT_PUBLIC_API_BASE_URL` to the Cloud Run
backend URL before `pnpm -C web run build`; there is no runtime server-side
proxy in Firebase Hosting. `deploy/cloudbuild.yaml` fails deployed frontend
builds when `_NEXT_PUBLIC_API_BASE_URL` is empty or when local backend URLs are
found in `web/out`.

### Where casefiles are stored

Casefiles, artifacts, and timelines are plain JSON files under
`.local_state/event_producer/events/<event_id>/` (override the root with
`EVENT_PRODUCER_CASEFILE_ROOT`). This is local demo storage, not a cloud
database; the **10 Settings** route shows the resolved root, the saved
casefile count, and the active casefile ID. Every pipeline run also saves a
`run-snapshot` artifact so the last run is restored after a page reload or a
backend restart. To reset local state, delete
`.local_state/event_producer/events` and restart.

To confirm which model provider the backend loaded at startup, call
`GET /runtime/model` with the demo header, or use **10 Settings** in the UI.
To run a tiny provider smoke test, call `POST /runtime/model/test` or click
**Test provider**. Both responses are non-secret: provider, mode, model name,
base URL/status, whether a key was loaded, response format mode, safe repair
fields, sanitized errors, and fallback reason only. Local settings writes are
accepted only from local dev hosts.

### Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `ALLOWED_ORIGINS` | CORS allowed origins (comma-separated) | No (defaults to localhost) |
| `ENABLE_LIVE_MODEL` | Enables the selected live model provider (exact `true`; otherwise fallback) | No (default: fallback) |
| `MODEL_PROVIDER` | `gemini`, `openrouter`, `openai_compatible`, `local`, `ollama`, or `lmstudio` | No (default: `gemini`) |
| `MODEL_NAME` | Generic model id override for non-Gemini providers | No |
| `ENABLE_LIVE_GEMINI` | Legacy Gemini-only toggle; still supported | No (default: fallback) |
| `GEMINI_API_KEY` | Server-side Gemini API key. Only read by the backend; never sent to the browser. See `.env.example`. | Only for Gemini live mode |
| `GOOGLE_API_KEY` | Legacy alias used if `GEMINI_API_KEY` is empty. | Only for Gemini live mode |
| `GEMINI_MODEL` | Model id for the live provider (default `gemini-2.5-flash`). | No |
| `OPENROUTER_API_KEY` | OpenRouter API key for `MODEL_PROVIDER=openrouter` | Only for OpenRouter live mode |
| `OPENROUTER_MODEL` | OpenRouter model id | No |
| `OPENAI_COMPATIBLE_API_KEY` | API key for a generic OpenAI-compatible endpoint | Only for hosted compatible endpoints |
| `OPENAI_COMPATIBLE_API_BASE_URL` | Chat-completions endpoint for OpenAI-compatible providers | Only for generic compatible endpoints |
| `LOCAL_LLM_API_BASE_URL` | Local chat-completions endpoint for `local` / `ollama` / `lmstudio` | No |
| `LOCAL_LLM_MODEL` | Local model id | No |
| `NEXT_PUBLIC_API_BASE_URL` | Frontend API base URL | For frontend build against backend; required for static deployment |

> **Secrets rule:** Never commit `.env*`, `*.key`, or service-account JSON.
> These are gitignored. Copy `.env.example` to `.env` to configure live mode.
> Local OpenAI-compatible servers may run without auth. If LM Studio requires an
> API token, set `OPENAI_COMPATIBLE_API_KEY` to that token; otherwise no
> Authorization header is sent for local providers.

## Demo seed briefs

### P7D Stress-test brief (Singapore open-bar scenario)

```json
{
  "brief": "1 night AI industry networking event with $10000 budget. Event will be held in an indoor bar or restaurant in Singapore, on 10 July 2026 between 6pm to 10pm. Open bar with canapes. Expected turnout 100 pax. Need basic AV system and banners. If budget permits, include some free merch such as branded t-shirts, caps and notebooks."
}
```

This scenario resolves to `100` attendees, parses the date as `2026-07-10`,
costs attendee-scaled items at quantity `100`, and triggers a prominent budget
realism warning in fallback mode.

### P7C Seed brief (calmer premium scenario)

```json
{
  "brief": "Need a 50-pax AI founder networking night in Singapore next Thursday. Budget is around 20k SGD. Want it to feel premium but not flashy, light F&B, a short fireside chat, and a few structured networking prompts. No full conference setup. Audience is founders, investors, and AI builders."
}
```

```json
{
  "brief": "Need a 50-pax AI founder networking night in Singapore next Thursday. Budget is around 20k SGD. Want it to feel premium but not flashy, light F&B, a short fireside chat, and a few structured networking prompts. No full conference setup. Audience is founders, investors, and AI builders."
}
```

Click "Try example" in the UI to load this seed brief.

## Default demo input (structured manual overrides)

```json
{
  "brief": "1 day AI networking event",
  "budget_cap": "10000",
  "contingency_pct": "10",
  "attendees": 50,
  "event_type": "corporate",
  "venue_type": "indoor",
  "date": "2026-06-30",
  "manual_constraints": {
    "budget_cap": true,
    "contingency_pct": true,
    "attendees": true,
    "event_type": true,
    "venue_type": true,
    "date": true
  }
}
```

Run it:

```bash
curl -X POST http://127.0.0.1:8080/run \
  -H "Content-Type: application/json" \
  -H "X-Demo-User: demo-user" \
  -d '{
    "brief": "1 day AI networking event",
    "budget_cap": "10000",
    "contingency_pct": "10",
    "attendees": 50,
    "event_type": "corporate",
    "venue_type": "indoor",
  "date": "2026-06-30",
  "manual_constraints": {
    "budget_cap": true,
    "contingency_pct": true,
    "attendees": true,
    "event_type": true,
    "venue_type": true,
    "date": true
  }
  }'
```

### Expected output summary

- **scope_items**: 6 (3 must, 2 should, 1 could), selected by default for
  budget basis
- **budget_summary**: populated lines, category rollups, tier rollups,
  contingency reserve, spendable, included totals, headroom, zero-sum holds
- **schedule_result**: 6 ordered tasks with dependencies and critical path
- **brief_intake**: extracted requirements / assumptions / gaps / confidence +
  `model_mode`
- **creative_concept**: advisory concepts + ideas + suggested additions/cuts +
  `model_mode`
- **agent_trace**: 7 role-agent steps (added **Brief Intake Agent** and
  **Creative Concept Agent**); each step exposes `model_mode` / `model_name` /
  `prompt_version` / `fallback_reason`.
- **approvals**: 1 pending approval (human-required before vendor send)
- **chat_log**: production messages explaining pipeline steps
- **security_beat**: `scripted_demo_ready`, 3 fixtures,
  `external_action_executed: false`, `state_mutation_executed: false`
- **model_mode_summary**: per-role mapping of `brief_intake`, `creative_concept`,
  `budget_manager`, `production_manager`, `vendor_coordinator`, `security` to one
  of `gemini_live | openai_compatible_live | rule_based_fallback | deterministic_engine | scripted_fixture | human_approval_gate`.

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
- **EventCommandHeader** — event identity, Run button, optional manual
  overrides with inactive/default badges and 7 field-level validation rules
- **AIProductionCrew** — top-level crew cards with mode badges, inputs,
  outputs, warnings, and approval-gate summaries
- **ExtractedRequirements** — resolved requirement basis with from-brief,
  manual-override, fallback-default, and missing provenance
- **AgentCrewTrace** — secondary timeline of role-agent steps with statuses,
  deterministic cores, artifacts
- **BudgetCard** — budget basis, realism warnings, lines, category rollups,
  tier pills, headroom, variance
- **RunOfShowCard** — ordered tasks, critical path, anchor highlighting
- **ApprovalInbox** — event-scoped approvals auto-expanded when pending;
  structural gate banner and mutation error/status feedback
- **SecurityBeat** — 3 scripted fixtures, blocked actions, no-execution status
- **ScopeCard** — add/edit/delete/toggle/retier scope items with recompute
  feedback
- **RiskCard** — risk/gap flags
- **VendorsCard** — frontend-session vendor draft rows with local-only copy;
  no backend vendor persistence or outreach claim
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

241 tests: budget engine, CPM scheduler, agents, API, security action-gate,
injection flag, audit log, MCP server, FX rates, default demo contract, P6F
security demo, P7B scope mutation and orchestrator proposals, P7D constraint
override semantics, budget realism warnings, and P7D-FIX recompute/provenance
regressions. 9 Gherkin eval
cases under `tests/eval_cases/`.

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

Honesty boundaries: this is a capstone prototype. Production auth, Firestore,
Telegram, OCR, and calendar write-back are **not implemented**. Live model calls
are optional and limited to the configured provider seam.

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
| Model-routing seam | Reason/formatter split plus optional Gemini/OpenAI-compatible live provider routing |

## Safety Rules

- **No secrets in code.** Ever. `.env*` is gitignored.
- **No force-push.** Ever.
- **Stage explicitly.** Never `git add -A`.
- **`main` stays green.** Branch per phase -> QA gate -> merge --no-ff -> push.

## License

CC-BY-4.0. See `LICENSE`.
