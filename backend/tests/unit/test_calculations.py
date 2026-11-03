# Test calculations
from app.analytics.calculations import (
    calculate_gross_profit,
    calculate_operating_income,
    calculate_gross_margin_pct,
    calculate_operating_margin_pct,
    calculate_variance,
    calculate_cash_flow_ending
)


def test_gross_profit():
    assert calculate_gross_profit(100000, 60000) == 40000


def test_operating_income():
    gross_profit = calculate_gross_profit(100000, 60000)
    operating_expenses = 25000
    assert calculate_operating_income(gross_profit, operating_expenses) == 15000


def test_gross_margin():
    margin = calculate_gross_margin_pct(40000, 100000)
    assert margin == 40.0


def test_operating_margin():
    margin = calculate_operating_margin_pct(15000, 100000)
    assert margin == 15.0


def test_gross_margin_zero_revenue():
    margin = calculate_gross_margin_pct(0, 0)
    assert margin is None


def test_operating_margin_zero_revenue():
    margin = calculate_operating_margin_pct(-10000, 0)
    assert margin is None


def test_variance_favourable():
    abs_var, pct_var = calculate_variance(950000, 900000)
    assert abs_var == 50000
    assert pct_var is not None
    assert abs(pct_var - 5.555) < 0.01


def test_variance_zero_budget():
    abs_var, pct_var = calculate_variance(50000, 0)
    assert abs_var == 50000
    assert pct_var is None


def test_variance_both_zero():
    abs_var, pct_var = calculate_variance(0, 0)
    assert abs_var == 0
    assert pct_var is None


def test_cash_flow_reconciliation():
    ending = calculate_cash_flow_ending(5000000, 1350000, 935000)
    assert ending == 5415000
