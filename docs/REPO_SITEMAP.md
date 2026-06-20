# REPO_SITEMAP.md -- Event Producer Folder Map

> This file describes the **intended** repository layout. The application is not yet built; this map serves as the canonical reference for where every class of artifact belongs.

---

## Root-Level Files

| File | Purpose |
|---|---|
| `README.md` | Front door -- project overview, setup instructions, quickstart |
| `CLAUDE.md` | Persistent instructions for AI coding agents working in this repo |
| `CHANGELOG.md` | Top-level changelog following the Keep-a-Changelog convention |
| `LICENSE` | CC-BY-4.0 license |
| `.gitignore` | Secrets-first ignore rules (see Gitignored section below) |

---

## Folder-by-Folder Breakdown

### `docs/`
Long-form documentation that does not belong in code-level docstrings. Currently holds this sitemap. Add architecture decision records (ADRs), runbooks, and integration guides here as the project matures.

### `changelogs/`
Per-phase detailed change logs that feed into the top-level `CHANGELOG.md`. Each phase (P0, P1, ...) gets its own file or subdirectory. This keeps the root changelog readable while preserving granular history.

### `project_documents/` *(GITIGNORED)*
Handover briefs, spec copies, and other working documents that should not be committed to version control. Subdirectory `handover-briefs/` is the default landing zone for phase-transition documents.

> **This entire directory is gitignored.** Do not commit files from here.

### `temp/` *(GITIGNORED)*
Scratch space for experiments, one-off scripts, and transient artifacts. Safe to delete at any time.

> **This entire directory is gitignored.** Do not commit files from here.

### `event_producer/` -- Main Python Package (ADK Backend)

The core application code. Organized by architectural layer:

#### `event_producer/__init__.py`
Package marker. Exports top-level symbols if needed.

#### `event_producer/main.py`
ADK application entry point. Wires agents, engines, and providers into a runnable app. This is the file the deployment target invokes.

#### `event_producer/agents/`
Role-based agents plus reasoner/formatter splits. Each agent file owns a single responsibility:

| File | Agent Role |
|---|---|
| `orchestrator.py` | Top-level coordinator; routes work to specialist agents |
| `brief_scope.py` | Parses and validates incoming event briefs |
| `budget_manager.py` | Owns budget allocation decisions (delegates math to Budget Engine) |
| `production_manager.py` | Manages production timeline and deliverables |
| `vendor_coordinator.py` | Handles vendor selection and communication |
| `risk_flagger.py` | Identifies and surfaces risks across all domains |

#### `event_producer/engines/`
Deterministic, pure-Python cores with no external dependencies. These are the "math" layer -- fully testable in isolation.

| File | Engine |
|---|---|
| `budget.py` | Budget allocation, tracking, and variance calculations |
| `scheduler.py` | Run-of-show CPM scheduler; produces time-coded production schedules |

#### `event_producer/models/`
Pydantic schemas shared across the codebase. Single file `schemas.py` for now; split into submodules only when the surface area demands it.

#### `event_producer/security/`
Action-gate enforcement, prompt-injection flagging, and audit logging. These modules form the trust boundary for all agent actions.

| File | Responsibility |
|---|---|
| `action_gate.py` | Gate checks before any side-effecting operation |
| `injection_flag.py` | Heuristic and model-based injection detection |
| `audit_log.py` | Immutable append-only audit trail for all gated actions |

#### `event_producer/providers/` -- Moat-Seam Boundary
Abstract interfaces that define the **seam** between the agent layer and external systems. See the Moat-Seam Boundary section below for the full explanation.

| File | Interface |
|---|---|
| `event_store.py` | Persistence for event data (CRUD contract) |
| `rate_card.py` | Vendor rate lookup and caching |
| `vendor_sourcer.py` | Vendor discovery and qualification |

#### `event_producer/mcp/`
MCP (Model Context Protocol) server implementation. Exposes agent capabilities as MCP tools for external consumers.

| File | Purpose |
|---|---|
| `server.py` | MCP server entry point and tool registration |

#### `event_producer/webhook/`
Optional webhook relays. Currently scoped to Telegram.

| File | Purpose |
|---|---|
| `telegram.py` | Telegram bot relay for notifications and commands (if-time deliverable) |

---

### `web/` -- Next.js Frontend

Browser-based UI for the event producer system.

| Path | Purpose |
|---|---|
| `web/package.json` | Node dependencies and scripts |
| `web/pages/` | Next.js page components (file-system routing) |
| `web/components/` | Shared UI components |
| `web/public/` | Static assets (images, fonts, etc.) |

---

### `tests/` -- Eval Framework and Test Suite

All test code lives here, mirroring the package structure where practical.

| File | Coverage |
|---|---|
| `test_budget_engine.py` | Deterministic budget engine unit tests |
| `test_scheduler.py` | CPM scheduler unit tests |
| `test_security.py` | Action-gate, injection flag, and audit log tests |
| `eval_cases/` | Red-team eval set written in Gherkin (`*.feature` files) |

---

### `deploy/` -- Cloud Run and Firebase Configuration

Infrastructure-as-code for deployment targets.

| File | Purpose |
|---|---|
| `Dockerfile` | Container image definition for Cloud Run |
| `cloudbuild.yaml` | Google Cloud Build pipeline config |
| `firebase.json` | Firebase Hosting config (serves the Next.js frontend) |

---

## Moat-Seam Boundary

The `event_producer/providers/` directory defines the **moat-seam boundary** -- the architectural line that separates the agent/reasoning layer from all external I/O.

**How it works:**

1. Each provider file contains an **abstract interface** (Python ABC or Protocol class) that defines a contract: method signatures, input/output types, and error semantics.
2. The agent layer (`event_producer/agents/`) imports and depends **only** on these abstract interfaces. Agents never import concrete implementations directly.
3. Concrete implementations (e.g., FirestoreEventStore, SheetsRateCard) are injected at the composition root (`event_producer/main.py`) or via a factory.
4. This seam makes it possible to:
   - Swap backends without touching agent code (e.g., replace Firestore with PostgreSQL).
   - Test agents in-memory with fake providers.
   - Deploy to different environments with different provider configs.

**Rule:** If a module outside `providers/` imports a concrete external SDK (Firestore client, Google Sheets API, HTTP library), the abstraction has leaked. Fix it by pushing the dependency behind a provider interface.

---

## High-Risk Files -- Do Not Edit Casually

These files have outsized blast radius. Changes here can cascade across the entire system. Always review impact and run the full test suite before committing.

| # | File | Why It Is High-Risk |
|---|---|---|
| 1 | `event_producer/main.py` | Composition root. Changing wiring or initialization order can break every agent and provider binding. |
| 2 | `event_producer/models/schemas.py` | Shared Pydantic schemas. A field rename or type change propagates to every agent, engine, and provider that consumes the model. |
| 3 | `event_producer/providers/*.py` (all) | Moat-seam interfaces. Changing a method signature requires updating every concrete implementation and every agent that calls it. |
| 4 | `event_producer/security/action_gate.py` | Trust boundary enforcement. A logic error here can either block legitimate actions or allow unauthorized ones. |
| 5 | `event_producer/engines/budget.py` | Deterministic financial core. Silent rounding or allocation errors compound across an entire event budget. |
| 6 | `event_producer/agents/orchestrator.py` | Top-level routing agent. A routing change can starve specialist agents or create circular delegation loops. |
| 7 | `deploy/Dockerfile` | Production container definition. A broken layer or missing dependency takes down the entire deployed service. |
| 8 | `.gitignore` | Secrets-first policy. Accidentally un-ignoring a pattern can expose credentials or large binaries to version control. |

---

*Last updated: 2026-06-21*
