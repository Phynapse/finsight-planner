"""Analysis planner: validates a constrained AnalysisPlan against the dataset and executes it through
an explicit allowlist of deterministic operations. Each operation returns computed results, an
evidence package and deterministic findings. No LLM is involved here."""
from typing import Dict, Any, List, Optional, Callable

from ..schemas.analysis import AnalysisPlan, ANALYSIS_TYPES
from ..scenarios.assumptions import AssumptionError
from ..services.evidence_service import EvidenceService
from ..services.financial_service import FinancialService, InvalidRequest
from ..services.scenario_service import ScenarioService, ScenarioNotFound

LABELS = {"revenue": "Revenue", "cogs": "COGS", "gross_profit": "Gross profit", "operating_expenses": "Operating expenses",
          "operating_income": "Operating income", "gross_margin_pct": "Gross margin", "operating_margin_pct": "Operating margin",
          "ending_cash": "Ending cash", "minimum_cash": "Minimum cash balance"}
CMP_LABEL = {"actual_vs_budget": "budget", "actual_vs_forecast": "forecast", "forecast_vs_budget": "budget",
             "year_over_year": "the same month of the prior year"}
CMP_DATASETS = {"actual_vs_budget": ["actuals", "budget"], "actual_vs_forecast": ["actuals", "forecast"],
                "forecast_vs_budget": ["forecast", "budget"], "year_over_year": ["actuals"]}
CAUSAL_CAVEAT = ("Variances are calculated differences; the dataset does not establish their underlying causes "
                 "(e.g. volume, price, timing or efficiency).")


class PlanError(ValueError):
    pass


def usd(v: Optional[float]) -> str:
    if v is None:
        return "n/a"
    return f"-${abs(v):,.0f}" if v < 0 else f"${v:,.0f}"


def signed_usd(v: Optional[float]) -> str:
    return "n/a" if v is None else ("+" if v >= 0 else "-") + f"${abs(v):,.0f}"


def pct(v: Optional[float], signed=True) -> str:
    if v is None:
        return "n/a"
    return f"{v:+.1f}%" if signed else f"{v:.1f}%"


def fmt_metric(metric: str, v: Optional[float]) -> str:
    return pct(v, signed=False) if metric.endswith("_pct") else usd(v)


def fmt_change(metric: str, change: Optional[float], pchange: Optional[float]) -> str:
    if metric.endswith("_pct"):
        return "n/a" if change is None else f"{change:+.1f} pp"
    return f"{signed_usd(change)} ({pct(pchange)})"


class AnalysisPlanner:
    def __init__(self, financial: FinancialService, scenarios: ScenarioService, evidence: EvidenceService):
        self.fin, self.scen, self.ev = financial, scenarios, evidence
        self.operations: Dict[str, Callable] = {
            "financial_summary": self._summary, "variance_analysis": self._variance,
            "dimension_comparison": self._dimension, "profitability_analysis": self._profitability,
            "scenario_comparison": self._scenario, "what_if": self._what_if,
            "sensitivity_analysis": self._sensitivity, "cash_flow_analysis": self._cash,
            "forecast_analysis": self._forecast, "driver_analysis": self._drivers}
        assert set(self.operations) == set(ANALYSIS_TYPES)

    # Backward-compatible interface
    def plan(self, interpreted_question):
        return interpreted_question

    def validate(self, plan: AnalysisPlan) -> AnalysisPlan:
        if plan.analysis_type not in self.operations:
            raise PlanError(f"Unsupported analysis type '{plan.analysis_type}'")
        try:
            self.fin.validate_scope(plan.periods, plan.business_unit, plan.department)
        except InvalidRequest as e:
            raise PlanError(str(e))
        if plan.analysis_type in ("scenario_comparison",):
            if not plan.scenario_id:
                raise PlanError("Scenario comparison requires a scenario (e.g. downside, upside, expense_reduction)")
            try:
                self.scen._definition(plan.scenario_id)
            except ScenarioNotFound:
                raise PlanError(f"Unknown scenario '{plan.scenario_id}'")
            if plan.scenario_id == "baseline":
                raise PlanError("Choose a scenario to compare against the baseline (downside, upside or expense_reduction)")
        if plan.analysis_type == "what_if":
            if not plan.assumptions:
                raise PlanError("What-if analysis requires at least one supported assumption change")
            try:
                self.scen.engine.validate_assumptions([a.model_dump() for a in plan.assumptions])
            except AssumptionError as e:
                raise PlanError(str(e))
        if plan.comparison == "year_over_year" and len(plan.periods) > 1:
            raise PlanError("Year-over-year comparison accepts a single period")
        return plan

    def execute(self, plan: AnalysisPlan, question: Optional[str] = None) -> Dict[str, Any]:
        self.validate(plan)
        out = self.operations[plan.analysis_type](plan, question)
        out["plan"] = plan.model_dump()
        return out

    # ------------------------------------------------------------------ operations
    def _scope(self, plan, **extra):
        s = {"periods": plan.periods or None, "business_unit": plan.business_unit, "department": plan.department}
        s.update(extra)
        return s

    def _summary(self, plan, q):
        period = plan.periods[0] if plan.periods else None
        s = self.fin.summary(period, plan.business_unit, plan.department)
        st, p = s["statement"], s["period"]
        dim = " | ".join(s["scope"]["units"])
        items = [{"metric": m, "value": st[m], "unit": "%" if m.endswith("_pct") else "USD", "period": p, "dimension": dim,
                  "source_dataset": "actuals", "kind": "source" if m in ("revenue", "cogs") else "calculated",
                  "formula_id": f"F-{m.upper()}", "calculation_description": FORMULAS.get(m, "Sum of reported records")}
                 for m in LABELS if m in st and st[m] is not None]
        yoy = s["year_over_year"]
        if yoy.get("statement"):
            for m in ("revenue", "operating_income"):
                v = yoy["statement"][m]
                items.append({"metric": f"{m}_yoy_matched", "value": v["value"], "comparison_value": v["comparison_value"],
                              "absolute_change": v["absolute_variance"], "percentage_change": v["percentage_variance"],
                              "period": f"{p} vs {s['prior_year_period']}", "dimension": "matched records",
                              "source_dataset": "actuals", "assessment": v["assessment"], "formula_id": "F-VARIANCE",
                              "calculation_description": "Current - prior-year same month, on records reported in both periods"})
        if s["cash"]:
            items.append({"metric": "ending_cash", "value": s["cash"]["ending_cash"], "period": p,
                          "dimension": ", ".join(s["cash"]["business_units"]), "source_dataset": "cash_flow", "kind": "source",
                          "calculation_description": "Reported ending_cash (see cash-flow reconciliation warnings)"})
        recon = [_oi_check(st)]
        pkg = self.ev.build("financial_summary", self._scope(plan, periods=[p]), items,
                            ["actuals", "cash_flow"] if s["cash"] else ["actuals"], q, reconciliation=recon,
                            warnings=s["warnings"])
        findings = [f"{LABELS[m]}: {fmt_metric(m, st[m])}" for m in
                    ("revenue", "gross_profit", "operating_expenses", "operating_income", "operating_margin_pct") if st.get(m) is not None]
        if yoy.get("statement"):
            r = yoy["statement"]["revenue"]
            findings.append(f"Revenue vs {s['prior_year_period']} (matched records): {fmt_change('revenue', r['absolute_variance'], r['percentage_variance'])}")
        if s["cash"]:
            findings.append(f"Reported ending cash ({', '.join(s['cash']['business_units'])}): {usd(s['cash']['ending_cash'])}")
        head = (f"In {p} ({dim}), revenue was {usd(st['revenue'])} and operating income {usd(st['operating_income'])} "
                f"(operating margin {pct(st['operating_margin_pct'], False)}).")
        return {"result": s, "evidence": pkg, "headline": head, "findings": findings,
                "follow_ups": ["How did operating income perform against budget?", "Show cash flow"]}

    def _variance(self, plan, q):
        comp = plan.comparison or "actual_vs_budget"
        v = self.fin.variance(comp, plan.periods or None, plan.business_unit, plan.department, None, plan.line_type)
        items, recon, findings = [], [], []
        per = ", ".join(v["matched_periods"]) or "none"
        if v["statement"]:
            for m, s in v["statement"].items():
                items.append({"metric": m, "value": s["value"], "comparison_value": s["comparison_value"],
                              "absolute_change": s["absolute_variance"], "percentage_change": s["percentage_variance"],
                              "unit": "%" if m.endswith("_pct") else "USD", "period": per, "dimension": "matched records",
                              "source_dataset": CMP_DATASETS[comp][0], "comparison_source": CMP_DATASETS[comp][-1],
                              "assessment": s["assessment"], "formula_id": "F-VARIANCE",
                              "calculation_description": "current - comparison on matched records; % = variance / |comparison|"})
            b = v["bridge"]
            for k in ("revenue_contribution", "cogs_contribution", "operating_expense_contribution"):
                items.append({"metric": f"oi_bridge_{k}", "value": b[k], "period": per, "dimension": "matched records",
                              "source_dataset": CMP_DATASETS[comp][0], "comparison_source": CMP_DATASETS[comp][-1],
                              "formula_id": "F-OI-BRIDGE", "calculation_description": b["formula"]})
            recon.append({"check": "operating income variance bridge", "status": "passed" if b["reconciled"] else "failed",
                          "difference": b["reconciliation_difference"], "tolerance": b["tolerance"],
                          "detail": f"calculated {b['calculated_operating_income_variance']:,.2f} vs actual difference "
                                    f"{b['actual_operating_income_difference']:,.2f}"})
            for r in v["material_variances"][:5]:
                items.append({"metric": r["metric"], "value": r["value"], "comparison_value": r["comparison_value"],
                              "absolute_change": r["absolute_variance"], "percentage_change": r["percentage_variance"],
                              "period": r["period"], "dimension": f"{r['business_unit']} | {r['department']}",
                              "source_dataset": CMP_DATASETS[comp][0], "comparison_source": CMP_DATASETS[comp][-1],
                              "assessment": r["assessment"], "kind": "source", "formula_id": "F-VARIANCE",
                              "calculation_description": "Line-level variance (material: |var| >= 10,000 and |%| >= 5)"})
            metric = plan.metric if plan.metric in v["statement"] else "operating_income"
            s = v["statement"][metric]
            head = (f"{LABELS[metric]} was {fmt_metric(metric, s['value'])} against {CMP_LABEL[comp]} of "
                    f"{fmt_metric(metric, s['comparison_value'])}, a variance of "
                    f"{fmt_change(metric, s['absolute_variance'], s['percentage_variance'])} ({s['assessment']}), "
                    f"across {v['matched_records']} matched records in {per}.")
            for m in ("revenue", "cogs", "operating_expenses", "operating_income"):
                s2 = v["statement"][m]
                findings.append(f"{LABELS[m]}: {fmt_change(m, s2['absolute_variance'], s2['percentage_variance'])} vs {CMP_LABEL[comp]} ({s2['assessment']})")
            findings.append(f"Operating-income bridge: revenue {signed_usd(b['revenue_contribution'])}, COGS "
                            f"{signed_usd(b['cogs_contribution'])}, operating expenses {signed_usd(b['operating_expense_contribution'])} "
                            f"= {signed_usd(b['calculated_operating_income_variance'])} (reconciled: {b['reconciled']})")
            for r in v["material_variances"][:3]:
                findings.append(f"Material: {r['business_unit']} / {r['department']} {r['metric']} {r['period']}: "
                                f"{fmt_change(r['metric'], r['absolute_variance'], r['percentage_variance'])} ({r['assessment']})")
        else:
            head = f"No overlapping {comp.replace('_', ' ')} records exist for the requested scope, so no variance can be calculated."
        warns = v["warnings"] + [CAUSAL_CAVEAT,
                                 f"{v.get('unmatched_current_records', 0)} current and {v.get('unmatched_comparison_records', 0)} "
                                 "comparison records had no counterpart and were excluded."]
        pkg = self.ev.build("variance_analysis", self._scope(plan, comparison=comp, line_type=plan.line_type), items,
                            CMP_DATASETS[comp], q, reconciliation=recon, warnings=warns)
        return {"result": v, "evidence": pkg, "headline": head, "findings": findings,
                "follow_ups": ["Which departments had the largest unfavorable expense variances?"]}

    def _dimension(self, plan, q):
        comp = plan.comparison or "actual_vs_budget"
        dim = plan.dimension or "department"
        line_type = plan.line_type or "expense"
        v = self.fin.variance(comp, plan.periods or None, plan.business_unit, plan.department, dim, line_type)
        agg: Dict[str, Dict[str, float]] = {}
        for r in v["line_variances"]:
            a = agg.setdefault(r[dim], {"value": 0.0, "comparison": 0.0})
            a["value"] += r["value"]
            a["comparison"] += r["comparison_value"]
        from ..analytics.calculations import calculate_variance, classify_variance
        rows = []
        for k, a in agg.items():
            d, p = calculate_variance(a["value"], a["comparison"])
            metric = "operating_expenses" if line_type == "expense" else ("revenue" if line_type == "revenue" else "net_lines")
            rows.append({dim: k, "value": a["value"], "comparison_value": a["comparison"], "absolute_variance": d,
                         "percentage_variance": p, "assessment": classify_variance(metric, d)})
        # most unfavourable first: for expenses largest positive variance; for revenue most negative
        rows.sort(key=lambda r: -r["absolute_variance"] if line_type != "revenue" else r["absolute_variance"])
        label = "expense (COGS + operating expenses)" if line_type == "expense" else line_type
        items = [{"metric": f"{line_type}_variance", "value": r["value"], "comparison_value": r["comparison_value"],
                  "absolute_change": r["absolute_variance"], "percentage_change": r["percentage_variance"],
                  "period": ", ".join(v["matched_periods"]), "dimension": r[dim], "source_dataset": CMP_DATASETS[comp][0],
                  "comparison_source": CMP_DATASETS[comp][-1], "assessment": r["assessment"], "formula_id": "F-VARIANCE",
                  "calculation_description": f"Sum of matched {label} lines by {dim}; current - comparison"} for r in rows]
        top_lines = sorted([r for r in v["line_variances"] if r["assessment"] == "unfavourable"],
                           key=lambda r: -abs(r["absolute_variance"]))[:5]
        for r in top_lines:
            items.append({"metric": r["metric"], "value": r["value"], "comparison_value": r["comparison_value"],
                          "absolute_change": r["absolute_variance"], "percentage_change": r["percentage_variance"],
                          "period": r["period"], "dimension": f"{r['business_unit']} | {r['department']}", "kind": "source",
                          "source_dataset": CMP_DATASETS[comp][0], "comparison_source": CMP_DATASETS[comp][-1],
                          "assessment": r["assessment"], "formula_id": "F-VARIANCE", "calculation_description": "Line-level variance"})
        unf = [r for r in rows if r["assessment"] == "unfavourable"]
        if not rows:
            head = "No matched records exist for this comparison and scope."
        elif unf:
            r = unf[0]
            head = (f"The largest unfavourable {label} variance vs {CMP_LABEL[comp]} is {r[dim]}: "
                    f"{fmt_change('x', r['absolute_variance'], r['percentage_variance'])} "
                    f"({usd(r['value'])} vs {usd(r['comparison_value'])}).")
        else:
            head = f"No {dim} shows an unfavourable {label} variance vs {CMP_LABEL[comp]} on matched records."
        findings = [f"{r[dim]}: {fmt_change('x', r['absolute_variance'], r['percentage_variance'])} ({r['assessment']})" for r in rows]
        findings += [f"Line: {r['business_unit']} / {r['department']} {r['metric']} {r['period']}: "
                     f"{fmt_change('x', r['absolute_variance'], r['percentage_variance'])}" for r in top_lines[:3]]
        pkg = self.ev.build("dimension_comparison", self._scope(plan, comparison=comp, dimension=dim, line_type=line_type),
                            items, CMP_DATASETS[comp], q, warnings=v["warnings"] + [CAUSAL_CAVEAT])
        return {"result": {"ranking": rows, "variance": v}, "evidence": pkg, "headline": head, "findings": findings,
                "follow_ups": ["Why is operating income below budget?"]}

    def _profitability(self, plan, q):
        periods = plan.periods or [self.fin.repo.latest_actual_period()]
        dim = plan.dimension or "department"
        r = self.fin.rollup("actual", periods, plan.business_unit, plan.department, dim)
        items = []
        for g in r["groups"] + ([dict(r["total"], **{dim: "Total"})] if r["total"] else []):
            for m in ("revenue", "gross_profit", "operating_income", "gross_margin_pct", "operating_margin_pct"):
                if g.get(m) is not None:
                    items.append({"metric": m, "value": g[m], "unit": "%" if m.endswith("_pct") else "USD",
                                  "period": ", ".join(periods), "dimension": g[dim], "source_dataset": "actuals",
                                  "formula_id": f"F-{m.upper()}", "calculation_description": FORMULAS[m]})
        t = r["total"] or {}
        head = (f"For {', '.join(periods)}, gross margin was {pct(t.get('gross_margin_pct'), False)} and operating margin "
                f"{pct(t.get('operating_margin_pct'), False)} on revenue of {usd(t.get('revenue'))}.")
        findings = [f"{g[dim]}: gross margin {pct(g['gross_margin_pct'], False)}, operating margin {pct(g['operating_margin_pct'], False)}, "
                    f"operating income {usd(g['operating_income'])}" for g in r["groups"]]
        warns = [f"{u['unit']} missing {', '.join(u['missing_lines'])}" for g in r["groups"] for u in g["units_with_missing_lines"]]
        recon = [_oi_check(t)] if t else []
        if r["rollup_check"]:
            recon.append({"check": r["rollup_check"]["check"], "status": "passed" if r["rollup_check"]["passed"] else "failed",
                          "difference": r["rollup_check"]["difference"], "tolerance": 0.01})
        pkg = self.ev.build("profitability_analysis", self._scope(plan, periods=periods, dimension=dim), items, ["actuals"], q,
                            reconciliation=recon, warnings=warns)
        return {"result": r, "evidence": pkg, "headline": head, "findings": findings,
                "follow_ups": ["How did revenue perform against budget?"]}

    def _scenario_items(self, comparison, periods, name):
        per = f"{periods[0]} to {periods[-1]}"
        return [{"metric": m, "value": c["scenario"], "comparison_value": c["baseline"], "absolute_change": c["absolute_change"],
                 "percentage_change": c["percentage_change"], "unit": "%" if m.endswith("_pct") else "USD", "period": per,
                 "dimension": name, "source_dataset": "model", "comparison_source": "model (baseline)", "kind": "projection",
                 "assessment": c["assessment"], "formula_id": "F-SCENARIO-DELTA",
                 "calculation_description": "Scenario projection - baseline projection (horizon totals; cash = final month)"}
                for m, c in comparison.items() if c["scenario"] is not None]

    def _scenario_out(self, result, comparison, name, plan, q, atype, assumptions):
        periods = result["periods"]
        items = self._scenario_items(comparison, periods, name)
        cash_ok = result["cash"]["reconciled"]
        recon = [{"check": "projected cash: ending = opening + inflows - outflows",
                  "status": "passed" if cash_ok else ("failed" if cash_ok is False else "not_applicable"), "tolerance": 0.01}]
        oi, cash = comparison["operating_income"], comparison["ending_cash"]
        head = (f"Over {periods[0]} to {periods[-1]}, {name} changes projected operating income by "
                f"{fmt_change('x', oi['absolute_change'], oi['percentage_change'])} versus the baseline")
        head += (f" and ending cash by {fmt_change('x', cash['absolute_change'], cash['percentage_change'])}." if cash["scenario"] is not None else ".")
        if plan.metric == "ending_cash" and cash["scenario"] is not None:
            head = (f"Under {name}, projected ending cash in {periods[-1]} is {usd(cash['scenario'])} vs {usd(cash['baseline'])} "
                    f"in the baseline ({fmt_change('x', cash['absolute_change'], cash['percentage_change'])}).")
        findings = [f"{LABELS[m]}: {fmt_metric(m, c['scenario'])} vs baseline {fmt_metric(m, c['baseline'])} "
                    f"({fmt_change(m, c['absolute_change'], c['percentage_change'])})" for m, c in comparison.items() if c["scenario"] is not None]
        findings += [f"Assumption: {a['name']} = {a['value']} ({a['unit']}){' for ' + a['department'] if a.get('department') else ''}"
                     for a in assumptions]
        pkg = self.ev.build(atype, self._scope(plan, scenario=name, horizon_months=plan.horizon_months, forecast_periods=periods),
                            items, ["actuals", "cash_flow", "financial_drivers", "scenarios", "model"], q,
                            assumptions=assumptions, reconciliation=recon, warnings=result["caveats"])
        return {"evidence": pkg, "headline": head, "findings": findings,
                "follow_ups": ["Which assumptions have the largest impact on profitability?"]}

    def _scenario(self, plan, q):
        sc = self.scen.get(plan.scenario_id, plan.horizon_months)
        res = sc["result"]
        out = self._scenario_out(res, res["comparison_against_baseline"], sc["name"], plan, q, "scenario_comparison", res["assumptions"])
        out["result"] = {"scenario_id": plan.scenario_id, "name": sc["name"], "comparison": res["comparison_against_baseline"],
                         "assumptions": res["assumptions"], "periods": res["periods"], "cash": res["cash"]["rows"]}
        return out

    def _what_if(self, plan, q):
        res = self.scen.engine.run([a.model_dump() for a in plan.assumptions], plan.horizon_months)
        out = self._scenario_out(res, res["comparison_against_baseline"], "the what-if case", plan, q, "what_if", res["assumptions"])
        out["result"] = {"comparison": res["comparison_against_baseline"], "assumptions": res["assumptions"], "periods": res["periods"]}
        return out

    def _sensitivity(self, plan, q):
        metric = plan.metric if plan.metric in ("operating_income", "ending_cash", "revenue", "gross_profit") else "operating_income"
        r = self.scen.sensitivity.rank(plan.horizon_months, metric)
        items = []
        for row in r["ranking"]:
            for side in ("low", "high"):
                items.append({"metric": f"{metric}_change", "value": row[f"impact_{side}"], "period": f"{plan.horizon_months}-month horizon",
                              "dimension": f"{row['assumption']} = {row[f'{side}_value']}", "source_dataset": "model", "kind": "projection",
                              "formula_id": "F-SENSITIVITY", "calculation_description": "Projection with one shocked assumption - baseline projection"})
        top = r["ranking"][0]
        head = (f"{top['assumption']} has the largest effect on projected {LABELS[metric].lower()}: "
                f"{signed_usd(top['impact_low'])} at {top['low_value']} and {signed_usd(top['impact_high'])} at {top['high_value']}.")
        findings = [f"{x['assumption']}: {signed_usd(x['impact_low'])} / {signed_usd(x['impact_high'])} (range {usd(x['range'])})" for x in r["ranking"]]
        assumptions = [{"key": x["assumption"], "value": x["low_value"], "note": "low shock"} for x in r["ranking"]] + \
                      [{"key": x["assumption"], "value": x["high_value"], "note": "high shock"} for x in r["ranking"]]
        pkg = self.ev.build("sensitivity_analysis", self._scope(plan, metric=metric), items, ["actuals", "cash_flow", "model"], q,
                            assumptions=assumptions, warnings=[r["method"]] + list(self.fin.inputs.warnings))
        return {"result": r, "evidence": pkg, "headline": head, "findings": findings,
                "follow_ups": ["Compare the downside scenario with the baseline."]}

    def _cash(self, plan, q):
        if plan.scenario_id and plan.scenario_id != "baseline":
            plan = plan.model_copy(update={"analysis_type": "scenario_comparison", "metric": "ending_cash"})
            return self._scenario(plan, q)
        c = self.fin.cash_flow(plan.business_unit, plan.horizon_months)
        hist = [r for r in c["history"]["rows"] if r["status"] == "historical" and not r["duplicate"]]
        items, findings = [], []
        for bu in sorted({r["business_unit"] for r in hist}):
            last = [r for r in hist if r["business_unit"] == bu][-1]
            items.append({"metric": "ending_cash_reported", "value": last["ending_cash_reported"],
                          "comparison_value": last["ending_cash_calculated"], "absolute_change": last["reconciliation_difference"],
                          "period": last["period"], "dimension": bu, "source_dataset": "cash_flow", "kind": "source",
                          "formula_id": "F-CASH-RECON", "calculation_description": "Reported ending cash vs opening + inflows - outflows"})
            findings.append(f"{bu} {last['period']}: reported ending cash {usd(last['ending_cash_reported'])}; components imply "
                            f"{usd(last['ending_cash_calculated'])} (difference {signed_usd(last['reconciliation_difference'])})")
        recon = [{"check": "historical cash rows reconcile", "status": "passed" if c["history"]["reconciled_rows"] == c["history"]["total_rows"] else "failed",
                  "detail": f"{c['history']['reconciled_rows']} of {c['history']['total_rows']} rows reconcile"}]
        head = f"{c['history']['reconciled_rows']} of {c['history']['total_rows']} historical cash rows reconcile to their components."
        p = c["projection"]
        if p and p["rows"]:
            last = p["rows"][-1]
            items.append({"metric": "projected_ending_cash", "value": last["ending_cash"], "comparison_value": p["assumptions"]["opening_cash"],
                          "absolute_change": last["ending_cash"] - p["assumptions"]["opening_cash"], "period": last["period"],
                          "dimension": ", ".join(c["projection_scope"]), "source_dataset": "model", "kind": "projection",
                          "formula_id": "F-CASH-PROJ", "calculation_description": p["assumptions"]["formula"]})
            recon.append({"check": "projected cash: ending = opening + inflows - outflows",
                          "status": "passed" if p["reconciled"] else "failed", "tolerance": 0.01})
            head += (f" Baseline projection: cash moves from {usd(p['assumptions']['opening_cash'])} to {usd(last['ending_cash'])} "
                     f"by {last['period']} ({', '.join(c['projection_scope'])}).")
            findings.append(f"Projected ending cash {last['period']}: {usd(last['ending_cash'])} (collection days {p['assumptions']['collection_days']})")
        pkg = self.ev.build("cash_flow_analysis", self._scope(plan), items, ["cash_flow", "actuals", "model"], q,
                            assumptions=[{"key": k, "value": v} for k, v in (p["assumptions"].items() if p else []) if isinstance(v, (int, float))],
                            reconciliation=recon, warnings=c["warnings"])
        return {"result": c, "evidence": pkg, "headline": head, "findings": findings,
                "follow_ups": ["How does the projected ending cash balance change under the downside scenario?"]}

    def _forecast(self, plan, q):
        f = self.fin.forecast(plan.horizon_months)
        s, per = f["projection"]["summary"], f["forecast_periods"]
        items = [{"metric": m, "value": s[m], "unit": "%" if m.endswith("_pct") else "USD", "period": f"{per[0]} to {per[-1]}",
                  "dimension": "projection scope", "source_dataset": "model", "kind": "projection", "formula_id": "F-PROJECTION",
                  "calculation_description": f"Sum of monthly projections ({f['method']})"}
                 for m in ("revenue", "gross_profit", "operating_expenses", "operating_income", "operating_margin_pct", "ending_cash") if s.get(m) is not None]
        rc = f["reference_forecast_comparison"]
        findings = [f"Projected {LABELS[i['metric']].lower()} {per[0]} to {per[-1]}: {fmt_metric(i['metric'], i['value'])}" for i in items]
        if rc["statement"]:
            for m in ("revenue", "operating_income"):
                v = rc["statement"][m]
                items.append({"metric": f"{m}_vs_reference_forecast", "value": v["value"], "comparison_value": v["comparison_value"],
                              "absolute_change": v["absolute_variance"], "percentage_change": v["percentage_variance"],
                              "period": ", ".join(rc["matched_periods"]), "dimension": "matched records", "source_dataset": "model",
                              "comparison_source": "forecast", "kind": "projection", "formula_id": "F-VARIANCE",
                              "calculation_description": "Generated projection - reference forecast (forecast.csv) on matched records"})
                findings.append(f"Generated vs reference forecast ({', '.join(rc['matched_periods'])}) {LABELS[m].lower()}: "
                                f"{fmt_change(m, v['absolute_variance'], v['percentage_variance'])}")
        assumptions = [{"key": f"{a['key']}: {k}", "value": a[k]} for a in f["assumptions"]
                       for k in ("baseline_annual_revenue_growth", "baseline_cogs_ratio", "baseline_annual_opex_growth")]
        head = (f"The {f['method']} projection from base period {f['base_period']} gives revenue of {usd(s['revenue'])} and operating "
                f"income of {usd(s['operating_income'])} over {per[0]} to {per[-1]}.")
        pkg = self.ev.build("forecast_analysis", self._scope(plan, forecast_periods=per, method=f["method"]), items,
                            ["actuals", "forecast", "cash_flow", "model"], q, assumptions=assumptions,
                            warnings=f["warnings"] + f["limitations"])
        return {"result": {k: v for k, v in f.items() if k != "historical_series"}, "evidence": pkg, "headline": head,
                "findings": findings, "follow_ups": ["Which assumptions have the largest impact on profitability?"]}

    def _drivers(self, plan, q):
        d = self.fin.drivers()
        items = [{"metric": c["relationship"], "value": c["implied_value"], "comparison_value": c.get("actual_value"),
                  "absolute_change": c.get("difference"), "percentage_change": c.get("difference_pct"), "period": c["period"],
                  "dimension": f"{c['business_unit']} | {c['department']}", "source_dataset": "financial_drivers",
                  "comparison_source": "actuals", "formula_id": f"F-{c['relationship'].upper()}", "calculation_description": c["formula"]}
                 for c in d["checks"] if c.get("actual_value") is not None]
        ok = sum(1 for c in d["checks"] if c["status"] == "consistent")
        head = f"{ok} of {len(items)} driver-to-actual checks are consistent within {d['tolerance_pct']}%."
        findings = [f"{c['business_unit']} / {c['department']} {c['period']}: {c['formula']} -> {usd(c['implied_value'])} vs actual "
                    f"{usd(c.get('actual_value'))} ({c['status']})" for c in d["checks"]]
        pkg = self.ev.build("driver_analysis", self._scope(plan), items, ["financial_drivers", "actuals"], q, warnings=d["notes"])
        return {"result": d, "evidence": pkg, "headline": head, "findings": findings, "follow_ups": ["Show the forecast"]}


FORMULAS = {"revenue": "Sum of reported revenue records", "cogs": "Sum of reported COGS records",
            "gross_profit": "Revenue - COGS", "operating_expenses": "Sum of reported operating-expense lines",
            "operating_income": "Gross profit - Operating expenses", "gross_margin_pct": "Gross profit / Revenue x 100",
            "operating_margin_pct": "Operating income / Revenue x 100", "ending_cash": "Reported ending cash"}


def _oi_check(st: Dict[str, Any]) -> Dict[str, Any]:
    if st.get("revenue") is None or st.get("operating_income") is None:
        return {"check": "operating income = revenue - COGS - opex", "status": "not_applicable"}
    diff = st["operating_income"] - (st["revenue"] - st["cogs"] - st["operating_expenses"])
    return {"check": "operating income = revenue - COGS - opex", "status": "passed" if abs(diff) <= 0.01 else "failed",
            "difference": diff, "tolerance": 0.01}
