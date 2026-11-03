"""Data-wide reconciliation checks on the complete synthetic dataset."""
import pytest

from app.analytics.profitability_analyzer import build_statements
from app.analytics.variance_analyzer import compare_sources
from app.data.repository import get_repository, LEDGER_KEY


@pytest.fixture(scope="module")
def repo():
    return get_repository()


def test_no_duplicate_ledger_records(repo):
    assert not repo.ledger.duplicated(LEDGER_KEY + ["source"]).any()


def test_known_data_issues_reported(repo):
    types = {i["type"] for i in repo.issues}
    assert "conflicting_duplicate" in types  # North America 2026-12 cash rows


@pytest.mark.parametrize("source", ["actual", "budget", "forecast"])
def test_statements_reconcile_to_components(repo, source):
    led = repo.get_ledger(source)
    for st in build_statements(led, ["period", "business_unit", "department"]):
        if st["operating_income"] is not None:
            assert st["operating_income"] == pytest.approx(st["revenue"] - st["cogs"] - st["operating_expenses"])
            assert st["gross_profit"] == pytest.approx(st["revenue"] - st["cogs"])


@pytest.mark.parametrize("source", ["actual", "budget", "forecast"])
def test_rollups_consistent(repo, source):
    led = repo.get_ledger(source)
    total = led["value"].sum()
    for cols in (["period"], ["business_unit"], ["department"], ["business_unit", "department"]):
        groups = build_statements(led, cols)
        assert sum(g["record_count"] for g in groups) == len(led)
        assert sum((led.merge(led[cols].drop_duplicates(), on=cols))["value"]) == pytest.approx(total)
    by_period = build_statements(led, ["period"])
    assert sum(g["revenue"] or 0 for g in by_period) == pytest.approx(led[led.financial_line == "revenue"]["value"].sum())


@pytest.mark.parametrize("cmp_", [("actual", "budget"), ("actual", "forecast"), ("forecast", "budget")])
def test_all_bridges_reconcile(repo, cmp_):
    r = compare_sources(repo.get_ledger(), cmp_[0], cmp_[1], "department")
    if r["bridge"]:
        assert r["bridge"]["reconciled"]
        assert all(g["bridge"]["reconciled"] for g in r["groups"])


def test_historical_and_forecast_periods_distinct(repo):
    assert max(repo.periods("actual")) < min(repo.periods("forecast"))
