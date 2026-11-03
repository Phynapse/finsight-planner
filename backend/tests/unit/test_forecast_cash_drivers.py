import pandas as pd
import pytest

from app.analytics.cash_flow_analyzer import CashFlowAnalyzer
from app.analytics.driver_analyzer import DriverAnalyzer
from app.analytics.forecasting import build_baseline_inputs, run_model, add_months
from app.data.repository import get_repository


def test_add_months():
    assert add_months("2026-11", 2) == "2027-01" and add_months("2026-09", -12) == "2025-09"


def test_real_baseline_inputs():
    repo = get_repository()
    inp = build_baseline_inputs(repo)
    assert inp.base_period == "2026-09"
    assert {(u.business_unit, u.department) for u in inp.units} == {("North America", "Sales & Marketing"),
                                                                       ("North America", "Engineering & Product")}
    sm = [u for u in inp.units if u.department == "Sales & Marketing"][0]
    assert sm.revenue_growth == pytest.approx(920000 / 880000 - 1)  # 2026-09 vs 2025-09 actuals
    assert sm.cogs_ratio == pytest.approx(368000 / 920000)
    assert any("excluded" in w for w in inp.warnings)


def test_projection_periods_and_first_month():
    repo = get_repository()
    inp = build_baseline_inputs(repo)
    r = run_model(inp, horizon=6)
    assert r["periods"][0] == "2026-10" and len(r["periods"]) == 6
    assert all(p > repo.latest_actual_period() for p in r["periods"])
    sm = [u for u in r["units"] if u["department"] == "Sales & Marketing"][0]["rows"][0]
    assert sm["revenue"] == pytest.approx(920000 * (920000 / 880000) ** (1 / 12))
    assert sm["cogs"] == pytest.approx(sm["revenue"] * 0.4)
    with pytest.raises(ValueError):
        run_model(inp, horizon=0)


def test_projected_cash_reconciles_every_month():
    inp = build_baseline_inputs(get_repository())
    rows = run_model(inp, horizon=12)["cash"]["rows"]
    assert rows[0]["opening_cash"] == 7025000  # reported NA ending cash 2026-09
    for prev, cur in zip(rows, rows[1:]):
        assert cur["opening_cash"] == prev["ending_cash"]
    for r in rows:
        assert r["ending_cash"] == pytest.approx(r["opening_cash"] + r["cash_inflows"] - r["cash_outflows"])


def test_cash_formula_outflows_positive():
    r = CashFlowAnalyzer().analyze(100, 50, 30, 120)
    assert r["ending_cash_calculated"] == 120 and r["reconciled"]
    r = CashFlowAnalyzer().analyze(100, 50, 30, 125)
    assert not r["reconciled"] and r["reconciliation_difference"] == 5


def test_cash_history_flags_and_continuity():
    cf = pd.DataFrame([
        {"period": "2024-01", "business_unit": "X", "opening_cash": 100, "customer_collections": 50, "operating_payments": 10,
         "payroll_payments": 10, "capital_expenditure": 5, "debt_repayments": 5, "other_cash_movements": 0, "ending_cash": 120, "duplicate": False},
        {"period": "2024-02", "business_unit": "X", "opening_cash": 125, "customer_collections": 0, "operating_payments": 0,
         "payroll_payments": 0, "capital_expenditure": 0, "debt_repayments": 0, "other_cash_movements": -5, "ending_cash": 120, "duplicate": False},
    ])
    h = CashFlowAnalyzer().history(cf, "2024-12")
    assert h["rows"][0]["reconciled"] and h["rows"][1]["reconciled"]  # negative other treated as outflow once
    assert h["continuity"][0]["expected"] and not h["continuity"][0]["continuous"]
    assert any("continuity" in w for w in h["warnings"])


def test_real_cash_history_reports_discrepancies_without_correcting():
    repo = get_repository()
    h = CashFlowAnalyzer().history(repo.cash_flow, repo.latest_actual_period())
    assert h["total_rows"] == 26
    eu = [r for r in h["rows"] if r["business_unit"] == "Europe" and r["period"] == "2024-01"][0]
    assert eu["reconciled"]
    na = [r for r in h["rows"] if r["business_unit"] == "North America" and r["period"] == "2024-01"][0]
    assert na["reconciliation_difference"] == 405000 and na["ending_cash_reported"] == 5680000
    assert any(r["status"] == "dataset_plan" for r in h["rows"])
    assert any(r["duplicate"] for r in h["rows"])


def test_driver_relationships():
    repo = get_repository()
    d = DriverAnalyzer().analyze(repo.drivers, repo.get_ledger("actual"))
    rev = [c for c in d["checks"] if c["relationship"] == "revenue_from_customers"][0]
    assert rev["implied_value"] == 8500 * 100 and rev["status"] == "consistent"
    unmatched = [c for c in d["checks"] if c["status"] == "no_matching_actual"]
    assert unmatched and all(c["actual_value"] is None for c in unmatched)


def test_missing_driver_not_fabricated():
    drivers = pd.DataFrame([{"period": "2024-01", "business_unit": "A", "department": "D", "driver_name": "customer_count",
                             "driver_value": 10, "driver_unit": "accounts", "scenario": "baseline", "assumption_source": "x"}])
    act = pd.DataFrame(columns=["period", "business_unit", "department", "financial_line", "value"])
    assert DriverAnalyzer().analyze(drivers, act)["checks"] == []
