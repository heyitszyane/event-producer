# Event Producer

> **Submission note:** Kaggle does not require a live public endpoint for judging. A public GitHub repository with complete setup instructions is acceptable. If the hosted demo is unstable, use the repo as the primary project link and treat deployment documentation/video proof as the deployability evidence.


**An AI production crew for working event casefiles.**

Event Producer is a Kaggle x Google AI Agents capstone project for **Agents for Business**. It helps a solo event producer turn an event brief into a saved, costed, scheduled, approval-gated working casefile.

The product is not a generic event-planning chatbot. It is a production-control workspace where:

- structured event facts are saved as casefile truth;
- specialist agents propose concepts, scope tradeoffs, vendor copy, and risk reviews;
- deterministic engines compute budget and run-sheet logic;
- vendor-facing and state-changing actions remain human-reviewed.

> **Core rule:** agents propose and draft; deterministic engines compute; humans approve consequential action.

---

## Capstone rubric mapping

| Required concept | Where this repo demonstrates it | Notes |
|---|---|---|
| Agent / multi-agent system | `event_producer/agents/`, `event_producer/main.py`, Agent Mission Control UI | Orchestrator plus specialist role agents with direct actions over saved casefile context. |
| MCP server / integration seam | MCP event-store wrapper | Exposes event-store operations through a tool-facing seam. |
| Security features | `event_producer/security/action_gate.py`, Vendor Notebook injection screening | Structural approval wall, no autonomous send/payment mutation, flagged vendor text withheld from prompts. |
| Deployability | `deploy/`, FastAPI backend, static Next.js frontend | Cloud Run backend lane + static frontend export for Firebase Hosting or similar hosting. |
| Agent skills | `event_producer/agents/cards/`, `event_producer/agents/cards.py` | Runtime-loaded skill-card registry drives prompts, UI cards, and contract tests. |
| Antigravity | Video demo | Shown as part of the AI-assisted build process. |

---

## Problem

Event production breaks when facts drift.

A brief may say 50 people, a producer may update the casefile to 100, the budget may still be calculated for 50, and a vendor draft may be written from stale context. A generic LLM can produce confident text while planning the wrong event.

Event Producer is designed to prevent that. User-entered casefile fields win over brief extraction. Conflicts are visible. Missing values stay missing. Defaults do not silently become product truth.

---

## Product loop

1. Start or open an event casefile.
2. Enter event basics: title, country, city, currency, budget cap, contingency percentage, dates, expected turnout, and event type.
3. Add event notes / brief as supporting context.
4. Save and generate a first pass.
5. Confirm requirements and resolve visible conflicts.
6. Ask specialist agents for creative concepts, scope strategy, vendor copy, and risk review.
7. Review deterministic budget and run-sheet outputs.
8. Manage vendors through draft-only copy, manual-send tracking, logs, and approval gates.
9. Reopen the casefile later with artifacts and timeline intact.

---

## Architecture

```text
Browser / Next.js Paper War Room
  ├─ Casefile selector + New Event
  ├─ Event Basics + Event Brief
  ├─ Requirements confirmation + Next Best Step
  ├─ Agent Mission Control
  │   ├─ AI Producer / Orchestrator
  │   ├─ Creative Concept Agent
  │   ├─ Scope Strategy Agent
  │   ├─ Vendor Copy Agent
  │   └─ Risk Review Agent
  ├─ Scope, Budget, Run Sheet
  ├─ Vendor Notebook
  ├─ Approvals
  └─ Audit / Diagnostics

FastAPI backend
  ├─ LocalCasefileStore (.local_state/event_producer/events)
  ├─ Agent skill-card registry
  ├─ Live model provider seam + fallback mode
  ├─ Specialist role agents
  ├─ Deterministic Budget Engine
  ├─ Deterministic Run Sheet / CPM Scheduler
  ├─ Vendor Notebook store
  └─ Structural approval/action gate
```

The backend is FastAPI with typed Pydantic contracts. The frontend is a Next.js static export. Live-capable agents call the configured provider when available; deterministic fallback is used for no-key clone setups and is labeled as degraded/resilience mode.

Budget and schedule invariants are owned by Python code, not free-text model output.

For a deeper structural walkthrough, see [docs/architecture.md](docs/architecture.md).

---

## Source-of-truth model

Casefiles are saved locally under:

```text
.local_state/event_producer/events/<event_id>/
```

Each casefile can contain:

```text
casefile.json
timeline.jsonl
artifacts/
  brief-intake.json
  creative-concept.json
  scope-strategy.json
  budget-summary.json
  run-sheet.json
  vendor-copy.json
  vendor-notebook.json
  risk-review.json
  run-snapshot.json
```

Resolved event state follows this precedence:

1. User-entered structured fields.
2. User-edited saved casefile values.
3. AI-extracted values from event notes only when the structured field is blank.
4. Explicit missing/unknown state.
5. Seeded demo defaults only inside seeded demos, never as hidden product truth.

Example: if the event notes mention 50 pax but the saved casefile says 100 pax, the system uses 100 and records a conflict notice.

---

## Agent crew

The crew includes:

| Component | Role |
|---|---|
| AI Producer / Orchestrator | Routes broad user requests and returns typed proposals. |
| Brief Intake / Requirements Agent | Extracts context and reconciles it against saved event basics. |
| Creative Concept Agent | Generates experience directions, titles, and creative ideas. |
| Scope Strategy Agent | Recommends additions, cuts, reductions, and tiering tradeoffs. |
| Vendor Copy Agent | Drafts editable vendor copy from selected-vendor context. |
| Risk Review Agent | Flags operational gaps, budget pressure, schedule risks, and vendor chase items. |
| Budget Engine | Deterministically computes spend, contingency, headroom, and rollups. |
| Run Sheet Engine | Deterministically computes day-of flow and scheduling logic. |
| Approval Wall | Blocks gated external/state-changing actions without human approval. |

The LLM-facing agents use a runtime-loaded skill-card registry. Each card contains a contract and instruction body. The same registry is served through `GET /agents`, rendered in Agent Mission Control, and appended into live agent system prompts.

---

## Vendor Notebook and safety model

The Vendor Notebook is a per-casefile chase list. Each vendor can have:

- profile and category;
- workflow status;
- payment planning fields;
- current draft;
- append-only activity log;
- injection-screened vendor replies.

The app does **not** send vendor messages and does **not** move money. It drafts copy, records manual workflow status, and keeps humans in the loop.

Security controls:

- vendor-supplied replies are treated as untrusted data;
- suspicious replies are flagged on entry;
- flagged vendor text is withheld from later agent prompts;
- gated actions such as `send_vendor_message`, `change_payment_details`, `mark_paid`, `change_scope`, `approve_budget`, `lock_scope`, and `release_funds` require a valid human-approved approval object.

---

## Run locally

### One-command local dev harness

```bash
./scripts/dev.sh
```

Then open the frontend and use **Settings** to choose a model provider or run in fallback mode.

### Manual backend

```bash
python3 -m uvicorn event_producer.main:create_app --factory --host 127.0.0.1 --port 8080 --reload
```

### Manual frontend

```bash
pnpm -C web install --frozen-lockfile
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8080 pnpm -C web run dev
```

The browser API calls require the demo header used by the frontend harness. For direct API testing, include:

```text
X-Demo-User: demo-user
```

---

## Optional live model configuration

Fallback mode works without keys. For live provider mode, copy `.env.example` to `.env` and configure a provider.

Important environment variables:

| Variable | Purpose |
|---|---|
| `ENABLE_LIVE_MODEL` | Enables live model calls when set to `true`. |
| `MODEL_PROVIDER` | `gemini`, `openrouter`, `openai_compatible`, `local`, `ollama`, or `lmstudio`. |
| `GEMINI_API_KEY` / `GOOGLE_API_KEY` | Gemini credentials. |
| `OPENROUTER_API_KEY` | OpenRouter credentials. |
| `OPENAI_COMPATIBLE_API_BASE_URL` | Hosted OpenAI-compatible endpoint. |
| `LOCAL_LLM_API_BASE_URL` | Local model endpoint for LM Studio/Ollama/local servers. |
| `NEXT_PUBLIC_API_BASE_URL` | Frontend API base URL for build/runtime. |
| `EVENT_PRODUCER_CASEFILE_ROOT` | Optional override for local casefile storage root. |
| `CASEFILE_STORE` | `local` by default; set to `firestore` for hosted Cloud Run demos. |
| `EVENT_PRODUCER_FIRESTORE_COLLECTION` | Optional Firestore owner collection override. |
| `ALLOWED_ORIGINS` | Required for hosted frontend origins calling Cloud Run. |

Secrets rule: do not commit `.env`, API keys, service-account JSON, or local state.

---

## Hosted demo deployment

This repo has a Cloud Run backend lane and a static frontend lane. It does not
prove that your project is already deployed; deployment still requires a Google
Cloud/Firebase project, an authenticated deploy operator, and the required
project services/IAM.

Hosted mode should use Firestore because Cloud Run container filesystems are
ephemeral:

```text
CASEFILE_STORE=firestore
EVENT_PRODUCER_LOAD_DOTENV=false
ALLOWED_ORIGINS=https://<your-frontend-host>
NEXT_PUBLIC_API_BASE_URL=https://<your-cloud-run-service-url>
```

The Cloud Build file expects:

```bash
gcloud builds submit \
  --config deploy/cloudbuild.yaml \
  --substitutions=_NEXT_PUBLIC_API_BASE_URL=https://<cloud-run-url>,_ALLOWED_ORIGINS=https://<frontend-origin>
```

For a first hosted environment where the Cloud Run URL is not known yet, use
`deploy/cloudbuild.backend.yaml` to build the backend image first, deploy Cloud
Run, then rerun the full deploy with the final Cloud Run and frontend origins.

Notes:

- `deploy/cloudbuild.yaml` deploys the backend to Cloud Run and the static
  frontend to Firebase Hosting using the root `firebase.json` Hosting config.
- The Cloud Run service account needs Firestore access if
  `_CASEFILE_STORE=firestore`.
- The frontend sends a browser-local `X-Demo-User` id so hosted demo casefiles
  are scoped per browser session.
- This is demo isolation, not production authentication.

---

## Seed demo casefiles

A fresh clone can materialize committed demo casefiles:

```bash
python3 scripts/seed_demo.py
```

Or click **Seed Demo** in the app.

The seed cases are intended to make the product explorable even when `.local_state/` is empty.

---

## Quality gates

Run before submission or merge:

```bash
git status --short
git diff --check
bash -n scripts/dev.sh
python3 -m pytest tests/ -v
python3 -m ruff check .
python3 -m mypy event_producer
pnpm -C web install --frozen-lockfile
pnpm -C web run lint
pnpm -C web run build
```

Use the latest local QA output as the source of truth for exact test counts.

For the regression model and manual smoke path, see
[docs/evaluation-and-quality.md](docs/evaluation-and-quality.md).

---

## Known limitations

This is a capstone prototype, not production SaaS.

Deferred / not implemented:

- production authentication and multi-user accounts;
- production-grade authenticated tenancy;
- live vendor directory lookup;
- live email, Telegram, or WhatsApp sending;
- autonomous vendor negotiation;
- payment execution;
- receipt OCR;
- live FX feeds;
- calendar writeback;
- full global location database;
- formal ADK runtime / Agents CLI packaging, unless added later.

These are deliberate boundaries. The implemented product demonstrates the core agentic workflow: saved casefiles, specialist agents, deterministic planning engines, draft-only vendor work, and structural safety gates.

See also [docs/security-and-limitations.md](docs/security-and-limitations.md) and
[docs/build-journey.md](docs/build-journey.md).

---

## License

This project is licensed under **CC BY 4.0**.
