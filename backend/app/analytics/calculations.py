"""Authoritative deterministic financial formulas.

Sign convention: revenue, COGS and operating expenses are positive amounts.
Variance convention: variance = value - comparison; variance % = variance / |comparison| * 100.
A zero comparison yields percentage = None (not applicable), never infinity.
"""
import math
from typing import Optional, Tuple, Dict, Iterable

RECONCILIATION_TOLERANCE = 0.01  # currency units

HIGHER_IS_BETTER = {"revenue", "gross_profit", "operating_income", "gross_margin_pct",
                    "operating_margin_pct", "ending_cash", "net_cash_movement", "cash_inflows"}
EXPENSE_METRICS = {"cogs", "operating_expenses", "compensation_expense", "marketing_expense",
                   "technology_expense", "facilities_expense", "other_operating_expense", "cash_outflows"}


def calculate_gross_profit(revenue: float, cogs: float) -> float:
    return revenue - cogs


def calculate_operating_expenses(compensation: float = 0, marketing: float = 0,
                                 technology: float = 0, facilities: float = 0,
                                 other: float = 0) -> float:
    return compensation + marketing + technology + facilities + other


def calculate_operating_income(gross_profit: float, operating_expenses: float) -> float:
    return gross_profit - operating_expenses


def safe_ratio_pct(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator * 100


def calculate_gross_margin_pct(gross_profit: float, revenue: float) -> Optional[float]:
    return safe_ratio_pct(gross_profit, revenue)


def calculate_operating_margin_pct(operating_income: float, revenue: float) -> Optional[float]:
    return safe_ratio_pct(operating_income, revenue)


def calculate_variance(actual_or_forecast: float, budget: float) -> Tuple[float, Optional[float]]:
    """Absolute variance and % variance against |comparison|; % is None when comparison is 0."""
    absolute_variance = actual_or_forecast - budget
    if budget == 0:
        return absolute_variance, None
    return absolute_variance, absolute_variance / abs(budget) * 100


def pct_change(new: Optional[float], old: Optional[float]) -> Optional[float]:
    if new is None or old is None:
        return None
    return calculate_variance(new, old)[1]


def classify_variance(metric: str, absolute_variance: Optional[float]) -> Optional[str]:
    """favourable / unfavourable / neutral. Expense increases are unfavourable."""
    if absolute_variance is None:
        return None
    if abs(absolute_variance) < 1e-9:
        return "neutral"
    m = metric.lower()
    if m in EXPENSE_METRICS or "expense" in m or m == "cogs":
        return "favourable" if absolute_variance < 0 else "unfavourable"
    return "favourable" if absolute_variance > 0 else "unfavourable"


def calculate_cash_flow_ending(opening_cash: float, inflows: float, outflows: float) -> float:
    """Outflows are positive amounts and are subtracted once."""
    return opening_cash + inflows - outflows


def is_finite_number(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def income_statement(lines: Dict[str, float], opex_lines: Iterable[str]) -> Dict:
    """Build an income statement from reported line amounts.

    Missing revenue -> revenue-dependent metrics are None. Missing COGS -> gross profit None.
    Missing operating-expense lines are listed in `missing_lines` (opex covers reported lines only).
    """
    opex_lines = list(opex_lines)
    revenue = lines.get("revenue")
    cogs = lines.get("cogs")
    reported_opex = [l for l in opex_lines if l in lines and lines[l] is not None]
    missing = [l for l in ["revenue", "cogs"] + opex_lines if l not in lines or lines[l] is None]
    opex = sum(lines[l] for l in reported_opex) if reported_opex else None
    gp = calculate_gross_profit(revenue, cogs) if revenue is not None and cogs is not None else None
    oi = calculate_operating_income(gp, opex) if gp is not None and opex is not None else None
    return {
        "revenue": revenue, "cogs": cogs, "gross_profit": gp,
        "operating_expenses": opex, "operating_income": oi,
        "gross_margin_pct": calculate_gross_margin_pct(gp, revenue) if gp is not None else None,
        "operating_margin_pct": calculate_operating_margin_pct(oi, revenue) if oi is not None else None,
        "missing_lines": missing,
    }
