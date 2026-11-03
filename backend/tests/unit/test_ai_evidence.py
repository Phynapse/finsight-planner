import asyncio
import json

import httpx
import pytest

from app.ai.analysis_planner import PlanError
from app.ai.explanation_generator import extract_numbers, is_grounded_number
from app.ai.providers.base import LLMProvider, CompletionResponse, ProviderError
from app.ai.providers.openai_compatible import OpenAICompatibleProvider
from app.schemas.analysis import AnalysisPlan
from app.services.container import Services
from app.services.evidence_service import EvidenceService, EvidenceError


class FakeProvider(LLMProvider):
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    async def complete(self, messages, **kwargs):
        self.calls += 1
        r = self.responses.pop(0)
        if isinstance(r, Exception):
            raise r
        return CompletionResponse(r)


class Unconfigured(FakeProvider):
    @property
    def is_configured(self):
        return False


def run(c):
    return asyncio.run(c)


@pytest.fixture(scope="module")
def svc():
    return Services(provider=Unconfigured([]))


def test_fallback_without_provider(svc):
    r = run(svc.ask("Why is operating income below budget?"))
    assert r["status"] == "answered" and r["explanation_method"] == "deterministic_fallback"
    assert r["interpretation"]["method"] == "rule_based" and not r["llm_configured"]
    ev = r["evidence"]
    oi = [i for i in ev["items"] if i["metric"] == "operating_income"][0]
    assert oi["absolute_change"] == pytest.approx(oi["value"] - oi["comparison_value"])
    assert ev["reconciliation"][0]["status"] == "passed"
    assert ev["source_datasets"] == ["actuals", "budget"]


def test_unsupported_question_not_routed(svc):
    r = run(svc.ask("What is the capital of France?"))
    assert r["status"] == "unsupported" and r["evidence"] is None and r["supported_examples"]


def test_invalid_plan_rejected(svc):
    with pytest.raises(PlanError):
        svc.planner.execute(AnalysisPlan(analysis_type="financial_summary", business_unit="Mars"))
    with pytest.raises(PlanError):
        svc.planner.execute(AnalysisPlan(analysis_type="scenario_comparison", scenario_id="nope"))
    with pytest.raises(PlanError):
        svc.planner.execute(AnalysisPlan(analysis_type="what_if", assumptions=[{"key": "rm -rf", "value": 1}]))
    with pytest.raises(Exception):
        AnalysisPlan(analysis_type="execute_python")
    with pytest.raises(Exception):
        AnalysisPlan(analysis_type="financial_summary", code="import os")


def test_evidence_scope_and_period(svc):
    out = svc.planner.execute(AnalysisPlan(analysis_type="financial_summary", periods=["2025-06"], business_unit="Europe"))
    ev = out["evidence"]
    assert ev.scope["periods"] == ["2025-06"] and ev.scope["business_unit"] == "Europe"
    rev = [i for i in ev.items if i.metric == "revenue"][0]
    assert rev.value == 540000 and rev.period == "2025-06" and rev.source_dataset == "actuals"
    assert svc.evidence.get(ev.analysis_id) is ev


def test_scenario_evidence_includes_assumptions(svc):
    out = svc.planner.execute(AnalysisPlan(analysis_type="scenario_comparison", scenario_id="downside"))
    keys = {a["key"] for a in out["evidence"].assumptions}
    assert {"revenue_level_pct", "compensation_pct", "collection_days"} <= keys


def test_evidence_validation():
    es = EvidenceService()
    with pytest.raises(EvidenceError):
        es.build("x", {}, [{"metric": "m", "value": float("inf"), "period": "p", "dimension": "d",
                            "source_dataset": "actuals", "calculation_description": "c"}], ["actuals"])
    with pytest.raises(EvidenceError):
        es.build("x", {}, [], ["llm_output"])
    pkg = es.build("x", {}, [], ["actuals"])
    assert not pkg.complete and pkg.missing_data


def test_grounding_number_checks():
    allowed = [1441000.0, -366200.0, -20.26]
    assert all(is_grounded_number(n, allowed) for n in extract_numbers("OI was $1,441,000, down $366,200 (-20.3%), or $1.44M"))
    assert not all(is_grounded_number(n, allowed) for n in extract_numbers("Revenue will grow to $9,999,999"))


def test_llm_plan_and_grounded_explanation():
    plan = json.dumps({"analysis_type": "variance_analysis", "metric": "operating_income", "comparison": "actual_vs_budget"})
    s = Services(provider=FakeProvider([plan, "placeholder"]))
    # second response must quote evidence numbers; build it from a deterministic run
    det = s.planner.execute(AnalysisPlan.model_validate_json(plan))
    oi = [i for i in det["evidence"].items if i.metric == "operating_income"][0]
    s.provider.responses = [plan, json.dumps({"answer": f"Operating income was ${oi.value:,.0f} versus ${oi.comparison_value:,.0f} budgeted.",
                                              "key_findings": [f"Variance {oi.absolute_change:,.0f}"], "caveats": []})]
    r = run(s.ask("explain op income vs plan please"))
    assert r["interpretation"]["method"] == "llm" and r["explanation_method"] == "llm"
    assert r["explanation"]["computed_findings"]


def test_llm_ungrounded_figures_rejected():
    plan = json.dumps({"analysis_type": "variance_analysis", "metric": "operating_income"})
    s = Services(provider=FakeProvider([plan, json.dumps({"answer": "Operating income will reach $12,345,678 next year."})]))
    r = run(s.ask("operating income vs budget"))
    assert r["explanation_method"] == "deterministic_fallback"
    assert r["explanation"]["llm_status"] == "rejected_ungrounded_figures"


@pytest.mark.parametrize("responses", [
    [ProviderError("timeout"), ProviderError("timeout")],
    ["not json at all", "{bad"],
    [json.dumps({"analysis_type": "run_sql", "query": "DROP"}), json.dumps({"answer": 5})],
])
def test_llm_failures_fall_back(responses):
    s = Services(provider=FakeProvider(responses))
    r = run(s.ask("How did revenue perform against budget?"))
    assert r["status"] == "answered"
    assert r["interpretation"]["method"] == "rule_based" and r["interpretation"]["llm_status"].startswith("fallback")
    assert r["explanation_method"] == "deterministic_fallback"


def test_openai_provider_timeout_and_errors():
    def timeout_handler(request):
        raise httpx.ReadTimeout("slow", request=request)
    p = OpenAICompatibleProvider("http://llm.test/v1", "k", "m", 1, transport=httpx.MockTransport(timeout_handler))
    with pytest.raises(ProviderError, match="timeout"):
        run(p.complete([]))
    p = OpenAICompatibleProvider("http://llm.test/v1", "k", "m", 1,
                                 transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"foo": 1})))
    with pytest.raises(ProviderError, match="Malformed"):
        run(p.complete([]))
    p = OpenAICompatibleProvider("http://llm.test/v1", "k", "m", 1,
                                 transport=httpx.MockTransport(lambda r: httpx.Response(401, json={})))
    with pytest.raises(ProviderError, match="401"):
        run(p.complete([]))
    ok = OpenAICompatibleProvider("http://llm.test/v1", "k", "m", 1, transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json={"choices": [{"message": {"content": "hi"}}]})))
    assert run(ok.complete([])).content == "hi"
    assert not OpenAICompatibleProvider(api_key="your_api_key_here").is_configured


def test_rule_interpreter_what_if_parsing(svc):
    r = svc.interpreter.interpret_rules("What happens to operating income if revenue growth is two percentage points lower?")
    assert r.plan.analysis_type == "what_if"
    assert r.plan.assumptions[0].key == "revenue_growth_adj" and r.plan.assumptions[0].value == pytest.approx(-0.02)
    r = svc.interpreter.interpret_rules("What if marketing is cut by 15% in Sales & Marketing?")
    a = r.plan.assumptions[0]
    assert a.key == "marketing_pct" and a.value == pytest.approx(-0.15) and a.department == "Sales & Marketing"
    assert svc.interpreter.interpret_rules("What if things change?").plan is None
