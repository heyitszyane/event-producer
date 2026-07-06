# Event Producer Evaluation and Quality

## Quality philosophy

Event Producer treats model output as useful but not authoritative. The system
uses deterministic tests, structural gates, typed contracts, saved artifacts,
and UI smoke checks to prevent three core failure modes:

1. planning the wrong event;
2. presenting fabricated defaults as truth;
3. allowing vendor or payment text to become executable instruction.

## Key regression classes

| Regression class | Expected behavior |
|---|---|
| State truth | If saved casefile turnout is 100, every visible planning surface uses 100. |
| Brief conflict | If event notes mention 50 but saved field says 100, the system records a conflict and uses 100. |
| Missing values | Missing expected turnout/date/budget remains missing, not hidden fallback truth. |
| Currency truth | Casefile currency threads through scope, budget, proposals, and display. |
| Scope accounting | Every selected item counts toward budget headroom; over-budget is allowed and visible. |
| Schedule sanity | Run sheet anchors to event date; vendor booking deadlines are separate from day-of rows. |
| Vendor context isolation | Vendor Copy Agent receives only the selected vendor's relevant context. |
| Injection handling | Flagged vendor reply text is withheld from prompts. |
| Action gating | Gated actions fail unless a valid human-approved Approval object is provided. |
| Skill-card drift | Agent cards that contradict runtime contracts fail tests. |

## Recommended final QA commands

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

Use the final local QA output as the source of truth for exact test counts.

## Manual browser smoke

Before submission, run one full casefile path:

1. Seed demo or create a new event.
2. Save basics with 100 expected turnout and SGD currency.
3. Add event notes that mention 50 people.
4. Save/regenerate.
5. Confirm conflict notice and 100-pax state truth.
6. Ask a direct specialist agent.
7. Check budget headroom and scope totals.
8. Check run sheet date behavior.
9. Draft vendor copy.
10. Copy/mark manually sent.
11. Log a hostile vendor reply.
12. Confirm it is flagged and withheld from prompts.
13. Confirm approval wall blocks gated action without valid approval.

## Evidence to surface publicly

- README concept mapping table.
- Architecture diagram.
- Security/limitations section.
- Video showing state-truth behavior.
- Video showing Antigravity build process.
- Final QA command output if available.

## Evaluation note for judges

This capstone does not rely on the LLM to grade itself. The most important
correctness properties are enforced outside prompts:

- Pydantic contracts for response structure;
- deterministic budget and schedule engines;
- local casefile source precedence;
- structural action gate;
- contract tests for agent cards;
- vendor reply injection screening before prompt assembly.
