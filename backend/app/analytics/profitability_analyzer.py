from typing import Dict, Any, List

import pandas as pd

from .calculations import (calculate_gross_profit, calculate_operating_income,
                           calculate_gross_margin_pct, calculate_operating_margin_pct, income_statement)
from ..data.repository import OPEX_LINES

METRICS = ["revenue", "cogs", "gross_profit", "operating_expenses", "operating_income",
           "gross_margin_pct", "operating_margin_pct"]


class ProfitabilityAnalyzer:
    def analyze(self, revenue: float, cogs: float, operating_expenses: float) -> Dict[str, Any]:
        gross_profit = calculate_gross_profit(revenue, cogs)
        operating_income = calculate_operating_income(gross_profit, operating_expenses)
        return {
            "revenue": revenue,
            "cogs": cogs,
            "gross_profit": gross_profit,
            "operating_expenses": operating_expenses,
            "operating_income": operating_income,
            "gross_margin_pct": calculate_gross_margin_pct(gross_profit, revenue),
            "operating_margin_pct": calculate_operating_margin_pct(operating_income, revenue),
        }


def build_statements(ledger: pd.DataFrame, group_cols: List[str]) -> List[Dict[str, Any]]:
    """Income statements per group. Lines are first summed per (period, BU, department) unit,
    so every reported record is counted exactly once. Lines that a unit did not report are
    tracked per unit and surfaced as `missing_lines` with the affected units."""
    if ledger.empty:
        return []
    out = []
    groups = ledger.groupby(group_cols, sort=True) if group_cols else [((), ledger)]
    for key, g in groups:
        key = key if isinstance(key, tuple) else (key,)
        lines = g.groupby("financial_line")["value"].sum().to_dict()
        st = income_statement(lines, OPEX_LINES)
        units = g.groupby(["period", "business_unit", "department"])["financial_line"].apply(set)
        partial = []
        for unit, present in units.items():
            miss = [l for l in ["revenue", "cogs"] + OPEX_LINES if l not in present]
            if miss:
                partial.append({"unit": " | ".join(unit), "missing_lines": miss})
        st["missing_lines"] = sorted({l for p in partial for l in p["missing_lines"]})
        st["units_with_missing_lines"] = partial
        st["unit_count"] = int(len(units))
        st["record_count"] = int(len(g))
        st.update(dict(zip(group_cols, key)))
        out.append(st)
    return out
