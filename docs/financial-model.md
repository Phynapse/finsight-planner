# Financial Model Specification

All authoritative calculations live in `backend/app/analytics/` and are deterministic, pure and unit-tested.
Data is synthetic (Asteron Group).

## Formulas (`calculations.py`)

| ID | Formula |
|---|---|
| F-GROSS_PROFIT | Gross profit = Revenue − COGS |
| F-OPERATING_EXPENSES | Operating expenses = Compensation + Marketing + Technology + Facilities + Other (reported lines only) |
| F-OPERATING_INCOME | Operating income = Gross profit − Operating expenses |
| F-GROSS_MARGIN_PCT | Gross margin % = Gross profit / Revenue × 100 |
| F-OPERATING_MARGIN_PCT | Operating margin % = Operating income / Revenue × 100 |
| F-VARIANCE | Variance = Current − Comparison; Variance % = Variance / \|Comparison\| × 100 |
| F-OI-BRIDGE | OI variance = Revenue variance − COGS variance − Opex variance |
| F-CASH-RECON | Ending cash = Opening + Inflows − Outflows |

Margins return `null` (not applicable) when revenue is 0. Variance % returns `null` when the comparison value is 0 —
never infinity. Margin changes are reported in percentage points.

## Sign conventions

- Revenue, COGS and all operating-expense lines are stored and calculated as **positive** amounts.
- Positive revenue / profit / margin / cash variance = **favourable**.
- Positive COGS or expense variance = higher spending = **unfavourable** (`classify_variance`).
- Cash: collections and every payment column are positive; `other_cash_movements` is a signed net movement
  (positive = inflow, negative = outflow). Outflows are subtracted exactly once.

## Matched-record comparison rule

Budget and forecast coverage is sparse. `compare_sources` compares only records present in **both** sources for the same
`(period, business_unit, department, financial_line)`. Unmatched counts are always returned and surfaced as warnings.
Consequences on the current data:

- Actual vs budget: 61 matched records across 2024-01, 2024-06, 2024-09, 2024-12, 2025-06, 2026-06.
- Actual vs forecast and forecast vs budget: **no overlapping records** (forecast covers 2026-12 and 2027-03 only);
  the API returns an explicit "no overlap" result instead of a number.
- Year over year compares the selected month with the same month 12 months earlier, on matched records.

Within a matched subset, operating income is computed on matched lines; the bridge always reconciles within the
0.01 tolerance, and any residual would be exposed (`reconciled: false`, `reconciliation_difference`).

## Aggregation and double counting

Each source record is a monthly `(period, BU, department, line)` amount; there are no parent/total rows, so rollups
are plain sums of distinct records (verified by the data-wide reconciliation tests). Group totals always sum to the
overall total. Periods with different unit coverage are flagged as not like-for-like in trends.

## Missing data

- Missing revenue → revenue-dependent metrics are `null`; missing COGS → gross profit `null`. Never zero-filled.
- Unreported opex lines (e.g. `other_operating_expense` for Engineering & Product after 2024-02) are listed in
  `missing_lines` / `units_with_missing_lines`; operating expenses then cover reported lines only, and this is disclosed.
- Non-numeric, negative or duplicate source rows are reported in `repository.issues`; duplicates keep the first row.

## Cash-flow reconciliation (source data)

`cash_flow.csv` is checked row by row: only 1 of 26 rows (Europe 2024-01) reconciles; the others differ by up to
405,000. Two conflicting rows exist for North America 2026-12. Rows after the last actual period (2026-09) are labelled
`dataset_plan`. These differences are reported, never corrected. Continuity (prior ending = next opening) is only
expected for consecutive months.

## Driver relationships (`driver_analyzer.py`)

- Revenue (Sales & Marketing) = customer_count × average_revenue_per_customer (2024-01: 8,500 × 100 = 850,000 = actual).
- Compensation = headcount × average_compensation (verified for all three NA departments in 2024-01, within 0.5%).
Driver rows without matching actuals (2025-01, 2026-01) are reported as unmatched.

## Limitations

No accounting accruals, balance sheet, tax, interest, FX, or free cash flow. Causes of variances (price, volume,
timing, efficiency) are not identifiable from the data and are never asserted.
