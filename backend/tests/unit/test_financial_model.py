import pandas as pd
import pytest

from app.analytics.calculations import (calculate_variance, classify_variance, income_statement, pct_change,
                                        safe_ratio_pct)
from app.analytics.profitability_analyzer import build_statements
from app.analytics.variance_analyzer import variance_bridge, compare_sources, metric_variance
from app.data.repository import OPEX_LINES


def _ledger(rows):
    return pd.DataFrame(rows, columns=["period", "business_unit", "department", "financial_line", "value", "source"])


def test_income_statement_complete():
    st = income_statement({"revenue": 1000, "cogs": 400, "compensation_expense": 200, "marketing_expense": 100,
                           "technology_expense": 50, "facilities_expense": 25, "other_operating_expense": 25}, OPEX_LINES)
    assert st["gross_profit"] == 600
    assert st["operating_expenses"] == 400
    assert st["operating_income"] == 200
    assert st["gross_margin_pct"] == 60
    assert st["operating_margin_pct"] == 20
    assert st["missing_lines"] == []


def test_negative_operating_income():
    st = income_statement({"revenue": 100, "cogs": 80, "compensation_expense": 50}, OPEX_LINES)
    assert st["operating_income"] == -30
    assert st["operating_margin_pct"] == -30


def test_zero_revenue_margins_not_applicable():
    st = income_statement({"revenue": 0, "cogs": 10, "compensation_expense": 5}, OPEX_LINES)
    assert st["operating_income"] == -15
    assert st["gross_margin_pct"] is None and st["operating_margin_pct"] is None


def test_missing_revenue_is_not_zero_filled():
    st = income_statement({"cogs": 10, "compensation_expense": 5}, OPEX_LINES)
    assert st["revenue"] is None and st["gross_profit"] is None and st["operating_income"] is None
    assert "revenue" in st["missing_lines"]


def test_missing_opex_line_flagged():
    st = income_statement({"revenue": 100, "cogs": 40, "compensation_expense": 20}, OPEX_LINES)
    assert "other_operating_expense" in st["missing_lines"]
    assert st["operating_expenses"] == 20


def test_variance_uses_absolute_denominator():
    a, p = calculate_variance(-50, -100)
    assert a == 50 and p == 50.0
    assert calculate_variance(10, 0) == (10, None)
    assert pct_change(None, 5) is None
    assert safe_ratio_pct(1, 0) is None


def test_favourability_conventions():
    assert classify_variance("revenue", 10) == "favourable"
    assert classify_variance("revenue", -10) == "unfavourable"
    assert classify_variance("cogs", 10) == "unfavourable"
    assert classify_variance("operating_expenses", -10) == "favourable"
    assert classify_variance("marketing_expense", 5) == "unfavourable"
    assert classify_variance("operating_income", 0) == "neutral"


def test_margin_variance_in_points():
    mv = metric_variance("operating_margin_pct", 20.0, 25.0)
    assert mv["absolute_variance"] == -5.0 and mv["percentage_variance"] is None


@pytest.mark.parametrize("cur,cmp_", [
    ({"revenue": 1100, "cogs": 450, "operating_expenses": 300, "operating_income": 350},
     {"revenue": 1000, "cogs": 400, "operating_expenses": 320, "operating_income": 280}),
    ({"revenue": 900, "cogs": 420, "operating_expenses": 350, "operating_income": 130},
     {"revenue": 1000, "cogs": 400, "operating_expenses": 320, "operating_income": 280}),
])
def test_bridge_reconciles(cur, cmp_):
    b = variance_bridge(cur, cmp_)
    expected = (cur["revenue"] - cmp_["revenue"]) - (cur["cogs"] - cmp_["cogs"]) - (cur["operating_expenses"] - cmp_["operating_expenses"])
    assert b["calculated_operating_income_variance"] == expected
    assert b["actual_operating_income_difference"] == cur["operating_income"] - cmp_["operating_income"]
    assert b["reconciled"]


def test_bridge_exposes_discrepancy():
    b = variance_bridge({"revenue": 100, "cogs": 0, "operating_expenses": 0, "operating_income": 90},
                        {"revenue": 0, "cogs": 0, "operating_expenses": 0, "operating_income": 0})
    assert not b["reconciled"] and b["reconciliation_difference"] == -10


def test_compare_sources_matches_records_only():
    led = _ledger([
        ("2024-01", "A", "D1", "revenue", 110, "actual"), ("2024-01", "A", "D1", "revenue", 100, "budget"),
        ("2024-01", "A", "D1", "cogs", 50, "actual"), ("2024-01", "A", "D1", "cogs", 40, "budget"),
        ("2024-01", "A", "D1", "marketing_expense", 20, "actual"),  # no budget -> excluded
        ("2024-01", "A", "D2", "revenue", 70, "actual"), ("2024-01", "A", "D2", "revenue", 80, "budget"),
    ])
    r = compare_sources(led, "actual", "budget", "department")
    assert r["matched_records"] == 3 and r["unmatched_current_records"] == 1
    assert r["statement"]["revenue"]["absolute_variance"] == 0  # (110+70) - (100+80)
    assert r["statement"]["cogs"]["assessment"] == "unfavourable"
    assert r["bridge"]["reconciled"]
    d2 = [g for g in r["groups"] if g["department"] == "D2"][0]
    assert d2["statement"]["revenue"]["absolute_variance"] == -10


def test_compare_sources_no_overlap():
    led = _ledger([("2024-01", "A", "D1", "revenue", 1, "actual"), ("2025-01", "A", "D1", "revenue", 1, "forecast")])
    r = compare_sources(led, "actual", "forecast")
    assert r["matched_records"] == 0 and r["statement"] is None and r["warnings"]


def test_build_statements_no_double_counting():
    led = _ledger([
        ("2024-01", "A", "D1", "revenue", 100, "actual"), ("2024-01", "A", "D1", "cogs", 40, "actual"),
        ("2024-01", "B", "D1", "revenue", 50, "actual"), ("2024-01", "B", "D1", "cogs", 10, "actual"),
        ("2024-02", "A", "D1", "revenue", 60, "actual"), ("2024-02", "A", "D1", "cogs", 30, "actual"),
    ])
    by_bu = build_statements(led, ["business_unit"])
    total = build_statements(led, [])[0]
    assert sum(g["revenue"] for g in by_bu) == total["revenue"] == 210
    by_period = build_statements(led, ["period"])
    assert [g["revenue"] for g in by_period] == [150, 60]
    assert total["units_with_missing_lines"]  # no opex reported -> flagged
