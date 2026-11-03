"""Scenario comparison on computed model outputs."""
from typing import Dict, Any

from ..analytics.calculations import calculate_variance, classify_variance

COMPARED = ["revenue", "cogs", "gross_profit", "operating_expenses", "operating_income",
            "gross_margin_pct", "operating_margin_pct", "ending_cash", "minimum_cash"]


def compare_summaries(scenario: Dict[str, Any], baseline: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    out = {}
    for m in COMPARED:
        s, b = scenario.get(m), baseline.get(m)
        if s is None or b is None:
            out[m] = {"scenario": s, "baseline": b, "absolute_change": None, "percentage_change": None,
                      "assessment": None, "note": "Not available"}
            continue
        if m.endswith("_pct"):
            diff = s - b
            out[m] = {"scenario": s, "baseline": b, "absolute_change": diff, "percentage_change": None,
                      "unit": "percentage points", "assessment": classify_variance(m, diff)}
        else:
            a, p = calculate_variance(s, b)
            out[m] = {"scenario": s, "baseline": b, "absolute_change": a, "percentage_change": p, "unit": "USD",
                      "assessment": classify_variance("ending_cash" if m == "minimum_cash" else m, a),
                      "note": "Baseline is zero; % not applicable" if p is None else None}
    return out


def compare_scenarios(s1: Dict[str, Any], s2: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Compare two scenario results (s1 relative to s2)."""
    return compare_summaries(s1["summary"], s2["summary"])
