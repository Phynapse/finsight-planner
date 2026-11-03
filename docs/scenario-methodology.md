# Scenario & Forecast Methodology

## Projection model (`analytics/forecasting.py`, method `historical_yoy_trend_with_cost_ratios`)

1. Base period = latest actual period (2026-09). Projected units = BU/department pairs with revenue and COGS actuals
   in the base period: **North America / Sales & Marketing** and **North America / Engineering & Product**. Other units
   are excluded with a warning (their latest actuals are 2024-01 or 2026-06).
2. Baseline annual revenue growth = same-month YoY (2026-09 vs 2025-09). Monthly rate = (1+g)^(1/12) − 1, compounded.
3. COGS = revenue × base-period COGS ratio.
4. Each reported opex line grows at the unit's YoY total-opex growth rate. Unreported lines are not projected.
5. Horizon: 1–24 months (default 12: 2026-10 … 2027-09). Every projected row has `status: "projected"`.
6. The reference forecast (`forecast.csv`, FCST-Q4-2026) is never overwritten; the generated projection is compared
   with it on matched records (2026-12 and 2027-03).

This is an explainable, assumption-driven projection — not a statistically validated forecast.

## Cash projection

- Opening cash = reported North America ending cash for 2026-09 (7,025,000). That row itself does not reconcile to its
  components (−200,000); the warning is propagated.
- Receivables AR = monthly revenue × collection days / 30. Collections = revenue + AR(t−1) − AR(t).
  Baseline collection days = 60 (**model assumption**; the dataset only gives 55 for upside and 75 for downside).
- COGS and operating expenses are paid in the month incurred (no payables model). Capex, debt repayments and
  other movements are held flat at the 2026-09 values. Ending = Opening + Inflows − Outflows (verified every month).

## Assumptions (`scenarios/assumptions.py`)

| Key | Unit / interpretation | Rule | Range |
|---|---|---|---|
| revenue_growth_adj | annual growth, pp as decimal (0.02 = +2pp) | added to baseline YoY revenue growth | ±0.5 |
| revenue_level_pct | relative change | revenue × (1+v); COGS follows via ratio | ±0.5 |
| customer_count_pct | relative change | Revenue = customers × ARPC (ARPC fixed); Sales & Marketing only | ±0.5 |
| cogs_ratio_adj | pp of revenue as decimal | added to COGS ratio; result must be in [0,1) | ±0.2 |
| opex_growth_adj | annual growth, pp as decimal | added to baseline opex growth | ±0.5 |
| compensation_pct | relative change | compensation = headcount × avg comp; × (1+v) | ±0.5 |
| headcount_pct | relative change | compensation × (1+v) | ±0.5 |
| marketing_pct | relative change | marketing × (1+v) | −1 … +1 |
| technology_pct | relative change | technology × (1+v) | −1 … +1 |
| collection_days | days, replacement | replaces baseline DSO; cash only, no P&L effect | 0 … 180 |

Department-scoped assumptions accept an optional `department`; omitted = all projected departments.

## Validation

Unknown keys, non-finite or out-of-range values, unknown departments, a department on a global assumption,
duplicate/overlapping assumptions, COGS ratios outside [0,1) and annual growth ≤ −100% are all rejected with HTTP 422
and a list of errors. Nothing is silently ignored. Bounds keep revenue positive; negative operating income is a
legitimate stressed outcome, not an error.

## Presets (`data/scenarios.json`)

| Preset | Type | Converted assumptions |
|---|---|---|
| baseline | baseline | none |
| upside | upside | revenue_level_pct +8% (S&M); collection_days 55 (from drivers) |
| downside | downside | revenue_level_pct −10% (S&M); compensation_pct +8% (E&P); collection_days 75 (from drivers) |
| expense_reduction | management_intervention | marketing_pct −15% (S&M); technology_pct −12% (E&P) |

Collection changes are mapped to the `collection_period_days` driver values for that scenario — not to the JSON's
percentage — because the receivables model needs days.

## Recalculation and comparison

`ScenarioEngine.run`: validate → run the pure model on immutable (frozen) baseline inputs → compute horizon totals
(revenue, COGS, gross profit, opex, operating income, margins) plus final and minimum cash → compare with a freshly
computed baseline (absolute change, % change with zero-denominator handling, margin changes in pp, assessment).
Identical inputs produce identical outputs; scenarios cannot affect each other or the baseline.

## Sensitivity (`analytics/sensitivity_analyzer.py`)

One-variable deterministic sweeps (≤ 9 values) and a one-at-a-time tornado ranking with standard shocks. Not Monte Carlo.

## State and limitations

User scenarios are kept in memory (max 100, lost on restart); presets are read-only (PUT returns 409). Single-point
YoY growth is a weak trend estimate; scope is limited to two North America departments; no seasonality.
