"""Deterministic projection model shared by forecasting, scenarios and sensitivity analysis.

Method `historical_yoy_trend_with_cost_ratios`:
* Base period = latest period in actuals. Projected units = (business_unit, department) pairs with
  revenue and COGS actuals in the base period.
* Annual revenue growth = same-month year-over-year growth (base period vs base period - 12 months).
  Monthly rate = (1 + annual)^(1/12) - 1, compounded from the base-period level.
* COGS = projected revenue x base-period COGS ratio (+ assumption adjustment).
* Each reported operating-expense line grows at the unit's YoY total-opex growth rate.
* Cash: opening cash = latest reported ending cash at/before the base period for the BU.
  Receivables = monthly revenue x collection days / 30; collections = revenue + AR(t-1) - AR(t).
  COGS and operating expenses are assumed paid in the month incurred. Capex, debt repayments and
  other cash movements are held flat at the anchor row values.
This is an assumption-driven projection, not a statistically validated prediction.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional, Any

import pandas as pd

from .calculations import income_statement, calculate_cash_flow_ending, RECONCILIATION_TOLERANCE
from ..data.repository import DataRepository, OPEX_LINES

METHOD = "historical_yoy_trend_with_cost_ratios"
BASELINE_COLLECTION_DAYS = 60.0  # model assumption: not present in the dataset for the baseline
MAX_HORIZON = 24
DEFAULT_HORIZON = 12


def add_months(period: str, n: int) -> str:
    return str(pd.Period(period, "M") + n)


@dataclass(frozen=True)
class UnitBase:
    business_unit: str
    department: str
    base_period: str
    lines: Tuple[Tuple[str, float], ...]
    revenue_growth: float
    opex_growth: float
    cogs_ratio: float
    growth_reference_period: Optional[str]

    def line(self, name: str) -> Optional[float]:
        return dict(self.lines).get(name)


@dataclass(frozen=True)
class CashAnchor:
    business_unit: str
    period: str
    ending_cash: float
    capital_expenditure: float
    debt_repayments: float
    other_cash_movements: float
    reported_reconciliation_difference: float


@dataclass(frozen=True)
class BaselineInputs:
    base_period: str
    units: Tuple[UnitBase, ...]
    cash_anchors: Tuple[CashAnchor, ...]
    baseline_collection_days: float = BASELINE_COLLECTION_DAYS
    warnings: Tuple[str, ...] = field(default_factory=tuple)
    excluded_units: Tuple[str, ...] = field(default_factory=tuple)

    @property
    def departments(self) -> List[str]:
        return [u.department for u in self.units]


def build_baseline_inputs(repo: DataRepository) -> BaselineInputs:
    act = repo.get_ledger("actual")
    base = repo.latest_actual_period()
    prior = add_months(base, -12)
    warnings, units, excluded = [], [], []
    for (bu, dept), g in act.groupby(["business_unit", "department"]):
        cur = g[g["period"] == base].set_index("financial_line")["value"].to_dict()
        if "revenue" not in cur or "cogs" not in cur:
            last = g["period"].max()
            excluded.append(f"{bu} / {dept} (latest actuals {last})")
            continue
        py = g[g["period"] == prior].set_index("financial_line")["value"].to_dict()
        opex_lines = [l for l in OPEX_LINES if l in cur]
        missing = [l for l in OPEX_LINES if l not in cur]
        if missing:
            warnings.append(f"{bu} / {dept}: {', '.join(missing)} not reported in {base}; not projected")
        if py.get("revenue"):
            rg = cur["revenue"] / py["revenue"] - 1
            matched = [l for l in opex_lines if l in py]
            og = sum(cur[l] for l in matched) / sum(py[l] for l in matched) - 1 if matched else 0.0
            ref = prior
        else:
            rg, og, ref = 0.0, 0.0, None
            warnings.append(f"{bu} / {dept}: no actuals for {prior}; growth assumed 0% (flat)")
        units.append(UnitBase(bu, dept, base, tuple((l, float(cur[l])) for l in ["revenue", "cogs"] + opex_lines),
                              float(rg), float(og), float(cur["cogs"] / cur["revenue"]), ref))
    anchors = []
    cf = repo.cash_flow
    for bu in sorted({u.business_unit for u in units}):
        rows = cf[(cf["business_unit"] == bu) & (cf["period"] <= base) & (~cf["duplicate"])].sort_values("period")
        if rows.empty:
            warnings.append(f"{bu}: no historical cash row at or before {base}; cash not projected")
            continue
        r = rows.iloc[-1]
        calc = (r.opening_cash + r.customer_collections + r.other_cash_movements - r.operating_payments
                - r.payroll_payments - r.capital_expenditure - r.debt_repayments)
        diff = float(r.ending_cash - calc)
        if r["period"] != base:
            warnings.append(f"{bu}: latest cash row is {r['period']}, not {base}")
        if abs(diff) > RECONCILIATION_TOLERANCE:
            warnings.append(f"{bu} {r['period']}: reported ending cash differs from its components by {diff:,.0f}; "
                            "projection opens from the reported ending cash")
        anchors.append(CashAnchor(bu, r["period"], float(r.ending_cash), float(r.capital_expenditure),
                                  float(r.debt_repayments), float(r.other_cash_movements), diff))
    if excluded:
        warnings.append(f"Units without {base} revenue/COGS actuals are excluded from projections: {'; '.join(excluded)}")
    return BaselineInputs(base, tuple(units), tuple(anchors), BASELINE_COLLECTION_DAYS,
                          tuple(warnings), tuple(excluded))


def _monthly(annual: float) -> float:
    return (1 + annual) ** (1 / 12) - 1


def run_model(inputs: BaselineInputs, dept_params: Optional[Dict[str, Dict[str, float]]] = None,
              collection_days: Optional[float] = None, horizon: int = DEFAULT_HORIZON) -> Dict[str, Any]:
    """Pure function: returns a new result; never mutates `inputs`."""
    if not 1 <= horizon <= MAX_HORIZON:
        raise ValueError(f"horizon must be between 1 and {MAX_HORIZON} months")
    dept_params = dept_params or {}
    periods = [add_months(inputs.base_period, i) for i in range(1, horizon + 1)]
    unit_out, trace = [], []
    totals = {p: {} for p in periods}
    for u in inputs.units:
        p = {k: 0.0 for k in ["revenue_growth_adj", "revenue_level_pct", "customer_count_pct", "cogs_ratio_adj",
                              "opex_growth_adj", "compensation_pct", "headcount_pct", "marketing_pct", "technology_pct"]}
        p.update(dept_params.get(u.department, {}))
        rev_g = u.revenue_growth + p["revenue_growth_adj"]
        opex_g = u.opex_growth + p["opex_growth_adj"]
        cogs_ratio = u.cogs_ratio + p["cogs_ratio_adj"]
        level = (1 + p["revenue_level_pct"]) * (1 + p["customer_count_pct"])
        line_mult = {"compensation_expense": (1 + p["compensation_pct"]) * (1 + p["headcount_pct"]),
                     "marketing_expense": 1 + p["marketing_pct"], "technology_expense": 1 + p["technology_pct"]}
        trace.append({"business_unit": u.business_unit, "department": u.department, "base_period": u.base_period,
                      "base_lines": dict(u.lines), "baseline_annual_revenue_growth": u.revenue_growth,
                      "growth_reference_period": u.growth_reference_period,
                      "applied_annual_revenue_growth": rev_g, "revenue_level_multiplier": level,
                      "baseline_cogs_ratio": u.cogs_ratio, "applied_cogs_ratio": cogs_ratio,
                      "baseline_annual_opex_growth": u.opex_growth, "applied_annual_opex_growth": opex_g,
                      "opex_line_multipliers": line_mult})
        rows = []
        for i, per in enumerate(periods, start=1):
            rev = u.line("revenue") * (1 + _monthly(rev_g)) ** i * level
            lines = {"revenue": rev, "cogs": rev * cogs_ratio}
            for l, v in u.lines:
                if l in OPEX_LINES:
                    lines[l] = v * (1 + _monthly(opex_g)) ** i * line_mult.get(l, 1.0)
            st = income_statement(lines, OPEX_LINES)
            row = {"period": per, "status": "projected", **{k: v for k, v in lines.items()}, **st}
            row["missing_lines"] = st["missing_lines"]
            rows.append(row)
            for k, v in lines.items():
                totals[per][k] = totals[per].get(k, 0.0) + v
        unit_out.append({"business_unit": u.business_unit, "department": u.department, "rows": rows})
    total_rows = []
    for per in periods:
        st = income_statement(totals[per], OPEX_LINES)
        st.pop("missing_lines")
        total_rows.append({"period": per, "status": "projected", **st})
    agg = {k: sum(r[k] for r in total_rows) for k in ["revenue", "cogs", "gross_profit", "operating_expenses", "operating_income"]}
    summary = dict(agg)
    summary["gross_margin_pct"] = agg["gross_profit"] / agg["revenue"] * 100 if agg["revenue"] else None
    summary["operating_margin_pct"] = agg["operating_income"] / agg["revenue"] * 100 if agg["revenue"] else None
    cash = project_cash(inputs, total_rows, collection_days if collection_days is not None else inputs.baseline_collection_days)
    if cash["rows"]:
        summary["ending_cash"] = cash["rows"][-1]["ending_cash"]
        summary["minimum_cash"] = min(r["ending_cash"] for r in cash["rows"])
    else:
        summary["ending_cash"] = summary["minimum_cash"] = None
    return {"method": METHOD, "base_period": inputs.base_period, "periods": periods,
            "units": unit_out, "total": total_rows, "summary": summary, "cash": cash, "trace": trace}


def project_cash(inputs: BaselineInputs, total_rows: List[Dict[str, Any]], collection_days: float) -> Dict[str, Any]:
    if not inputs.cash_anchors or not total_rows:
        return {"rows": [], "assumptions": {}, "reconciled": None}
    anchor_cash = sum(a.ending_cash for a in inputs.cash_anchors)
    capex = sum(a.capital_expenditure for a in inputs.cash_anchors)
    debt = sum(a.debt_repayments for a in inputs.cash_anchors)
    other = sum(a.other_cash_movements for a in inputs.cash_anchors)
    base_rev = sum(u.line("revenue") for u in inputs.units)
    ar_prev = base_rev * inputs.baseline_collection_days / 30.0
    opening = anchor_cash
    rows, ok = [], True
    for r in total_rows:
        ar = r["revenue"] * collection_days / 30.0
        collections = r["revenue"] + ar_prev - ar
        inflows = collections + max(other, 0.0)
        operating_payments = r["cogs"] + r["operating_expenses"]
        outflows = operating_payments + capex + debt + max(-other, 0.0)
        ending = calculate_cash_flow_ending(opening, inflows, outflows)
        ok = ok and abs(opening + inflows - outflows - ending) <= RECONCILIATION_TOLERANCE
        rows.append({"period": r["period"], "status": "projected", "opening_cash": opening,
                     "customer_collections": collections, "other_cash_movements": other, "cash_inflows": inflows,
                     "operating_payments": operating_payments, "capital_expenditure": capex, "debt_repayments": debt,
                     "cash_outflows": outflows, "net_cash_movement": inflows - outflows, "ending_cash": ending,
                     "receivables": ar})
        opening, ar_prev = ending, ar
    return {"rows": rows, "reconciled": ok, "assumptions": {
        "opening_cash": anchor_cash, "opening_cash_source": [f"cash_flow {a.business_unit} {a.period} ending_cash" for a in inputs.cash_anchors],
        "baseline_collection_days": inputs.baseline_collection_days, "collection_days": collection_days,
        "payment_timing": "COGS and operating expenses paid in the month incurred",
        "capital_expenditure_per_month": capex, "debt_repayments_per_month": debt,
        "other_cash_movements_per_month": other,
        "formula": "Ending = Opening + Inflows - Outflows; Collections = Revenue + AR(t-1) - AR(t); AR = Revenue x days / 30"}}
