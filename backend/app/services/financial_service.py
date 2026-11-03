"""Financial service: filtering, statements, variances, rollups, forecast and cash flow."""
from typing import Dict, Any, List, Optional

import pandas as pd

from ..analytics.calculations import RECONCILIATION_TOLERANCE
from ..analytics.cash_flow_analyzer import CashFlowAnalyzer
from ..analytics.driver_analyzer import DriverAnalyzer
from ..analytics.forecasting import build_baseline_inputs, run_model, add_months, METHOD, BaselineInputs
from ..analytics.profitability_analyzer import build_statements
from ..analytics.variance_analyzer import compare_sources
from ..data.repository import DataRepository, ALL_LINES, OPEX_LINES

COMPARISONS = {"actual_vs_budget": ("actual", "budget"), "actual_vs_forecast": ("actual", "forecast"),
               "forecast_vs_budget": ("forecast", "budget")}
SOURCES = ("actual", "budget", "forecast")


class InvalidRequest(ValueError):
    pass


class FinancialService:
    def __init__(self, repo: DataRepository):
        self.repo = repo
        self.inputs: BaselineInputs = build_baseline_inputs(repo)

    # ---------- validation ----------
    def validate_scope(self, periods=None, business_unit=None, department=None, source=None):
        if business_unit and business_unit not in self.repo.business_units():
            raise InvalidRequest(f"Unknown business_unit '{business_unit}'. Valid: {', '.join(self.repo.business_units())}")
        if department and department not in self.repo.departments():
            raise InvalidRequest(f"Unknown department '{department}'. Valid: {', '.join(self.repo.departments())}")
        if source and source not in SOURCES:
            raise InvalidRequest(f"Unknown source '{source}'. Valid: {', '.join(SOURCES)}")
        all_periods = set(self.repo.ledger["period"])
        for p in periods or []:
            if p not in all_periods:
                raise InvalidRequest(f"Period '{p}' has no data in any dataset")

    def _filter(self, df: pd.DataFrame, periods=None, business_unit=None, department=None) -> pd.DataFrame:
        if periods:
            df = df[df["period"].isin(periods)]
        if business_unit:
            df = df[df["business_unit"] == business_unit]
        if department:
            df = df[df["department"] == department]
        return df

    def meta(self) -> Dict[str, Any]:
        cov = {s: self.repo.periods(s) for s in SOURCES}
        return {"company": "Asteron Group (synthetic)", "currency": "USD", "business_units": self.repo.business_units(),
                "departments": self.repo.departments(), "financial_lines": ALL_LINES, "periods": cov,
                "latest_actual_period": self.repo.latest_actual_period(), "comparisons": list(COMPARISONS) + ["year_over_year"],
                "data_issues": self.repo.issues, "granularity": "monthly records; actuals cover 13 sampled months, not a continuous series"}

    # ---------- statements ----------
    def summary(self, period: Optional[str] = None, business_unit: Optional[str] = None,
                department: Optional[str] = None) -> Dict[str, Any]:
        period = period or self.repo.latest_actual_period()
        self.validate_scope([period], business_unit, department)
        act = self._filter(self.repo.get_ledger("actual"), [period], business_unit, department)
        if act.empty:
            raise InvalidRequest(f"No actuals for {period} in the requested scope")
        st = build_statements(act, [])[0]
        units = sorted({f"{r.business_unit} / {r.department}" for r in act.itertuples()})
        prior = add_months(period, -12)
        yoy = self.year_over_year(period, business_unit, department)
        led = self._filter(self.repo.get_ledger(), [period], business_unit, department)
        budget = compare_sources(led, "actual", "budget")
        cf = self.repo.cash_flow
        cfp = cf[(cf["period"] == period) & (~cf["duplicate"])]
        if business_unit:
            cfp = cfp[cfp["business_unit"] == business_unit]
        cash = None
        if not cfp.empty and not department:
            cash = {"ending_cash": float(cfp["ending_cash"].sum()), "business_units": sorted(cfp["business_unit"].tolist()),
                    "source": "cash_flow.csv reported ending_cash"}
        warnings = []
        if st["units_with_missing_lines"]:
            warnings.append("Some units did not report all lines: " + "; ".join(
                f"{u['unit']} missing {', '.join(u['missing_lines'])}" for u in st["units_with_missing_lines"]))
        if department and business_unit is None and cash is None:
            warnings.append("Cash is reported by business unit only; not available at department level")
        return {"period": period, "scope": {"business_unit": business_unit, "department": department, "units": units},
                "statement": st, "year_over_year": yoy, "prior_year_period": prior, "budget_comparison": budget,
                "cash": cash, "warnings": warnings, "synthetic": True}

    def year_over_year(self, period: str, business_unit=None, department=None) -> Dict[str, Any]:
        prior = add_months(period, -12)
        act = self._filter(self.repo.get_ledger("actual"), None, business_unit, department)
        cur = act[act["period"] == period].assign(source="current")
        pri = act[act["period"] == prior].assign(source="prior_year", period=period)
        res = compare_sources(pd.concat([cur, pri]), "current", "prior_year")
        res["prior_year_period"] = prior
        return res

    def trend(self, business_unit=None, department=None, source="actual") -> Dict[str, Any]:
        self.validate_scope(None, business_unit, department, source)
        df = self._filter(self.repo.get_ledger(source), None, business_unit, department)
        rows = build_statements(df, ["period"])
        for r in rows:
            sub = df[df["period"] == r["period"]]
            r["units"] = sorted({f"{a} / {b}" for a, b in zip(sub["business_unit"], sub["department"])})
        counts = [len(r["units"]) for r in rows]
        mode = max(set(counts), key=counts.count) if counts else 0
        warnings = []
        changed = [r["period"] for r in rows if len(r["units"]) != mode]
        if changed:
            warnings.append(f"Reporting-unit coverage differs in {', '.join(changed)}; totals in those periods are not like-for-like")
        return {"source": source, "scope": {"business_unit": business_unit, "department": department},
                "rows": rows, "warnings": warnings}

    def rollup(self, source="actual", periods=None, business_unit=None, department=None,
               group_by: str = "department") -> Dict[str, Any]:
        if group_by not in ("business_unit", "department", "business_unit_department", "period"):
            raise InvalidRequest("group_by must be business_unit, department, business_unit_department or period")
        self.validate_scope(periods, business_unit, department, source)
        df = self._filter(self.repo.get_ledger(source), periods, business_unit, department)
        cols = ["business_unit", "department"] if group_by == "business_unit_department" else [group_by]
        groups = build_statements(df, cols)
        total = build_statements(df, [])
        check = None
        if groups and total:
            s = sum(g["revenue"] or 0 for g in groups)
            check = {"check": "group revenue sums to total", "difference": s - (total[0]["revenue"] or 0),
                     "passed": abs(s - (total[0]["revenue"] or 0)) <= RECONCILIATION_TOLERANCE}
        return {"source": source, "group_by": group_by, "periods": periods or sorted(df["period"].unique().tolist()),
                "scope": {"business_unit": business_unit, "department": department}, "groups": groups,
                "total": total[0] if total else None, "rollup_check": check,
                "warnings": [] if periods else ["No period filter: totals span all periods with differing unit coverage"]}

    def variance(self, comparison="actual_vs_budget", periods=None, business_unit=None, department=None,
                 group_by: Optional[str] = None, line_type: Optional[str] = None) -> Dict[str, Any]:
        if comparison == "year_over_year":
            if not periods or len(periods) != 1:
                raise InvalidRequest("year_over_year requires exactly one period")
            self.validate_scope(periods, business_unit, department)
            res = self.year_over_year(periods[0], business_unit, department)
        else:
            if comparison not in COMPARISONS:
                raise InvalidRequest(f"Unknown comparison '{comparison}'. Valid: {', '.join(COMPARISONS)}, year_over_year")
            if group_by not in (None, "business_unit", "department"):
                raise InvalidRequest("group_by must be business_unit or department")
            self.validate_scope(periods, business_unit, department)
            led = self._filter(self.repo.get_ledger(), periods, business_unit, department)
            if line_type == "revenue":
                led = led[led["financial_line"] == "revenue"]
            elif line_type == "expense":
                led = led[led["financial_line"].isin(["cogs"] + OPEX_LINES)]
            cur, cmp_ = COMPARISONS[comparison]
            res = compare_sources(led, cur, cmp_, group_by)
        res.update(comparison=comparison, scope={"periods": periods, "business_unit": business_unit,
                                                 "department": department, "line_type": line_type},
                   convention="variance = current - comparison; % = variance / |comparison|; expense increases are unfavourable")
        return res

    # ---------- forecast / drivers / cash ----------
    def forecast(self, horizon: int = 12) -> Dict[str, Any]:
        res = run_model(self.inputs, {}, None, horizon)
        ref = self.repo.get_ledger("forecast")
        gen = []
        for u in res["units"]:
            for r in u["rows"]:
                for l in ALL_LINES:
                    if r.get(l) is not None and l in r:
                        gen.append({"period": r["period"], "business_unit": u["business_unit"],
                                    "department": u["department"], "financial_line": l, "value": r[l], "source": "generated"})
        cmp_ = compare_sources(pd.concat([pd.DataFrame(gen), ref]), "generated", "forecast", "department")
        hist = self.trend(None, None, "actual")
        drivers = DriverAnalyzer().analyze(self.repo.drivers, self.repo.get_ledger("actual"))
        return {"method": METHOD, "base_period": res["base_period"], "forecast_periods": res["periods"],
                "historical_periods": self.repo.periods("actual"), "projection": res,
                "reference_forecast_comparison": cmp_, "drivers": drivers,
                "assumptions": [{"key": t["department"], **{k: t[k] for k in ("baseline_annual_revenue_growth",
                                 "growth_reference_period", "baseline_cogs_ratio", "baseline_annual_opex_growth")}}
                                for t in res["trace"]],
                "warnings": list(self.inputs.warnings),
                "limitations": ["Assumption-driven projection; not statistically validated.",
                                "Growth rates come from a single same-month YoY observation per unit.",
                                "Reference forecast (forecast.csv) is preserved and compared, never overwritten."],
                "historical_series": hist["rows"]}

    def drivers(self) -> Dict[str, Any]:
        return DriverAnalyzer().analyze(self.repo.drivers, self.repo.get_ledger("actual"))

    def cash_flow(self, business_unit: Optional[str] = None, horizon: int = 12) -> Dict[str, Any]:
        self.validate_scope(None, business_unit)
        hist = CashFlowAnalyzer().history(self.repo.cash_flow, self.repo.latest_actual_period(), business_unit)
        proj = None
        anchor_bus = {a.business_unit for a in self.inputs.cash_anchors}
        if business_unit is None or business_unit in anchor_bus:
            proj = run_model(self.inputs, {}, None, horizon)["cash"]
        return {"history": hist, "projection": proj, "projection_scope": sorted(anchor_bus),
                "warnings": hist["warnings"] + ([] if proj else [f"No projection for {business_unit}: outside projection scope"])}
