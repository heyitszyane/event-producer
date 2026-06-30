# P7D-FIX Task 0 — Baseline and Public State

## Branch / Commit

- Starting branch: `feat/p7d-interactive-agentic-demo-surface-rescue`
- Starting commit: `ce9f58faf19cae26f1ff31ff2de861ea3e63ad27`
- Fix branch: `fix/p7d-constraint-provenance-and-demo-surface`
- Local `origin/main`: `e914760b444fc5448c80b685ba4c438315248038`
- Public `origin/main` from `git ls-remote origin main`: `e914760b444fc5448c80b685ba4c438315248038`

## P7D Commit Location

- `ce9f58f` is present on local branch `feat/p7d-interactive-agentic-demo-surface-rescue`.
- `origin/main` is still at P7C (`e914760`), so the fix branch was correctly based on the local P7D rescue branch rather than pre-P7D `main`.

## Baseline QA

- `python -m pytest tests/ -v`: PASS, `222 passed, 1 warning`
- `python -m ruff check .`: FAIL at baseline
  - unused imports in `tests/test_p7d_constraint_overrides.py`
  - unused imports/variable and `== False` comparison in `tests/test_p7d_scope_customization.py`
- `python -m mypy event_producer`: PASS
- `pnpm -C web install --frozen-lockfile`: PASS
- `pnpm -C web run build`: PASS
  - build warning: Google font stylesheet could not be downloaded in the sandbox
  - build warning: static export disables API routes/middleware
- `git diff --check`: PASS

## Docs / Public State

- `README.md` already mentions P7D and 222 tests locally.
- `CHANGELOG.md` contains a P7D entry.
- `docs/REPO_SITEMAP.md` still says last updated P7C, so it is stale.
- Public `main` is confirmed stale relative to P7D/P7D-FIX because it points to P7C.

## Screenshot State

- `project_documents/result-artifacts/p7d-fix/screenshots/` was created for this fix pass.
- No P7D-FIX screenshots existed at baseline.

## Implementation Base Chosen

The implementation base is `ce9f58f` on local branch `feat/p7d-interactive-agentic-demo-surface-rescue`, with a new fix branch created at the same commit: `fix/p7d-constraint-provenance-and-demo-surface`.
