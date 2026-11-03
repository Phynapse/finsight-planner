import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_reports_data_and_llm():
    j = client.get("/api/health").json()
    assert j["data_loaded"] and j["llm_configured"] is False and j["synthetic_data"]


def test_dataset_summary_and_unknown():
    j = client.get("/api/datasets/actuals/summary").json()
    assert j["rows"] == 235 and j["period_end"] == "2026-09"
    assert client.get("/api/datasets/nope/summary").status_code == 404


def test_financial_summary_computed():
    j = client.get("/api/financials/summary", params={"period": "2026-09"}).json()
    st = j["statement"]
    assert st["revenue"] == 920000 + 760000
    assert st["gross_profit"] == st["revenue"] - st["cogs"]
    assert st["operating_income"] == pytest.approx(st["gross_profit"] - st["operating_expenses"])
    assert j["cash"]["ending_cash"] == 7025000
    assert j["year_over_year"]["statement"]["revenue"]["comparison_value"] == 880000 + 720000


def test_summary_invalid_filters():
    assert client.get("/api/financials/summary", params={"business_unit": "Mars"}).status_code == 422
    assert client.get("/api/financials/summary", params={"period": "1999-01"}).status_code == 422
    assert client.get("/api/financials/variance", params={"comparison": "foo"}).status_code == 422


def test_variance_reconciles_and_groups_sum():
    j = client.get("/api/financials/variance", params={"comparison": "actual_vs_budget", "group_by": "department"}).json()
    assert j["bridge"]["reconciled"]
    total = j["statement"]["operating_income"]["absolute_variance"]
    assert sum(g["statement"]["operating_income"]["absolute_variance"] for g in j["groups"]) == pytest.approx(total)
    assert all(g["bridge"]["reconciled"] for g in j["groups"])


def test_actual_vs_forecast_no_overlap_is_explicit():
    j = client.get("/api/financials/variance", params={"comparison": "actual_vs_forecast"}).json()
    assert j["matched_records"] == 0 and j["warnings"]


def test_scenario_create_retrieve_update_compare():
    base_before = client.get("/api/scenarios/baseline").json()["result"]["summary"]
    r = client.post("/api/scenarios", json={"name": "Price cut", "assumptions": [
        {"key": "revenue_level_pct", "value": -0.05}, {"key": "collection_days", "value": 70}]})
    assert r.status_code == 201
    sc = r.json()
    sid = sc["scenario_id"]
    cmp_ = sc["result"]["comparison_against_baseline"]
    assert cmp_["revenue"]["percentage_change"] == pytest.approx(-5.0)
    assert cmp_["ending_cash"]["absolute_change"] < 0
    got = client.get(f"/api/scenarios/{sid}").json()
    assert got["result"]["summary"] == sc["result"]["summary"]
    upd = client.put(f"/api/scenarios/{sid}", json={"assumptions": [{"key": "revenue_level_pct", "value": 0.05}]}).json()
    assert upd["result"]["comparison_against_baseline"]["revenue"]["percentage_change"] == pytest.approx(5.0)
    c = client.get(f"/api/scenarios/{sid}/compare", params={"against": "downside"}).json()
    assert c["comparison"]["operating_income"]["absolute_change"] > 0
    assert client.get("/api/scenarios/baseline").json()["result"]["summary"] == base_before
    assert sid in [s["scenario_id"] for s in client.get("/api/scenarios").json()["scenarios"]]


def test_scenario_errors():
    assert client.get("/api/scenarios/does-not-exist").status_code == 404
    r = client.post("/api/scenarios", json={"name": "bad", "assumptions": [{"key": "magic", "value": 1}]})
    assert r.status_code == 422 and r.json()["errors"]
    assert client.post("/api/scenarios", json={"name": "bad", "assumptions": [{"key": "revenue_level_pct", "value": 3}]}).status_code == 422
    assert client.post("/api/scenarios", json={"assumptions": []}).status_code == 422
    assert client.put("/api/scenarios/downside", json={"assumptions": []}).status_code == 409


def test_sensitivity_endpoints():
    j = client.post("/api/scenarios/sensitivity", json={"assumption": "cogs_ratio_adj", "values": [-0.02, 0, 0.02]}).json()
    oi = [p["metrics"]["operating_income"] for p in j["points"]]
    assert oi[0] > oi[1] > oi[2]
    r = client.get("/api/scenarios/sensitivity/ranking").json()
    assert len(r["ranking"]) == 8


def test_forecast_and_cash_endpoints():
    f = client.get("/api/financials/forecast", params={"horizon_months": 6}).json()
    assert f["forecast_periods"][0] == "2026-10" and len(f["forecast_periods"]) == 6
    assert f["reference_forecast_comparison"]["matched_periods"] == ["2026-12", "2027-03"]
    assert all(r["status"] == "projected" for r in f["projection"]["total"])
    c = client.get("/api/financials/cash-flow").json()
    assert c["history"]["total_rows"] == 26 and c["projection"]["reconciled"]
    assert client.get("/api/financials/forecast", params={"horizon_months": 99}).status_code == 422


def test_analysis_endpoint_and_evidence():
    r = client.post("/api/analysis", json={"analysis_type": "profitability_analysis", "periods": ["2026-06"], "dimension": "business_unit"})
    assert r.status_code == 200
    j = r.json()
    ev = client.get(f"/api/evidence/{j['analysis_id']}").json()
    assert ev["scope"]["periods"] == ["2026-06"]
    na = [i for i in ev["items"] if i["dimension"] == "North America" and i["metric"] == "revenue"][0]
    assert na["value"] == 910000 + 750000
    assert client.post("/api/analysis", json={"analysis_type": "hack"}).status_code == 422
    assert client.get("/api/evidence/AN-missing").status_code == 404


def test_questions_endpoint():
    j = client.post("/api/questions", json={"question": "Compare the downside scenario with the baseline."}).json()
    assert j["status"] == "answered" and j["plan"]["scenario_id"] == "downside"
    assert j["explanation_method"] == "deterministic_fallback"
    items = {i["metric"]: i for i in j["evidence"]["items"]}
    assert items["operating_income"]["absolute_change"] == pytest.approx(
        items["operating_income"]["value"] - items["operating_income"]["comparison_value"])
    assert client.post("/api/questions", json={"question": ""}).status_code == 422
    u = client.post("/api/questions", json={"question": "Tell me a joke"}).json()
    assert u["status"] == "unsupported"
