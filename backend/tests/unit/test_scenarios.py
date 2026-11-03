import copy

import pytest

from app.analytics.forecasting import run_model
from app.analytics.sensitivity_analyzer import SensitivityAnalyzer
from app.scenarios.assumptions import AssumptionError, preset_assumptions
from app.scenarios.engine import ScenarioEngine


def test_baseline_hand_verified(tiny_inputs):
    r = run_model(tiny_inputs, horizon=3)
    assert r["periods"] == ["2026-10", "2026-11", "2026-12"]
    s = r["summary"]
    assert s["revenue"] == pytest.approx(3000) and s["cogs"] == pytest.approx(1200)
    assert s["operating_expenses"] == pytest.approx(900) and s["operating_income"] == pytest.approx(900)
    assert s["operating_margin_pct"] == pytest.approx(30)
    # cash: +1000 collections - 700 payments - 50 capex per month
    assert s["ending_cash"] == pytest.approx(10750)
    assert all(row["status"] == "projected" for row in r["total"])


def test_revenue_level_flows_to_profit_and_cash(tiny_inputs):
    e = ScenarioEngine(tiny_inputs)
    r = e.run([{"key": "revenue_level_pct", "value": -0.10}], horizon=3)
    s = r["summary"]
    assert s["revenue"] == pytest.approx(2700) and s["cogs"] == pytest.approx(1080)
    assert s["operating_income"] == pytest.approx(720)
    c = r["comparison_against_baseline"]["operating_income"]
    assert c["absolute_change"] == pytest.approx(-180) and c["percentage_change"] == pytest.approx(-20)
    assert c["assessment"] == "unfavourable"
    # AR falls from 2000 to 1800 in month 1 -> collections 1100
    assert r["cash"]["rows"][0]["customer_collections"] == pytest.approx(1100)


def test_collection_days_affect_cash_only(tiny_inputs):
    r = ScenarioEngine(tiny_inputs).run([{"key": "collection_days", "value": 90}], horizon=3)
    assert r["comparison_against_baseline"]["operating_income"]["absolute_change"] == pytest.approx(0)
    assert r["cash"]["rows"][0]["customer_collections"] == pytest.approx(0)
    assert r["summary"]["ending_cash"] == pytest.approx(9750)


def test_growth_adjustment_compounds(tiny_inputs):
    r = run_model(tiny_inputs, {"Sales & Marketing": {"revenue_growth_adj": 0.2}}, horizon=12)
    assert r["total"][-1]["revenue"] == pytest.approx(1200)
    assert r["total"][0]["revenue"] == pytest.approx(1000 * 1.2 ** (1 / 12))


def test_multiple_assumptions(tiny_inputs):
    r = ScenarioEngine(tiny_inputs).run([{"key": "cogs_ratio_adj", "value": 0.1}, {"key": "marketing_pct", "value": -0.5},
                                         {"key": "compensation_pct", "value": 0.1}, {"key": "headcount_pct", "value": 0.1}], horizon=1)
    s = r["summary"]
    assert s["cogs"] == pytest.approx(500)
    assert s["operating_expenses"] == pytest.approx(200 * 1.1 * 1.1 + 50)
    assert len(r["assumptions"]) == 4


@pytest.mark.parametrize("bad", [
    [{"key": "unknown", "value": 1}],
    [{"key": "revenue_level_pct", "value": -0.9}],
    [{"key": "revenue_level_pct", "value": float("nan")}],
    [{"key": "revenue_level_pct", "value": 0.1, "department": "Nope"}],
    [{"key": "collection_days", "value": 30, "department": "Sales & Marketing"}],
    [{"key": "cogs_ratio_adj", "value": -0.45}],
    [{"key": "marketing_pct", "value": 0.1}, {"key": "marketing_pct", "value": 0.2}],
])
def test_invalid_assumptions_rejected(tiny_inputs, bad):
    with pytest.raises(AssumptionError):
        ScenarioEngine(tiny_inputs).run(bad, horizon=3)


def test_isolation_immutability_determinism(tiny_inputs):
    snapshot = copy.deepcopy(tiny_inputs)
    e = ScenarioEngine(tiny_inputs)
    base1 = e.baseline(3)
    a = e.run([{"key": "revenue_level_pct", "value": 0.2}], 3)
    b = e.run([{"key": "marketing_pct", "value": -0.5}], 3)
    assert tiny_inputs == snapshot
    assert e.baseline(3) == base1
    assert a["summary"]["operating_expenses"] == pytest.approx(900)
    assert b["summary"]["revenue"] == pytest.approx(3000)
    assert e.run([{"key": "revenue_level_pct", "value": 0.2}], 3)["summary"] == a["summary"]


def test_zero_denominator_comparison(tiny_inputs):
    from app.scenarios.comparison import compare_summaries
    c = compare_summaries({"operating_income": 10, "revenue": 5}, {"operating_income": 0, "revenue": 5})
    assert c["operating_income"]["percentage_change"] is None and c["operating_income"]["absolute_change"] == 10


def test_sensitivity_monotonic(tiny_inputs):
    s = SensitivityAnalyzer(ScenarioEngine(tiny_inputs))
    r = s.analyze("revenue_level_pct", [-0.1, 0.0, 0.1], horizon=3)
    oi = [p["metrics"]["operating_income"] for p in r["points"]]
    assert oi == sorted(oi) and oi[1] == pytest.approx(900)
    with pytest.raises(ValueError):
        s.analyze("revenue_level_pct", [], 3)
    rank = s.rank(3)
    assert rank["ranking"][0]["range"] >= rank["ranking"][-1]["range"]


def test_presets_on_real_data():
    from app.data.repository import get_repository
    from app.analytics.forecasting import build_baseline_inputs
    repo = get_repository()
    inputs = build_baseline_inputs(repo)
    e = ScenarioEngine(inputs)
    base = e.baseline()["summary"]
    res = {}
    for s in repo.scenarios["scenarios"]:
        res[s["scenario_id"]] = e.run(preset_assumptions(s, repo.drivers, inputs))["summary"]
    assert res["baseline"] == base
    assert res["downside"]["operating_income"] < base["operating_income"] < res["upside"]["operating_income"]
    assert res["downside"]["ending_cash"] < base["ending_cash"] < res["upside"]["ending_cash"]
    assert res["expense_reduction"]["revenue"] == pytest.approx(base["revenue"])
    assert res["expense_reduction"]["operating_expenses"] < base["operating_expenses"]
    # downside collection days come from the financial_drivers dataset (75 days)
    down = [a for a in preset_assumptions(repo.scenarios["scenarios"][1], repo.drivers, inputs) if a["key"] == "collection_days"]
    assert down[0]["value"] == 75
