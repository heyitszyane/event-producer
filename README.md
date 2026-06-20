# Event Producer

> The AI production crew that lets one person run the whole event.

## Status

**Phase 0 — Scaffold** · Branch: `main` · [CHANGELOG](CHANGELOG.md)

## Architecture at a Glance

ADK multi-agent (Python) on Cloud Run · Gemini 2.5 Flash (+ Flash-Lite for formatters) · Firestore · Next.js on Firebase Hosting · MCP wrapper over event-store · Telegram (scripted) · typed Pydantic JSON contracts.

## Pinned Stack

| Layer | Choice | Version |
|-------|--------|---------|
| Agent framework | Google ADK (Python) | _(pin in P1)_ |
| LLM | Gemini 2.5 Flash | _(pin in P1)_ |
| State store | Firestore | _(pin in P1)_ |
| Backend host | Cloud Run | _(pin in P1)_ |
| Frontend | Next.js on Firebase Hosting | _(pin in P1)_ |

## Setup & Run

_(Filled in P1 — see CHANGELOG.md)_

## QA Commands

_(Filled in P1 — the QA gate: typecheck + lint + tests/eval + build)_

## Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `GOOGLE_CLOUD_PROJECT` | GCP project ID | Yes |
| `GEMINI_API_KEY` | Gemini API key | Yes |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token | If-time |

> **Secrets rule:** Never commit `.env*`, `*.key`, or service-account JSON. These are gitignored.

## Running the Agent Crew

The agent crew can be invoked via the CLI:

```bash
python -m event_producer.main
```

This runs a sample networking event through the full pipeline:
1. **Brief/Scope** — parses the brief and proposes scope items
2. **Budget** — computes a reconciled budget with tier gating
3. **Production** — generates a run-of-show schedule via CPM
4. **Risk** — flags budget, schedule, vendor, and security risks
5. **Vendor** — drafts vendor RFPs (with action-gate enforcement)
6. **Compose** — assembles a complete RunOfShow

### Eval Cases

Eval cases are written in Gherkin format under `tests/eval_cases/`:

- `orchestrator.feature` — Orchestrator routing and gate enforcement
- `brief_scope.feature` — Brief parsing and scope proposal
- `budget_manager.feature` — Budget computation and tier gating
- `production_manager.feature` — CPM scheduling and conflict detection
- `vendor_coordinator.feature` — Vendor coordination and security
- `risk_flagger.feature` — Risk and gap detection
- `security.feature` — Action-gate, injection flag, and audit log

### Architecture

```
event_producer/
├── agents/          # Role agents + reason→formatter splits
├── engines/         # Deterministic cores (budget, scheduler)
├── models/          # Pydantic schemas
├── providers/       # Moat-seam interfaces
├── security/        # Action-gate, injection flag, audit log
├── mcp/             # MCP wrapper over event-store
└── main.py          # ADK composition root
```

The Budget Engine and Scheduler are **plain Python called from code** — never registered as LLM tools. Agents that both reason and emit typed JSON use a **reason→formatter split** to maintain this boundary.

## Repo Map

See [docs/REPO_SITEMAP.md](docs/REPO_SITEMAP.md) for the full folder-by-folder breakdown.

## Concepts We Use

This capstone demonstrates these course concepts:

| Concept | Where |
|---------|-------|
| Multi-agent ADK | `event_producer/agents/` — role agents + reason→formatter splits |
| Agent skills | Each role ships as a reusable ADK skill |
| Security / context hygiene | `event_producer/security/` — structural action-gate + injection flag |
| Deployment | Cloud Run + Firebase Hosting |
| MCP | `event_producer/mcp/` — wrapper over event-store + free source |
| Eval framework | `tests/` — EDD, Gherkin, trajectory scoring, pass-to-the-K |

## Safety Rules

- **No secrets in code.** Ever. `.env*` is gitignored.
- **No force-push.** Ever.
- **Stage explicitly.** Never `git add -A`.
- **`main` stays green.** Branch per phase → QA gate → merge --no-ff → tag → push.
