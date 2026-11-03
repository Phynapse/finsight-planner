"""Deterministic one-variable sensitivity analysis using the scenario engine (not Monte Carlo)."""
from typing import Dict, Any, List, Optional

STANDARD_SHOCKS = {
    "revenue_growth_adj": (-0.02, 0.02), "revenue_level_pct": (-0.05, 0.05), "cogs_ratio_adj": (-0.02, 0.02),
    "opex_growth_adj": (-0.02, 0.02), "compensation_pct": (-0.05, 0.05), "marketing_pct": (-0.10, 0.10),
    "technology_pct": (-0.10, 0.10), "collection_days": (45.0, 75.0),
}
MAX_POINTS = 9
OUTPUT_METRICS = ["revenue", "gross_profit", "operating_income", "operating_margin_pct", "ending_cash"]


class SensitivityAnalyzer:
    def __init__(self, engine):
        self.engine = engine

    def analyze(self, key: str, values: List[float], horizon: int = 12,
                department: Optional[str] = None) -> Dict[str, Any]:
        if not values or len(values) > MAX_POINTS:
            raise ValueError(f"Provide between 1 and {MAX_POINTS} test values")
        base = self.engine.baseline(horizon)["summary"]
        points = []
        for v in values:
            a = {"key": key, "value": v}
            if department:
                a["department"] = department
            res = self.engine.run([a], horizon)  # raises AssumptionError on invalid values
            points.append({"value": v, "metrics": {m: res["summary"].get(m) for m in OUTPUT_METRICS},
                           "change_vs_baseline": {m: res["comparison_against_baseline"][m]["absolute_change"]
                                                  for m in OUTPUT_METRICS}})
        return {"assumption": key, "department": department, "baseline": {m: base.get(m) for m in OUTPUT_METRICS},
                "points": points, "method": "one-variable deterministic sensitivity"}

    def rank(self, horizon: int = 12, metric: str = "operating_income") -> Dict[str, Any]:
        """Tornado ranking: impact of standard low/high shocks on `metric`."""
        rows = []
        for key, (lo, hi) in STANDARD_SHOCKS.items():
            r = self.analyze(key, [lo, hi], horizon)
            low, high = (p["change_vs_baseline"][metric] for p in r["points"])
            rows.append({"assumption": key, "low_value": lo, "high_value": hi, "impact_low": low, "impact_high": high,
                         "range": abs(high - low) if low is not None and high is not None else None})
        rows.sort(key=lambda x: -(x["range"] or 0))
        return {"metric": metric, "horizon_months": horizon, "ranking": rows,
                "method": "one-at-a-time standard shocks; not a probabilistic analysis"}
