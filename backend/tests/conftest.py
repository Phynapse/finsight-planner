import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
os.environ["LLM_API_KEY"] = ""  # tests never call a real LLM

from app.analytics.forecasting import BaselineInputs, UnitBase, CashAnchor  # noqa: E402


@pytest.fixture
def tiny_inputs():
    """Hand-verifiable model: revenue 1000, COGS 400 (40%), opex 300, flat growth, cash 10,000."""
    unit = UnitBase("TestBU", "Sales & Marketing", "2026-09",
                    (("revenue", 1000.0), ("cogs", 400.0), ("compensation_expense", 200.0), ("marketing_expense", 100.0)),
                    revenue_growth=0.0, opex_growth=0.0, cogs_ratio=0.4, growth_reference_period="2025-09")
    anchor = CashAnchor("TestBU", "2026-09", 10000.0, 50.0, 0.0, 0.0, 0.0)
    return BaselineInputs("2026-09", (unit,), (anchor,), 60.0, (), ())
