# Event Producer

> The AI production crew that lets one person run the whole event.

## Status

**P5A Audit-Fix Pass -- Capstone Ready** · Branch: `main` · [CHANGELOG](CHANGELOG.md)

119 tests passing. Budget Engine and CPM Scheduler are deterministic, pure-Python,
Decimal-based cores. Security action-gate is structural (enforced in code, not
prompts). HITL approval flow is wired end-to-end through the EventStore provider
seam. Frontend dashboard is a Next.js static export on Firebase Hosting with a
FastAPI backend on Cloud Run.

## Architecture at a Glance

ADK-style multi-agent (Python) on Cloud Run · Rule-based agents with
reason->formatter splits · Firebase Hosting (Next.js static export) · MCP wrapper
over event-store (honest CRUD via provider seam) · Typed Pydantic JSON contracts
· In-memory EventStore (Firestore deferred).

## Pinned Stack

| Layer | Choice | Version |
|-------|--------|---------|
| Agent framework | Python multi-agent (reason->formatter splits) | N/A (rule-based demo) |
| LLM | Gemini 2.5 Flash | Deferred (rule-based agents) |
| State store | In-memory (Firestore deferred) | N/A |
| Backend host | Cloud Run (FastAPI + uvicorn) | fastapi==0.138.0, uvicorn==0.49.0 |
| Frontend | Next.js 14 on Firebase Hosting | next@14.2.0, react@^18.2.0 |
| Validation | Pydantic | pydantic==2.13.4 |
| Linter | Ruff | ruff==0.15.18 |
| Type checker | mypy | mypy==2.1.0 |

## Local Run Instructions

```bash
# Backend
pip install -r requirements.txt
python3 -m pytest                # run test suite (119 tests)
python3 -m event_producer.main   # run demo pipeline locally

# API server
pip install -r requirements.txt
uvicorn event_producer.api:create_app --factory --port 8080

# Frontend
cd web
npm install
npm run build                     # static export to web/out/
```

For the frontend to reach the backend, set the environment variable:

```bash
export NEXT_PUBLIC_API_BASE_URL=http://localhost:8080
```

## Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `ALLOWED_ORIGINS` | CORS allowed origins (comma-separated) | No (defaults to `http://localhost:3000,http://localhost:8080`) |
| `NEXT_PUBLIC_API_BASE_URL` | Frontend API base URL | For frontend build |

> **Secrets rule:** Never commit `.env*`, `*.key`, or service-account JSON. These are gitignored.

## Implemented / Scripted / Deferred

### Implemented

- **Budget Engine** -- Pure Python, Decimal arithmetic, deterministic. Budget
  reconciles to zero. Tier-gating (must/should/could/wow). Multi-currency with
  line-total-first FX rounding. Receipt variance aggregation. 30+ tests.
- **CPM Scheduler** -- Pure Python, deterministic. Dependency resolution,
  lead-time validation, anchor constraints, cycle detection. Conflict reporting
  for missing dependencies, duplicate IDs, lead-time violations, anchor
  violations, and cycles. 25+ tests.
- **Agent crew** -- Role agents (brief/scope, budget manager, production
  manager, vendor coordinator, risk flagger, orchestrator) with reason->formatter
  splits. Rule-based demo (not live Gemini). 15+ tests.
- **Security action-gate** -- Structural enforcement via `enforce()` function.
  Financial/state-changing actions require human Approval. Tested end-to-end.
- **REST API** -- FastAPI with `/run`, `/event/{id}`, `/approvals`,
  `/approvals/{id}`, `/chat`, `/healthz` endpoints. HITL approval flow with
  action-gate integration. CORS driven by environment variable. Consistent error
  envelope. 25+ tests.
- **Frontend dashboard** -- Next.js 14 static export on Firebase Hosting.
  Approval inbox, budget summary, run-of-show, vendor cards, risk flags, conflict
  report rendering. Direct backend calls via `NEXT_PUBLIC_API_BASE_URL`.
- **MCP event-store wrapper** -- Honest CRUD/list/delete via the EventStore
  provider ABC. No private introspection hacks.

### Scripted

- **Telegram security beat** -- No live bot. Structural boundary code exists.
- **Vendor messages** -- Simulated. Approval-gated send demonstrated in tests.
- **Agent reasoning** -- Rule-based, not live Gemini. Agents produce structured
  output via deterministic logic.
- **Demo seed data** -- `scripts/seed_demo.py` runs the networking event
  pipeline against a running API server.

### Deferred

- Firestore (in-memory only)
- Live Gemini / ADK integration
- Live Telegram relay
- Auth / multi-user
- Receipt OCR
- Live FX feed
- Calendar write-back
- Full budget configurator/toggle UX
- Sponsor/guest/post-event systems

## Running the Agent Crew

The agent crew can be invoked via the CLI:

```bash
python -m event_producer.main
```

This runs a sample networking event through the full pipeline:
1. **Brief/Scope** -- parses the brief and proposes scope items
2. **Budget** -- computes a reconciled budget with tier gating
3. **Production** -- generates a run-of-show schedule via CPM
4. **Risk** -- flags budget, schedule, vendor, and security risks
5. **Vendor** -- drafts vendor RFPs (with action-gate enforcement)
6. **Compose** -- assembles a complete RunOfShow

Or via the REST API:

```bash
curl -X POST http://localhost:8080/run \
  -H "Content-Type: application/json" \
  -H "X-Demo-User: user" \
  -d '{
    "brief": "Corporate networking event",
    "budget_cap": "10000",
    "contingency_pct": "10",
    "attendees": 100,
    "event_type": "corporate",
    "venue_type": "indoor",
    "date": "2026-07-15"
  }'
```

## Eval Cases

Eval cases are written in Gherkin format under `tests/eval_cases/`:

- `orchestrator.feature` -- Orchestrator routing and gate enforcement
- `brief_scope.feature` -- Brief parsing and scope proposal
- `budget_manager.feature` -- Budget computation and tier gating
- `production_manager.feature` -- CPM scheduling and conflict detection
- `vendor_coordinator.feature` -- Vendor coordination and security
- `risk_flagger.feature` -- Risk and gap detection
- `security.feature` -- Action-gate, injection flag, and audit log

## Project Structure

```
event_producer/
├── agents/          # Role agents + reason->formatter splits
├── engines/         # Deterministic cores (budget, scheduler)
├── models/          # Pydantic schemas
├── providers/       # Moat-seam interfaces (abstract)
├── security/        # Action-gate, injection flag, audit log
├── mcp/             # MCP wrapper over event-store (honest CRUD)
└── main.py          # Composition root + InMemoryEventStore
```

The Budget Engine and Scheduler are **plain Python called from code** -- never
registered as LLM tools. Agents that both reason and emit typed JSON use a
**reason->formatter split** to maintain this boundary.

## Repo Map

See [docs/REPO_SITEMAP.md](docs/REPO_SITEMAP.md) for the full folder-by-folder
breakdown.

## Concepts Demonstrated

| Concept | Where |
|---------|-------|
| Multi-agent ADK | `event_producer/agents/` -- role agents + reason->formatter splits |
| Agent skills | Each role ships as a reusable ADK skill |
| Security / context hygiene | `event_producer/security/` -- structural action-gate + injection flag |
| Deployment | Cloud Run + Firebase Hosting |
| MCP | `event_producer/mcp/` -- wrapper over event-store via provider seam |
| Eval framework | `tests/` -- EDD, Gherkin, trajectory scoring |
| Separated evaluation | Build itself runs planner->generator->evaluator |
| Model routing | Flash-Lite for formatters, Flash for reasoning |

## QA Commands

| Gate | Command |
|------|---------|
| Tests | `python3 -m pytest` |
| Lint | `python3 -m ruff check .` |
| Type check | `python3 -m mypy event_producer` |
| Frontend build | `cd web && npm run build` |

## Safety Rules

- **No secrets in code.** Ever. `.env*` is gitignored.
- **No force-push.** Ever.
- **Stage explicitly.** Never `git add -A`.
- **`main` stays green.** Branch per phase -> QA gate -> merge --no-ff -> tag -> push.
