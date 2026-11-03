"""Scenario assumption registry, validation and preset conversion.

Every assumption has a stable key, a unit, an application rule and bounds. Unknown keys,
out-of-range values, unknown departments and duplicates are rejected (never silently ignored).
"""
import math
from typing import Dict, List, Any, Optional, Tuple

from ..analytics.forecasting import BaselineInputs

ASSUMPTIONS: Dict[str, Dict[str, Any]] = {
    "revenue_growth_adj": {
        "name": "Revenue growth adjustment", "kind": "additive_rate", "min": -0.5, "max": 0.5,
        "unit": "annual growth, percentage points as a decimal (0.02 = +2pp)",
        "rule": "Added to the department's baseline annual YoY revenue growth; compounded monthly.",
        "department_scoped": True},
    "revenue_level_pct": {
        "name": "Revenue level change", "kind": "relative", "min": -0.5, "max": 0.5,
        "unit": "relative change as a decimal (-0.10 = -10%)",
        "rule": "Projected revenue in every period multiplied by (1 + value). COGS follows via the COGS ratio.",
        "department_scoped": True},
    "customer_count_pct": {
        "name": "Customer count change", "kind": "relative", "min": -0.5, "max": 0.5,
        "unit": "relative change as a decimal",
        "rule": "Revenue = customer_count x average revenue per customer (ARPC held constant), so revenue scales by (1 + value). "
                "Only Sales & Marketing has customer drivers.",
        "department_scoped": True, "allowed_departments": ["Sales & Marketing"]},
    "cogs_ratio_adj": {
        "name": "COGS ratio adjustment", "kind": "additive_ratio", "min": -0.2, "max": 0.2,
        "unit": "percentage points of revenue as a decimal (0.02 = +2pp)",
        "rule": "Added to the base-period COGS/revenue ratio; resulting ratio must stay within [0, 1).",
        "department_scoped": True},
    "opex_growth_adj": {
        "name": "Operating expense growth adjustment", "kind": "additive_rate", "min": -0.5, "max": 0.5,
        "unit": "annual growth, percentage points as a decimal",
        "rule": "Added to the department's baseline annual YoY operating-expense growth; compounded monthly.",
        "department_scoped": True},
    "compensation_pct": {
        "name": "Average compensation change", "kind": "relative", "min": -0.5, "max": 0.5,
        "unit": "relative change as a decimal",
        "rule": "Compensation = headcount x average compensation; compensation expense multiplied by (1 + value).",
        "department_scoped": True},
    "headcount_pct": {
        "name": "Headcount change", "kind": "relative", "min": -0.5, "max": 0.5,
        "unit": "relative change as a decimal",
        "rule": "Compensation = headcount x average compensation; compensation expense multiplied by (1 + value).",
        "department_scoped": True},
    "marketing_pct": {
        "name": "Marketing expense change", "kind": "relative", "min": -1.0, "max": 1.0,
        "unit": "relative change as a decimal", "rule": "Marketing expense multiplied by (1 + value); -1.0 eliminates it.",
        "department_scoped": True},
    "technology_pct": {
        "name": "Technology expense change", "kind": "relative", "min": -1.0, "max": 1.0,
        "unit": "relative change as a decimal", "rule": "Technology expense multiplied by (1 + value).",
        "department_scoped": True},
    "collection_days": {
        "name": "Collection period (DSO)", "kind": "replacement", "min": 0.0, "max": 180.0,
        "unit": "days", "rule": "Replaces the baseline collection period. Receivables = monthly revenue x days / 30; "
                                "the change in receivables shifts cash collections (no income-statement effect).",
        "department_scoped": False},
}

# scenarios.json financial_line -> assumption key (percentage change_type)
_LINE_TO_KEY = {"revenue": "revenue_level_pct", "compensation_expense": "compensation_pct",
                "marketing_expense": "marketing_pct", "technology_expense": "technology_pct"}

PRESET_TYPES = {"reference": "baseline", "optimistic": "upside", "stress_test": "downside",
                "intervention": "management_intervention"}


class AssumptionError(ValueError):
    def __init__(self, errors: List[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def registry(inputs: BaselineInputs) -> List[Dict[str, Any]]:
    out = []
    for k, v in ASSUMPTIONS.items():
        d = {"key": k, **v}
        if v["department_scoped"]:
            d["departments"] = [x for x in inputs.departments if x in v.get("allowed_departments", inputs.departments)]
        if k == "collection_days":
            d["baseline_value"] = inputs.baseline_collection_days
        out.append(d)
    return out


def validate_assumptions(assumptions: List[Dict[str, Any]], inputs: BaselineInputs
                         ) -> Tuple[Dict[str, Dict[str, float]], Optional[float], List[Dict[str, Any]]]:
    """Return (per-department params, collection_days, normalised assumptions). Raises AssumptionError."""
    errors, seen, normalised = [], set(), []
    depts = inputs.departments
    params: Dict[str, Dict[str, float]] = {d: {} for d in depts}
    collection_days = None
    for i, a in enumerate(assumptions):
        key, value, dept = a.get("key"), a.get("value"), a.get("department")
        spec = ASSUMPTIONS.get(key)
        if spec is None:
            errors.append(f"assumption[{i}]: unsupported key '{key}'. Supported: {', '.join(ASSUMPTIONS)}")
            continue
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            errors.append(f"{key}: value must be a finite number")
            continue
        if not spec["min"] <= value <= spec["max"]:
            errors.append(f"{key}: value {value} outside allowed range [{spec['min']}, {spec['max']}] ({spec['unit']})")
            continue
        if not spec["department_scoped"] and dept:
            errors.append(f"{key}: applies to the whole model and does not accept a department")
            continue
        allowed = [d for d in depts if d in spec.get("allowed_departments", depts)]
        targets = [dept] if dept else allowed
        if dept and dept not in allowed:
            errors.append(f"{key}: department '{dept}' not supported; allowed: {', '.join(allowed)}")
            continue
        sig = (key, dept or "*")
        if sig in seen or (dept and (key, "*") in seen) or (not dept and any(s[0] == key for s in seen)):
            errors.append(f"{key}: duplicate or overlapping assumption for {dept or 'all departments'}")
            continue
        seen.add(sig)
        if key == "collection_days":
            collection_days = float(value)
        else:
            for d in targets:
                params[d][key] = float(value)
        if key == "cogs_ratio_adj":
            for u in inputs.units:
                if u.department in targets and not 0 <= u.cogs_ratio + value < 1:
                    errors.append(f"cogs_ratio_adj: resulting COGS ratio {u.cogs_ratio + value:.3f} for {u.department} is outside [0, 1)")
        if key in ("revenue_growth_adj", "opex_growth_adj"):
            for u in inputs.units:
                base = u.revenue_growth if key == "revenue_growth_adj" else u.opex_growth
                if u.department in targets and base + value <= -1:
                    errors.append(f"{key}: resulting annual growth for {u.department} is <= -100%")
        normalised.append({"key": key, "name": spec["name"], "value": float(value), "unit": spec["unit"],
                           "department": dept, "kind": spec["kind"], "rule": spec["rule"],
                           "description": a.get("description")})
    if errors:
        raise AssumptionError(errors)
    return params, collection_days, normalised


def preset_assumptions(scenario: Dict[str, Any], drivers, inputs: BaselineInputs) -> List[Dict[str, Any]]:
    """Convert a scenarios.json definition into registry assumptions. Unsupported entries raise."""
    out, errors = [], []
    for a in scenario.get("assumptions", []):
        t = a.get("target", {})
        line = t.get("financial_line")
        if line == "customer_collections":
            d = drivers[(drivers["driver_name"] == "collection_period_days") & (drivers["scenario"] == scenario["scenario_id"])]
            if d.empty:
                errors.append(f"{a['assumption_name']}: no collection_period_days driver for scenario {scenario['scenario_id']}")
                continue
            out.append({"key": "collection_days", "value": float(d.iloc[0]["driver_value"]),
                        "description": f"{a['description']} (collection_period_days driver = {d.iloc[0]['driver_value']})"})
        elif line in _LINE_TO_KEY and a.get("change_type") == "percentage":
            if t.get("business_unit") not in {u.business_unit for u in inputs.units}:
                errors.append(f"{a['assumption_name']}: business unit {t.get('business_unit')} not in projection scope")
                continue
            dept = t.get("department")
            out.append({"key": _LINE_TO_KEY[line], "value": float(a["change_value"]),
                        "department": None if dept in (None, "*") else dept, "description": a["description"]})
        else:
            errors.append(f"{a.get('assumption_name')}: unsupported target {line}/{a.get('change_type')}")
    if errors:
        raise AssumptionError(errors)
    return out
