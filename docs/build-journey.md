# Event Producer Build Journey

## Starting point

Event Producer began as a capstone attempt to demonstrate agentic event
production: a system that could take an event brief and produce scope, budget,
schedule, vendor copy, and approval gates.

The initial risk was breadth. A large dashboard can look impressive while
hiding a weak state model. The project therefore shifted toward a stricter
question: can the app preserve event truth as the brief changes?

## Key product correction: state truth

The defining reset was the realization that the product could appear to work
while showing contradictory event facts. For example, a user might change the
event to 100 pax while fallback/default state still showed 50 pax elsewhere.

That is not visual polish. It is a trust failure.

The correction was to make Event Producer a saved casefile system:

- critical fields are dedicated inputs;
- the casefile saves before agent generation;
- structured fields override brief extraction;
- conflicts are visible;
- missing values remain missing;
- agent outputs persist as artifacts;
- every screen renders from the same resolved state.

## Major implementation stages

| Stage | Contribution |
|---|---|
| State truth and local casefiles | File-backed casefile store, index, timeline, artifacts, resolved state precedence, 100-pax regression tests. |
| Requirements and guidance | Requirements confirmation, missing/conflict notices, Next Best Step. |
| Direct specialist agents | Creative Concept, Scope Strategy, Vendor Copy, and Risk Review actions over saved casefile context. |
| Vendor copy artifacts | Editable, saveable, copyable vendor drafts; no fake send semantics. |
| Run persistence and UX hardening | Run snapshots, casefile dropdown, restored saved artifacts, clearer route surfaces. |
| Mission Control and skill cards | Runtime-loaded skill-card registry, role-card UI, direct actions, contract tests. |
| Vendor Notebook | Persistent per-vendor chase list, drafts, logs, statuses, injection-screened replies, vendor-scoped prompt context. |
| Post-polish corrections | Currency truth, intelligent scope quantities, sane run-sheet timing, seeded demo casefiles, clearer budget behavior. |

## Agentic engineering lessons applied

1. The harness matters more than raw model output.
2. The context window is not a database.
3. Agents should not own arithmetic or schedule invariants.
4. Human approval should be structural, not prompt-based.
5. Vendor-supplied text is data, not instruction.
6. Saved artifacts are better than disappearing chat responses.
7. Documentation must distinguish implemented behavior, demo seams, and deferred work.

## Final positioning

Event Producer is not a fake autonomous planner. It is an agent-assisted
production workspace for a solo producer. It demonstrates how specialist
agents, deterministic engines, saved casefiles, and human approval gates can
work together without sacrificing operational control.
