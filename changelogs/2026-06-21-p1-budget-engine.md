# P1 Budget Engine — 2026-06-21

## What Was Done

Implemented the deterministic Budget Engine core (P1) for the Event Producer. This is
the foundational financial computation layer: it reconciles event budgets to zero,
normalizes multi-currency line items to a reporting currency, gates spend by tier
(must/should/could/wow), and tracks variance against ingested receipts.

All monetary arithmetic uses Python `Decimal` — never `float`. This is an invariant,
not a preference.

## Key Decisions

| Decision | Rationale |
|----------|-----------|
| **Decimal-only arithmetic** | Float rounding error is unacceptable in financial computation. All `BudgetLine`, `BudgetSummary`, `BudgetVariance`, and `Receipt` fields are `Decimal`. Pydantic validators reject `float` inputs. |
| **USD-pivot cross-rate FX conversion** | Rates are stored vs USD. Non-USD-to-non-USD conversions cross through the USD pivot (e.g., SGD->THB = (1/USD_SGD) * USD_THB). Simple, auditable, sufficient for 12 currencies. |
| **Greedy tier-gating** | Tiers are evaluated must-first, then should, then could/wow. Spend is included greedily until headroom is exhausted. Deterministic and explainable. |
| **Contingency reserved before any spend** | `contingency_reserve = budget_cap * contingency_pct / 100`. `spendable = budget_cap - contingency_reserve`. This is the first computation — it cannot be bypassed. |
| **Zero-sum by construction** | `budget_cap - contingency_reserve - spendable == 0` and `spendable - included_totals - headroom == 0` are guaranteed by the math, not asserted after the fact. |
| **Static FX provider (seeded)** | Rates are a frozen dict, not a live API call. Deterministic, testable, no external dependency. Swap via the provider interface when live rates are needed. |
| **EDD: eval cases before implementation** | 13 Gherkin scenarios written as acceptance criteria before any engine code. Tests trace back to scenarios. |

## Files Created

| File | Purpose |
|------|---------|
| `event_producer/models/schemas.py` | Pydantic models: `BudgetLine`, `BudgetSummary`, `BudgetVariance`, `Receipt`, `Tier`, `Currency` |
| `event_producer/providers/rate_card.py` | `FXRateProvider` interface + `StaticFXRateProvider` (12 currencies, USD-pivot) |
| `event_producer/engines/budget.py` | `BudgetEngine.compute_budget()` — contingency, FX normalization, tier-gating, rollups, variance |
| `event_producer/__init__.py` | Package init |
| `event_producer/models/__init__.py` | Models package init |
| `event_producer/providers/__init__.py` | Providers package init |
| `event_producer/engines/__init__.py` | Engines package init |
| `tests/eval_cases/budget_engine.feature` | 13 Gherkin scenarios (EDD acceptance criteria) |
| `tests/test_budget_engine.py` | 20 pytest tests for the engine |
| `tests/test_fx_rates.py` | 7 pytest tests for FX rate provider |

## Test Status

- **Total tests**: 27
- **Result**: All 27 passed (0.08s)
- **Breakdown**: 20 budget engine + 7 FX rates
- **Coverage of invariants**: zero-sum reconciliation, contingency reservation, tier-gating, FX normalization, variance computation, Decimal-only contract, edge cases (zero budget, over budget, headroom=0)

## QA Gate

| Check | Result |
|-------|--------|
| `pytest tests/ -v` | 27/27 passed |
| `ruff check event_producer/ tests/` | All checks passed |
| `mypy event_producer/` | No issues found in 7 source files |

## Known Limitations

1. **Static FX rates only** — the `StaticFXRateProvider` uses seeded rates. A live provider (e.g., ECB, Open Exchange Rates) can be swapped in via the `FXRateProvider` interface without touching engine code.
2. **12 currencies supported** — SGD, THB, JPY, EUR, GBP, AUD, CAD, CHF, CNY, INR, MYR, PHP. Add more by extending the seeded dict.
3. **No persistence** — the engine is pure computation. Persistence (Firestore/document store) is a later phase concern, accessed only through the provider/moat seam.
4. **Single reporting currency per call** — you specify one `reporting_currency` per `compute_budget()` call. Multi-currency reporting requires multiple calls.
5. **Greedy tier-gating is simple** — it does not optimize across tiers (e.g., knapsack). It includes must-first, then should, then could/wow until headroom is exhausted. Sufficient for scope gating; not a portfolio optimizer.
