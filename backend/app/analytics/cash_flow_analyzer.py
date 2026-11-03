"""Historical cash-flow reconciliation.

Source convention (cash_flow.csv): collections and all payment columns are positive amounts;
`other_cash_movements` is a signed net movement (positive = inflow).
Ending cash = Opening + Collections + Other - Operating payments - Payroll - Capex - Debt repayments.
Reported values are never corrected; differences are reported.
"""
from typing import Dict, Any, List, Optional

import pandas as pd

from .calculations import calculate_cash_flow_ending, RECONCILIATION_TOLERANCE, pct_change

OUTFLOW_COLS = ["operating_payments", "payroll_payments", "capital_expenditure", "debt_repayments"]


class CashFlowAnalyzer:
    def analyze(self, opening_cash: float, inflows: float, outflows: float, ending_cash_reported: float = None) -> dict:
        ending_cash_calc = calculate_cash_flow_ending(opening_cash, inflows, outflows)
        reconciled = True
        if ending_cash_reported is not None:
            reconciled = abs(ending_cash_calc - ending_cash_reported) <= RECONCILIATION_TOLERANCE
        return {
            "opening_cash": opening_cash,
            "inflows": inflows,
            "outflows": outflows,
            "ending_cash_calculated": ending_cash_calc,
            "ending_cash_reported": ending_cash_reported,
            "reconciliation_difference": None if ending_cash_reported is None else ending_cash_reported - ending_cash_calc,
            "reconciled": reconciled,
        }

    def history(self, cf: pd.DataFrame, last_actual_period: str, business_unit: Optional[str] = None) -> Dict[str, Any]:
        if business_unit:
            cf = cf[cf["business_unit"] == business_unit]
        rows: List[Dict[str, Any]] = []
        for _, r in cf.sort_values(["business_unit", "period"], kind="stable").iterrows():
            other = float(r["other_cash_movements"])
            inflows = float(r["customer_collections"]) + max(other, 0.0)
            outflows = float(sum(r[c] for c in OUTFLOW_COLS)) + max(-other, 0.0)
            rec = self.analyze(float(r["opening_cash"]), inflows, outflows, float(r["ending_cash"]))
            rows.append({"period": r["period"], "business_unit": r["business_unit"],
                         "status": "historical" if r["period"] <= last_actual_period else "dataset_plan",
                         "opening_cash": float(r["opening_cash"]), "customer_collections": float(r["customer_collections"]),
                         "other_cash_movements": other, "cash_inflows": inflows,
                         **{c: float(r[c]) for c in OUTFLOW_COLS}, "cash_outflows": outflows,
                         "net_cash_movement": inflows - outflows, "ending_cash_reported": float(r["ending_cash"]),
                         "ending_cash_calculated": rec["ending_cash_calculated"],
                         "reconciliation_difference": rec["reconciliation_difference"], "reconciled": rec["reconciled"],
                         "duplicate": bool(r.get("duplicate", False))})
        continuity = []
        for bu in sorted({r["business_unit"] for r in rows}):
            seq = [r for r in rows if r["business_unit"] == bu and not r["duplicate"]]
            for prev, cur in zip(seq, seq[1:]):
                consecutive = str(pd.Period(prev["period"], "M") + 1) == cur["period"]
                diff = cur["opening_cash"] - prev["ending_cash_reported"]
                continuity.append({"business_unit": bu, "from_period": prev["period"], "to_period": cur["period"],
                                   "consecutive_months": consecutive, "difference": diff,
                                   "continuous": abs(diff) <= RECONCILIATION_TOLERANCE,
                                   "expected": consecutive})
        unrec = [r for r in rows if not r["reconciled"]]
        breaks = [c for c in continuity if c["expected"] and not c["continuous"]]
        warnings = []
        if unrec:
            warnings.append(f"{len(unrec)} of {len(rows)} cash rows: reported ending cash does not equal opening + inflows - outflows "
                            f"(largest difference {max(abs(r['reconciliation_difference']) for r in unrec):,.0f}). Source data not corrected.")
        if breaks:
            warnings.append(f"{len(breaks)} consecutive-month opening/ending cash continuity breaks")
        if any(r["duplicate"] for r in rows):
            warnings.append("Conflicting duplicate cash rows exist for the same business unit and period")
        gaps = [c for c in continuity if not c["consecutive_months"]]
        if gaps:
            warnings.append(f"{len(gaps)} non-consecutive period gaps; continuity is not expected across gaps")
        return {"rows": rows, "continuity": continuity, "warnings": warnings,
                "reconciled_rows": len(rows) - len(unrec), "total_rows": len(rows),
                "convention": __doc__.strip()}
