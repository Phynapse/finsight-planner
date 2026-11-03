# Limitations

## Completed in Box 2

Deterministic statements, variances, OI bridge, rollups, YoY; projection model; scenario engine with validated
assumptions and four presets; sensitivity; historical cash reconciliation and cash projection; driver checks;
evidence packages; rule-based + optional LLM interpretation; grounded explanations; five connected UI pages; 96 tests.

## Data

- All data is synthetic (Asteron Group). No real company, ERP or accounting integration.
- Actuals contain 13 sampled months (2024-01 … 2026-09), not a continuous 36-month series; several units report only
  in 2024-01. Trend totals mix differing unit coverage (flagged in the API/UI).
- Budget is sparse; actual-vs-budget uses 61 matched records. Forecast has no period overlap with actuals or budget,
  so actual-vs-forecast and forecast-vs-budget return explicit "no overlap" results.
- 25 of 26 cash-flow rows do not reconcile to their own components; North America 2026-12 has two conflicting rows.
  Reported, not corrected.
- `other_operating_expense` is unreported for Engineering & Product after 2024-02 (disclosed as a missing line).

## Model

- Projections cover only North America Sales & Marketing and Engineering & Product (units with 2026-09 actuals).
- Growth comes from one same-month YoY observation; no seasonality; not statistically validated.
- Baseline collection period of 60 days is a model assumption; payments are assumed in the month incurred;
  capex/debt/other cash held flat. No balance sheet, accruals, tax, interest, FX, free cash flow or DSCR.
- Variance causes (price/volume/timing/efficiency) cannot be established and are never asserted.
- Sensitivity is one-variable deterministic; no probabilistic or Monte Carlo analysis.

## AI

- Rule-based interpretation covers the documented question patterns; phrasing outside them returns "unsupported".
- The OpenAI-compatible provider is tested only with mocks; it was not exercised against a live endpoint.
- Numeric grounding is tolerance-based pattern matching; it cannot verify qualitative claims, which are labelled as
  interpretations.

## Platform

- Scenarios (max 100) and evidence packages (max 200) are in memory and lost on restart.
- No authentication, authorisation, persistence or audit trail. No audit certification; no guarantee of real outcomes.
- No frontend unit-test framework (TypeScript type check + production build only).
