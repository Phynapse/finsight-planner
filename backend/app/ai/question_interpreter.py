"""Question interpretation -> constrained AnalysisPlan.

Rule-based interpretation is always available. When an LLM provider is configured it is asked for a
JSON plan (never an answer); the plan is strictly validated and any failure falls back to rules.
"""
import json
import logging
import re
from typing import Dict, Any, List, Optional

from pydantic import ValidationError

from ..schemas.analysis import AnalysisPlan, ANALYSIS_TYPES
from .providers.base import LLMProvider, Message, ProviderError

logger = logging.getLogger("finsight.ai")

EXAMPLES = [
    "How did revenue perform against budget?",
    "Which departments had the largest unfavorable expense variances?",
    "Why is operating income below budget?",
    "What happens to operating income if revenue growth is two percentage points lower?",
    "Compare the downside scenario with the baseline.",
    "How does the projected ending cash balance change under the downside scenario?",
    "Which assumptions have the largest impact on profitability?",
    "Give me a financial summary for 2026-09.",
    "Show the forecast.",
]
NUM_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
             "ten": 10, "fifteen": 15, "twenty": 20, "half a": 0.5}
SCENARIO_WORDS = [("downside", "downside"), ("upside", "upside"), ("expense reduction", "expense_reduction"),
                  ("cost reduction", "expense_reduction"), ("management intervention", "expense_reduction"),
                  ("intervention", "expense_reduction"), ("baseline", "baseline")]
NEG = r"(lower|less|fall|falls|drop|drops|decline|declines|decrease|decreases|cut|cuts|reduce|reduced|reduction|down|slower|weaker)"
# (assumption key, keyword regex, accepted unit kind)
WHAT_IF_PATTERNS = [
    ("opex_growth_adj", r"(opex|operating expense|expense) growth", "pp"),
    ("revenue_growth_adj", r"(?<!opex )(?<!expense )(revenue\s+)?growth", "pp"),
    ("customer_count_pct", r"customer(s| count)", "pct"),
    ("revenue_level_pct", r"(revenue|sales)(?!\s+growth)", "pct"),
    ("cogs_ratio_adj", r"(cogs|cost of goods)( ratio)?", "pp"),
    ("headcount_pct", r"headcount", "pct"),
    ("compensation_pct", r"(compensation|salar(y|ies)|wages|payroll)", "pct"),
    ("marketing_pct", r"marketing", "pct"),
    ("technology_pct", r"technology", "pct"),
    ("collection_days", r"(collection(s)?( period| days)?|dso)", "days"),
]


class InterpretationResult:
    def __init__(self, plan: Optional[AnalysisPlan], method: str, unsupported_reason: Optional[str] = None,
                 llm_status: str = "not_configured"):
        self.plan, self.method, self.unsupported_reason, self.llm_status = plan, method, unsupported_reason, llm_status

    def to_dict(self):
        return {"plan": self.plan.model_dump() if self.plan else None, "method": self.method,
                "unsupported_reason": self.unsupported_reason, "llm_status": self.llm_status}


class QuestionInterpreter:
    def __init__(self, business_units: List[str], departments: List[str], periods: List[str],
                 provider: Optional[LLMProvider] = None):
        self.business_units, self.departments, self.periods = business_units, departments, periods
        self.provider = provider

    # Backward-compatible synchronous rule-based interface
    def interpret(self, question: str) -> InterpretationResult:
        return self.interpret_rules(question)

    async def interpret_async(self, question: str) -> InterpretationResult:
        if self.provider is None or not self.provider.is_configured:
            return self.interpret_rules(question)
        try:
            plan = await self._interpret_llm(question)
            if plan is None:
                r = self.interpret_rules(question)
                r.llm_status = "llm_reported_unsupported"
                return r
            return InterpretationResult(plan, "llm", llm_status="ok")
        except (ProviderError, ValidationError, ValueError) as e:
            logger.warning("LLM interpretation unusable (%s); using rule-based interpretation", type(e).__name__)
            r = self.interpret_rules(question)
            r.llm_status = f"fallback: {type(e).__name__}"
            return r

    async def _interpret_llm(self, question: str) -> Optional[AnalysisPlan]:
        system = (
            "You convert finance questions into a JSON analysis plan. Never answer the question, never compute numbers, "
            "never output code. Respond with ONE JSON object only. If unsupported respond {\"unsupported\": true}.\n"
            f"analysis_type: one of {ANALYSIS_TYPES}\n"
            "metric: revenue|cogs|gross_profit|operating_expenses|operating_income|gross_margin_pct|operating_margin_pct|ending_cash|null\n"
            "comparison: actual_vs_budget|actual_vs_forecast|forecast_vs_budget|year_over_year|null\n"
            f"business_unit: one of {self.business_units} or null\ndepartment: one of {self.departments} or null\n"
            f"periods: list of YYYY-MM from {self.periods} (empty = default)\n"
            "dimension: business_unit|department|null; line_type: revenue|expense|all|null\n"
            "scenario_id: baseline|upside|downside|expense_reduction|null\n"
            "assumptions: list of {key, value, department?} with keys revenue_growth_adj (annual pp decimal), revenue_level_pct, "
            "customer_count_pct, cogs_ratio_adj, opex_growth_adj, compensation_pct, headcount_pct, marketing_pct, technology_pct "
            "(relative decimals), collection_days (days). Only for analysis_type what_if.\n"
            "horizon_months: 1-24 (default 12); reasoning_goal: short string.")
        resp = await self.provider.complete([Message("system", system), Message("user", question[:500])],
                                            temperature=0, max_tokens=400)
        text = resp.content.strip()
        text = re.sub(r"^```(json)?|```$", "", text, flags=re.M).strip()
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("plan is not an object")
        if data.get("unsupported"):
            return None
        data = {k: v for k, v in data.items() if v is not None}
        return AnalysisPlan.model_validate(data)

    # ------------------------------------------------------------------ rules
    def interpret_rules(self, question: str) -> InterpretationResult:
        q = " " + question.lower().strip() + " "
        for w, n in NUM_WORDS.items():
            q = re.sub(rf"\b{w}\b", str(n), q)
        f: Dict[str, Any] = {}
        periods = re.findall(r"\b(20\d{2}-(?:0[1-9]|1[0-2]))\b", q)
        if not periods:
            years = set(re.findall(r"\b(20\d{2})\b", q))
            periods = [p for p in self.periods if p[:4] in years]
            if years and not periods:
                return InterpretationResult(None, "rule_based", f"No actual periods found for {', '.join(sorted(years))}. "
                                            f"Available: {self.periods[0]} to {self.periods[-1]}.")
        f["periods"] = periods
        for bu in self.business_units:
            if bu.lower() in q or (bu == "Asia Pacific" and "apac" in q):
                f["business_unit"] = bu
        aliases = {"Engineering & Product": ["engineering"], "Customer Success": ["customer success"],
                   "Sales & Marketing": ["sales & marketing", "sales and marketing"]}
        for d in self.departments:
            if d.lower() in q or any(a in q for a in aliases.get(d, [])):
                f["department"] = d
        for w, sid in SCENARIO_WORDS:
            if w in q:
                f["scenario_id"] = sid
                break
        if "this scenario" in q and "scenario_id" not in f:
            return InterpretationResult(None, "rule_based", "Please name the scenario (downside, upside, expense_reduction).")
        f["metric"] = self._metric(q)
        plan_type = self._intent(q, f)
        if plan_type is None:
            return InterpretationResult(None, "rule_based", "The question does not match a supported analysis.")
        if isinstance(plan_type, str) and plan_type.startswith("!"):
            return InterpretationResult(None, "rule_based", plan_type[1:])
        f["analysis_type"] = plan_type
        try:
            plan = AnalysisPlan.model_validate({k: v for k, v in f.items() if v is not None})
        except ValidationError as e:
            return InterpretationResult(None, "rule_based", f"Could not build a valid plan: {e.errors()[0]['msg']}")
        return InterpretationResult(plan, "rule_based")

    @staticmethod
    def _metric(q: str) -> Optional[str]:
        for pat, m in [(r"operating margin", "operating_margin_pct"), (r"gross margin", "gross_margin_pct"),
                       (r"gross profit", "gross_profit"), (r"operating income|\bebit\b|\bprofit\b", "operating_income"),
                       (r"ending cash|cash balance", "ending_cash"), (r"\bcogs\b|cost of goods", "cogs"),
                       (r"expense|opex|spend|cost", "operating_expenses"), (r"revenue|\bsales\b(?! &| and)", "revenue")]:
            if re.search(pat, q):
                return m
        return None

    def _what_if(self, q: str) -> List[Dict[str, Any]]:
        out, used = [], set()
        for key, kw, kind in WHAT_IF_PATTERNS:
            m = re.search(rf"{kw}[^.?;\d]*?(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>%|percent(?:age points?)?|pp|points?|days)?", q)
            if not m or key in used:
                continue
            if key == "revenue_level_pct" and "revenue_growth_adj" in used:
                continue
            num, unit = float(m.group("num")), (m.group("unit") or "")
            if kind == "days":
                if "day" not in unit:
                    continue
                value = num  # replacement value in days
            else:
                if not unit:
                    continue
                if kind == "pct" and "point" in unit or unit == "pp":
                    if kind == "pct":
                        continue  # percentage points are not a relative change for this assumption
                window = q[max(0, m.start() - 40): m.end() + 30]
                sign = -1 if re.search(NEG, window) else 1
                value = sign * num / 100
            out.append({"key": key, "value": value})
            used.add(key)
        return out

    def _intent(self, q: str, f: Dict[str, Any]):
        has = lambda *ws: any(re.search(w, q) for w in ws)
        if has(r"assumption", r"sensitiv") and has(r"impact", r"largest", r"most", r"biggest", r"effect", r"sensitiv", r"matter"):
            return "sensitivity_analysis"
        if has(r"what happens", r"what if", r"what would", r"\bif\b", r"suppose", r"assuming"):
            a = self._what_if(q)
            if a:
                f["assumptions"] = a
                if f.get("department"):
                    for x in a:
                        if x["key"] != "collection_days":
                            x["department"] = f["department"]
                f.pop("department", None)
                f.pop("scenario_id", None)
                return "what_if"
            if "scenario_id" not in f:
                return "!This what-if question has no recognised assumption change. Supported example: 'What happens to operating income if revenue growth is 2 percentage points lower?'"
        if "scenario_id" in f and f["scenario_id"] != "baseline" or (has(r"scenario") and "scenario_id" in f):
            if f.get("scenario_id") == "baseline":
                return "!Name a scenario to compare with the baseline: downside, upside or expense_reduction."
            if has(r"cash"):
                f["metric"] = "ending_cash"
            return "scenario_comparison"
        if has(r"scenario"):
            return "!Name a scenario: downside, upside or expense_reduction (management intervention)."
        if has(r"\bcash\b", r"liquidity", r"collections"):
            return "cash_flow_analysis"
        if has(r"driver"):
            return "driver_analysis"
        if has(r"forecast", r"projection", r"outlook", r"next 12", r"project") and not has(r"budget", r"variance", r"actual"):
            return "forecast_analysis"
        if has(r"department", r"business unit", r"\bunits?\b", r"\bwhich\b") and has(r"variance", r"over budget", r"unfavo", r"overspen", r"largest", r"expense", r"budget"):
            f["dimension"] = "business_unit" if has(r"business unit", r"region") else "department"
            f["line_type"] = "revenue" if f.get("metric") == "revenue" else "expense"
            f["comparison"] = self._comparison(q)
            f.pop("metric", None)
            return "dimension_comparison"
        if has(r"budget", r"variance", r"against", r"\bvs\b", r"versus", r"below", r"above", r"\bmiss", r"\bwhy\b",
               r"last year", r"prior year", r"year over year", r"\byoy\b", r"compared"):
            f["comparison"] = self._comparison(q)
            if f["comparison"] == "year_over_year" and len(f.get("periods", [])) != 1:
                f["periods"] = [self.periods[-1]]
            if f.get("metric") == "revenue":
                f["line_type"] = "revenue"
            return "variance_analysis"
        if has(r"margin", r"profitab"):
            return "profitability_analysis"
        if has(r"summary", r"overview", r"perform", r"how are we", r"\bkpi", r"revenue", r"operating income", r"how did", r"results"):
            if len(f.get("periods", [])) > 1:
                f["periods"] = f["periods"][-1:]
            return "financial_summary"
        return None

    @staticmethod
    def _comparison(q: str) -> str:
        if re.search(r"last year|prior year|year over year|\byoy\b|previous year", q):
            return "year_over_year"
        if "forecast" in q and "budget" in q:
            return "forecast_vs_budget"
        if "forecast" in q:
            return "actual_vs_forecast"
        return "actual_vs_budget"
