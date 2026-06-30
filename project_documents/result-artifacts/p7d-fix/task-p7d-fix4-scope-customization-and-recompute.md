# P7D-FIX Task 4 — Scope Customization and Recompute

## What Changed

- Rebuilt `ScopeCard` to support add, edit, delete, toggle selected, and retier flows.
- Add/edit forms include name, category, tier, quantity, unit cost, and selected state.
- Scope mutation responses now include `recompute_notice` with previous headroom, current headroom, schedule status, and human-readable message.
- Frontend applies full mutation payloads: scope, budget, schedule, call sheet, and recompute notice.
- Proposal apply uses the same recompute feedback path.
- Budget manager now budgets selected items when selection is present, while preserving legacy all-unselected fixture behavior.

## Tests

- Rewrote `tests/test_p7d_scope_customization.py` around HTTP endpoints.
- Coverage includes add, edit quantity/cost, delete, toggle, retier, proposal apply, preserved budget basis, preserved contingency, and recompute notices.
