# CLAUDE.md — Event Producer

Persistent project instructions for any coding-agent harness working in this
repository. Read this file before every session and follow its rules strictly.

---

## 1. Product Frame

**Event Producer** is an AI production crew — an ADK-style multi-agent system
(rule-based, no live Gemini runtime) — that lets one person run a
brand/experiential event end-to-end. It covers:

- **Budget-gated scope configurator** — the user describes the event, the
  agent proposes scope options constrained by a hard budget.
- **Deterministic Budget Engine + Run-of-Show (CPM) scheduler** — budgets
  reconcile to zero; the schedule respects dependencies and lead times.
- **Secured vendor coordination** — every action that touches vendor
  communication or financial state goes through a human-approval gate.
- **HITL on every approval** — "human in the loop" is the default, not an
  afterthought.

This is a Google x Kaggle 2026 capstone project under **Agents for Business**.

**Honest-claims rule:** all copy in docs, READMEs, comments, and agent-facing
descriptions must match what the code actually does. No aspirational claims.

---

## 2. Operating Rules

These rules apply to every task in this codebase.

1. **Inspect before editing.** Read the relevant code and tests before making
   any change. Do not edit blindly.
2. **Root-cause, not hotfix.** Fix the underlying problem, not the symptom.
   Patches that hide a bug without addressing it will be rejected.
3. **No broad refactors unless asked.** Keep changes scoped to the task.
   Renaming, restructuring, or rewriting unrelated files is out of scope.
4. **Never weaken invariants.** The deterministic-core guarantees (budget
   reconciliation, contingency reservation, scheduler dependency/lead-time
   respect), the action-gate, and HITL requirements must not be softened to
   make a test pass or to unblock delivery.
5. **Never weaken the action-gate or HITL.** The structural action-gate
   (financial/state-changing actions require human approval) is non-negotiable.
6. **Docs-only tasks do not change behavior.** If the task is to document
   something, do not alter any code or test behavior.
7. **QA gate must pass before "done".** Typecheck + lint + tests/eval + build
   must all pass before a task is considered complete.
8. **Write a result artifact.** For any non-trivial task, write a result
   artifact under `project_documents/` summarizing what was done and why.

---

## 3. Build Pattern

This project is built by an agent pipeline:

```
Orchestrator (main)
  -> Planner
  -> Generator
  -> Evaluator
```

Two loops execute:

1. **Planning + Generation loop** — planner designs the approach; generator
   implements it.
2. **Evaluation loop** — evaluator runs independently and judges the output.

**Separated evaluation:** the evaluator is never the same agent that planned
or generated the work. This is intentional and must be preserved.

### Branch workflow

```
Phase branch -> QA gate -> merge --no-ff to main -> tag -> push
```

- Every phase gets a branch.
- QA gate must pass before merge.
- Merge is `--no-ff` (no fast-forward) so the branch history is preserved.
- After merge, tag the merge commit and push.

**The orchestrator never plans, codes, or judges its own work.** Even trivial
tasks are delegated to the planner/generator/evaluator pipeline.

---

## 4. Hard Boundaries

These are structural constraints that must never be violated.

### Deterministic-core invariants

- Budget must reconcile to zero (inflows minus outflows minus contingency).
- Contingency must be reserved before any discretionary spend.
- The scheduler must respect task dependencies and vendor lead times.
- **Never weaken these invariants to pass a test or meet a deadline.**

### Vendor-comms security

- **Structural action-gate:** no financial or state-changing action is executed
  without a human Approval. The gate is enforced in code, not in prompts.
- **Data-not-instruction boundary:** vendor-supplied data is treated as untrusted;
  it is never executed or interpolated into instructions.
- **Audit log:** every vendor interaction is logged immutably.
- The vendor channel **never auto-acts**. Every outbound action requires
  explicit human approval.

### Moat seam (provider isolation)

- Agents call **provider interfaces** (abstractions), never a concrete
  database, calendar, model, or chain directly.
- This seam allows swapping providers without touching agent logic.

### Secrets and force-push

- **Never commit secrets.** This includes `.env*` files, service-account
  JSON, Gemini API keys, Telegram tokens, and any other credential.
- `.env*` is in `.gitignore` — keep it that way.
- **Never force-push** to any branch, especially `main`.
- **Git identity:** `user.name = heyitszyane`, `user.email = zyanetan@gmail.com`
  (set locally in this repo for portfolio credit on heyitszyane's contribution graph).

---

## 5. Commands

### Python

```bash
python3 -m pytest            # run test suite
python3 -m mypy event_producer  # type checking
python3 -m ruff check .      # linting
```

### Node / TypeScript

```bash
pnpm -C web run build      # production build (static export)
pnpm -C web run lint       # linting
```

### QA gate (must pass before "done")

```
typecheck + lint + tests/eval + build
```

All four must pass. A task is not complete until the QA gate is green.

---

## 6. Architecture

The full technology stack:

| Layer | Technology |
|-------|-----------|
| Agent framework | ADK-style multi-agent (rule-based role agents + reason->formatter splits; no live Gemini runtime) |
| LLM | Deferred (rule-based agents; no live Gemini runtime) |
| State + audit log | InMemoryEventStore (Firestore-ready provider seam; Firestore deferred) |
| Backend hosting | Cloud Run |
| Frontend | Next.js on Firebase Hosting |
| Data interface | MCP wrapper over the event-store |
| Messaging | Deferred (scripted vendor-message fixtures; no live Telegram) |
| Contracts | Typed Pydantic JSON |

**Key design decisions:**

- Engines (budget, scheduler) are called from code, not invoked as LLM tools.
- Role agents own a reason step and a formatter step, keeping the LLM call
  focused on one concern.
- The MCP wrapper provides a stable interface over the event-store, decoupling
  agents from the underlying persistence layer.

---

## 7. Course Concepts Demonstrated

| Concept | Where |
|---------|-------|
| ADK-style multi-agent | `agents/` — rule-based role agents + reason->formatter splits (no live ADK runtime) |
| Agent skills | `agents/cards/` — 10 runtime-loaded skill cards (YAML contract + instruction body, versioned, contract-tested) served by `GET /agents`; formal ADK Agent Skills packaging still deferred |
| Security / context hygiene | `security/` — structural action-gate + advisory injection flag |
| Deployment | Cloud Run + Firebase Hosting |
| MCP | `mcp/` — wrapper over event-store via provider seam |
| Eval framework | `tests/` — EDD, Gherkin, trajectory scoring |
| Separated evaluation | Build itself runs planner->generator->evaluator |
| Model-routing seam | Reason/formatter split is represented structurally; live Gemini/Flash routing is deferred |

---

## 8. Documentation System

Three-document system plus working artifacts:

| Artifact | Purpose |
|----------|---------|
| `README.md` | Public-facing project overview |
| `docs/REPO_SITEMAP.md` | Structural map of the codebase |
| `CHANGELOG.md` | High-level release notes |
| `changelogs/` | Detailed per-change entries |
| `project_documents/` | Internal/result artifacts (gitignored) |
| `temp/` | Transient working files (gitignored) |

**Rule:** update the relevant doc in the same task that changes setup,
structure, architecture, or behavior. Internal and raw artifacts, plus
handover briefs, go under `project_documents/` — never in public docs.

---

## 9. Result Artifacts & Handovers

- **Non-trivial tasks** produce a result artifact under `project_documents/`.
  The artifact summarizes what was done, key decisions, and any open
  questions.
- **Every phase boundary** produces a self-contained handover under
  `project_documents/handover-briefs/`.
- The handover template is defined in the build brief section 9.
- Handovers are self-contained: a new agent should be able to pick up the
  project from a handover without reading prior conversations.

### 9a. Subagent Output Visibility (HARD RULE)

Every subagent spawn (planner, generator, evaluator) produces output that must
be saved to disk. The orchestrator's context is ephemeral — saved files are the
only persistent record. Without these files, there is no audit trail, no
debugging history, and no way for the human to see what was decided.

**After every subagent spawn returns**, save its output to:
```
project_documents/result-artifacts/<phase>/subagents/<role>/<description>.md
```

Where:
- `<phase>` = `p0`, `p1`, `p2`, `p3`, etc.
- `<role>` = `planner`, `generator`, `evaluator`
- `<description>` = e.g., `loop1-round1-plan`, `task3-fx-rates`, `task5-verdict`

**What to save:**
- **Planner:** the full plan for each round (including revision notes and what changed)
- **Generator:** summary of what was done, files created, verification results
- **Evaluator:** the full structured verdict (JSON), findings, remediation priorities

**Directory convention:**
```
project_documents/result-artifacts/
└── p1/
    ├── subagents/
    │   ├── planner/     (loop1-round{1..N}-plan.md)
    │   ├── generator/   (task{N}-{name}.md)
    │   └── evaluator/   (loop1-round{N}-verdict.md, task{N}-verdict.md)
    └── p1-budget-engine-complete-20260621.md
```

This is NOT optional. The human cannot see subagent output unless it is saved to
disk. The orchestrator saves subagent output as it arrives — do not wait until
the end of the phase.

---

## 10. High-Risk Files (inspect before editing)

The following files are high-risk. Always read them fully before making any
change. A mistake here can break security, correctness, or deployability.

| File / Area | Risk |
|-------------|------|
| `budget.py` (Budget Engine) | Deterministic-core invariant; budget must reconcile to zero |
| `scheduler.py` (Run-of-Show / CPM) | Deterministic-core invariant; deps + lead time |
| Security / action-gate module | Structural security boundary |
| Provider interfaces | Moat seam; must stay abstract |
| Firestore rules | Data integrity and access control |
| Deploy config | Production deployment safety |
| `.gitignore` | Must keep `.env*` and secrets out of VCS |
| Package manifests | Dependency integrity |

If a task touches any of these, double-check the change against the relevant
invariant or boundary before committing.
