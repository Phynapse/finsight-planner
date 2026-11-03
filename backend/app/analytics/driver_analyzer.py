"""Driver relationships verified against actuals.

Revenue (Sales & Marketing) = customer_count x average_revenue_per_customer
Compensation expense       = headcount x average_compensation
Driver rows without a matching actual period are reported as unmatched, never back-filled.
"""
from typing import Dict, Any, List

import pandas as pd

from .calculations import calculate_variance

RELATIONSHIPS = [
    {"id": "revenue_from_customers", "output_line": "revenue",
     "drivers": ("customer_count", "average_revenue_per_customer"),
     "formula": "Revenue = customer_count x average_revenue_per_customer"},
    {"id": "compensation_from_headcount", "output_line": "compensation_expense",
     "drivers": ("headcount", "average_compensation"),
     "formula": "Compensation expense = headcount x average_compensation"},
]
TOLERANCE_PCT = 0.5


class DriverAnalyzer:
    def analyze(self, drivers: pd.DataFrame, actuals: pd.DataFrame) -> Dict[str, Any]:
        checks: List[Dict[str, Any]] = []
        scenario_implied: List[Dict[str, Any]] = []
        for rel in RELATIONSHIPS:
            d1, d2 = rel["drivers"]
            sub = drivers[drivers["driver_name"].isin([d1, d2])]
            piv = sub.pivot_table(index=["period", "business_unit", "department", "scenario"],
                                  columns="driver_name", values="driver_value", aggfunc="first")
            for (period, bu, dept, scen), r in piv.iterrows():
                if pd.isna(r.get(d1)) or pd.isna(r.get(d2)):
                    continue
                implied = float(r[d1] * r[d2])
                row = {"relationship": rel["id"], "formula": rel["formula"], "period": period, "business_unit": bu,
                       "department": dept, "scenario": scen, d1: float(r[d1]), d2: float(r[d2]), "implied_value": implied}
                if scen != "baseline":
                    scenario_implied.append(row)
                    continue
                act = actuals[(actuals["period"] == period) & (actuals["business_unit"] == bu)
                              & (actuals["department"] == dept) & (actuals["financial_line"] == rel["output_line"])]
                if act.empty:
                    row.update(actual_value=None, status="no_matching_actual")
                else:
                    a = float(act.iloc[0]["value"])
                    diff, pct = calculate_variance(a, implied)
                    row.update(actual_value=a, difference=diff, difference_pct=pct,
                               status="consistent" if pct is not None and abs(pct) <= TOLERANCE_PCT else "inconsistent")
                checks.append(row)
        return {"relationships": RELATIONSHIPS, "checks": checks, "scenario_driver_values": scenario_implied,
                "tolerance_pct": TOLERANCE_PCT,
                "notes": ["Driver data is sparse (2024-01, 2025-01, 2026-01); relationships are verified only where an "
                          "actual exists for the same period and unit.",
                          "Scenario driver rows (upside/downside) are shown as implied values; no baseline 2026 customer drivers exist."]}
