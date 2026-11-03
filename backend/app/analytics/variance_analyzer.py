"""Variance analysis and operating-income variance bridge.

Comparisons are performed on *matched records only*: a line is compared when both sources report
the same (period, business_unit, department, financial_line). This prevents comparing a full set
of actuals against a partial budget. Unmatched record counts are always reported.
"""
from typing import Dict, Any, List, Optional

import pandas as pd

from .calculations import (calculate_variance, classify_variance, income_statement,
                           RECONCILIATION_TOLERANCE)
from ..data.repository import LEDGER_KEY, OPEX_LINES

STATEMENT_METRICS = ["revenue", "cogs", "gross_profit", "operating_expenses", "operating_income",
                     "gross_margin_pct", "operating_margin_pct"]


class VarianceAnalyzer:
    def analyze_variance(self, actual_or_forecast: float, budget: float, metric: str) -> Dict[str, Any]:
        abs_var, pct_var = calculate_variance(actual_or_forecast, budget)
        caveats = []
        if budget == 0:
            caveats.append("Comparison value is zero; percentage variance not applicable")
        return {
            "metric": metric,
            "actual_or_forecast_value": actual_or_forecast,
            "budget_value": budget,
            "absolute_variance": abs_var,
            "percentage_variance": pct_var,
            "favourable_unfavourable": classify_variance(metric, abs_var),
            "caveats": caveats,
        }


def metric_variance(metric: str, value: Optional[float], comparison: Optional[float]) -> Dict[str, Any]:
    if value is None or comparison is None:
        return {"metric": metric, "value": value, "comparison_value": comparison,
                "absolute_variance": None, "percentage_variance": None, "assessment": None,
                "note": "Not available: one side is missing"}
    if metric.endswith("_pct"):
        diff = value - comparison  # percentage points
        return {"metric": metric, "value": value, "comparison_value": comparison,
                "absolute_variance": diff, "percentage_variance": None,
                "assessment": classify_variance(metric, diff), "note": "Margin change in percentage points"}
    a, p = calculate_variance(value, comparison)
    return {"metric": metric, "value": value, "comparison_value": comparison,
            "absolute_variance": a, "percentage_variance": p, "assessment": classify_variance(metric, a),
            "note": "Comparison value is zero; % not applicable" if p is None else None}


def variance_bridge(current: Dict[str, float], comparison: Dict[str, float]) -> Dict[str, Any]:
    """OI variance = revenue variance - COGS variance - opex variance (expenses positive)."""
    rv = current["revenue"] - comparison["revenue"]
    cv = current["cogs"] - comparison["cogs"]
    ov = current["operating_expenses"] - comparison["operating_expenses"]
    calculated = rv - cv - ov
    actual_diff = current["operating_income"] - comparison["operating_income"]
    residual = actual_diff - calculated
    return {
        "revenue_contribution": rv,
        "cogs_contribution": -cv,
        "operating_expense_contribution": -ov,
        "calculated_operating_income_variance": calculated,
        "actual_operating_income_difference": actual_diff,
        "reconciliation_difference": residual,
        "tolerance": RECONCILIATION_TOLERANCE,
        "reconciled": abs(residual) <= RECONCILIATION_TOLERANCE,
        "formula": "OI variance = Revenue variance - COGS variance - Operating expense variance",
    }


def _matched_statement(lines: Dict[str, float]) -> Dict[str, Any]:
    # Within a matched subset, an unreported line contributes 0 to both sides equally.
    full = {l: lines.get(l, 0.0) for l in ["revenue", "cogs"] + OPEX_LINES}
    st = income_statement(full, OPEX_LINES)
    st.pop("missing_lines")
    return st


def compare_sources(ledger: pd.DataFrame, current: str, comparison: str,
                    group_by: Optional[str] = None, materiality_pct: float = 5.0,
                    materiality_abs: float = 10000.0) -> Dict[str, Any]:
    a = ledger[ledger["source"] == current][LEDGER_KEY + ["value"]]
    b = ledger[ledger["source"] == comparison][LEDGER_KEY + ["value"]]
    merged = a.merge(b, on=LEDGER_KEY, how="outer", suffixes=("_cur", "_cmp"), indicator=True)
    matched = merged[merged["_merge"] == "both"].copy()
    result: Dict[str, Any] = {
        "current_source": current, "comparison_source": comparison,
        "matched_records": int(len(matched)),
        "unmatched_current_records": int((merged["_merge"] == "left_only").sum()),
        "unmatched_comparison_records": int((merged["_merge"] == "right_only").sum()),
        "matched_periods": sorted(matched["period"].unique().tolist()),
        "line_variances": [], "statement": None, "bridge": None, "groups": [], "material_variances": [],
        "warnings": [],
    }
    if matched.empty:
        result["warnings"].append(f"No overlapping records between {current} and {comparison} for the requested scope")
        return result
    rows = []
    for _, r in matched.iterrows():
        mv = metric_variance(r["financial_line"], float(r["value_cur"]), float(r["value_cmp"]))
        mv.update(period=r["period"], business_unit=r["business_unit"], department=r["department"])
        rows.append(mv)
    result["line_variances"] = rows
    result["material_variances"] = sorted(
        [r for r in rows if abs(r["absolute_variance"]) >= materiality_abs
         and (r["percentage_variance"] is None or abs(r["percentage_variance"]) >= materiality_pct)],
        key=lambda r: -abs(r["absolute_variance"]))
    result["materiality"] = {"abs": materiality_abs, "pct": materiality_pct}

    def _side(df, col):
        return df.groupby("financial_line")[col].sum().to_dict()

    cur_st, cmp_st = _matched_statement(_side(matched, "value_cur")), _matched_statement(_side(matched, "value_cmp"))
    result["statement"] = {m: metric_variance(m, cur_st[m], cmp_st[m]) for m in STATEMENT_METRICS}
    result["bridge"] = variance_bridge(cur_st, cmp_st)
    present = set(matched["financial_line"])
    if "revenue" not in present:
        result["warnings"].append("Matched scope contains no revenue lines; margins are not meaningful")
    if group_by:
        for key, g in matched.groupby(group_by):
            c, k = _matched_statement(_side(g, "value_cur")), _matched_statement(_side(g, "value_cmp"))
            result["groups"].append({group_by: key,
                                     "statement": {m: metric_variance(m, c[m], k[m]) for m in STATEMENT_METRICS},
                                     "bridge": variance_bridge(c, k)})
    return result
