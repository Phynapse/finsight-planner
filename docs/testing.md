# Testing

## Commands

```bash
cd backend && python -m pytest -v        # all backend tests (no network / LLM credits)
cd frontend && npm run build             # tsc type check + Vite production build
```

## Suites

| File | Coverage |
|---|---|
| unit/test_calculations.py, test_variance.py, test_cash_flow.py | Box 1 baseline formulas (kept) |
| unit/test_financial_model.py | income statement, negative OI, zero revenue, missing lines, variance %, favourability, margin pp, bridge reconciliation and discrepancy exposure, matched-record comparison, no-overlap, no double counting |
| unit/test_scenarios.py | hand-verified baseline, revenue/collection/growth/multi assumptions, invalid assumptions, isolation, immutability, determinism, zero denominators, sensitivity, presets on real data |
| unit/test_forecast_cash_drivers.py | baseline inputs from real data, projection periods/values, monthly cash reconciliation and continuity, outflow signs, source cash discrepancies, driver relationships, missing drivers |
| unit/test_ai_evidence.py | deterministic fallback, unsupported questions, invalid plans/filters, evidence scope/assumptions/validation, numeric grounding, fake-LLM plan + explanation, ungrounded rejection, provider timeout/malformed/error handling, what-if parsing |
| integration/test_api.py | Box 1 smoke tests (kept) |
| integration/test_workflows.py | HTTP workflows: health, datasets, summary, variance, scenarios CRUD/compare, sensitivity, forecast, cash, analysis + evidence, questions, error codes |
| integration/test_data_reconciliation.py | data-wide: no duplicates, known issues reported, statements reconcile for every unit/period/source, rollups consistent, all bridges reconcile, historical vs forecast periods distinct |

Small hand-verifiable fixtures (`tests/conftest.py::tiny_inputs`) are used alongside the full dataset so expected values
are not copied from the implementation.

## Verification run (2026-11-02)

- Baseline before changes: 19 passed (16 unit + 3 integration); frontend build succeeded.
- After Box 2: `python -m pytest` → **96 passed**, 0 failed, 0 skipped (2 deprecation warnings).
- `npm run build` → tsc passed, Vite build succeeded (chunk-size warning only, from recharts).
- Live API smoke test (uvicorn on :8000): health, datasets, summary, variance (bridge reconciled), scenario creation
  (COGS +2pp → OI −414,043), baseline unchanged after creation, downside comparison, forecast, cash flow (projection
  reconciled; 1/26 source rows reconcile), question answered with evidence via deterministic fallback, and 422/404
  responses for invalid input — all verified by real HTTP requests.

## Limitations

No live LLM tests; no frontend unit/E2E tests; UI behaviour verified via type check, build and API contracts.
