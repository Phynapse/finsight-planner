"""In-memory repository holding normalised, validated synthetic datasets.

Source files are read once and never written. All consumers receive copies.
"""
from functools import lru_cache
from pathlib import Path
from typing import Dict, Any, List, Optional

import pandas as pd

from .loader import DataLoader
from .validation import ledger_issues, cash_flow_issues, validate_financial_data
from ..core.config import settings

REVENUE_LINE = "revenue"
COGS_LINE = "cogs"
OPEX_LINES = ["compensation_expense", "marketing_expense", "technology_expense",
              "facilities_expense", "other_operating_expense"]
ALL_LINES = [REVENUE_LINE, COGS_LINE] + OPEX_LINES

# source -> (file, value column, dataset id)
SOURCES = {
    "actual": ("actuals.csv", "amount"),
    "budget": ("budget.csv", "budget_amount"),
    "forecast": ("forecast.csv", "forecast_amount"),
}
SOURCE_DATASET = {"actual": "actuals", "budget": "budget", "forecast": "forecast"}
LEDGER_KEY = ["period", "business_unit", "department", "financial_line"]

DATASET_DESCRIPTIONS = {
    "actuals": "Historical monthly actuals (synthetic)",
    "budget": "Approved budget (synthetic, sparse coverage)",
    "forecast": "Reference forecast FCST-Q4-2026 (synthetic)",
    "financial_drivers": "Operational drivers: customers, ARPC, headcount, compensation, collection days",
    "cash_flow": "Cash-flow statement rows by business unit (synthetic)",
    "scenarios": "Scenario preset definitions",
}


def resolve_data_dir(data_dir: str) -> Path:
    p = Path(data_dir)
    if not p.is_absolute():
        p = (Path(__file__).resolve().parents[2] / p).resolve()
    return p


class DataRepository:
    def __init__(self, data_dir: Optional[str] = None):
        self.data_dir = resolve_data_dir(data_dir or settings.data_dir)
        loader = DataLoader(str(self.data_dir))
        self.raw: Dict[str, Any] = loader.load_all()
        self.issues: List[Dict[str, Any]] = []
        frames = []
        for source, (_, col) in SOURCES.items():
            df = self.raw[SOURCE_DATASET[source]].copy()
            validate_financial_data(df, col)
            self.issues += ledger_issues(df, SOURCE_DATASET[source], col)
            df["value"] = pd.to_numeric(df[col], errors="coerce")
            df = df[df["value"].notna()]
            df = df.drop_duplicates(LEDGER_KEY, keep="first")
            df["source"] = source
            frames.append(df[LEDGER_KEY + ["value", "source"]])
        self.ledger = pd.concat(frames, ignore_index=True)
        self.ledger["period"] = self.ledger["period"].astype(str)
        cf = self.raw["cash_flow"].copy()
        cf["period"] = cf["period"].astype(str)
        self.issues += cash_flow_issues(cf)
        cf["duplicate"] = cf.duplicated(["period", "business_unit"], keep=False)
        self.cash_flow = cf
        self.drivers = self.raw["financial_drivers"].copy()
        self.drivers["period"] = self.drivers["period"].astype(str)
        self.scenarios = self.raw["scenarios"]

    # ---- accessors (always return copies) ----
    def get_ledger(self, source: Optional[str] = None) -> pd.DataFrame:
        df = self.ledger if source is None else self.ledger[self.ledger["source"] == source]
        return df.copy()

    def get(self, key: str):
        val = self.raw.get(key)
        return val.copy() if hasattr(val, "copy") else val

    def get_all(self):
        return dict(self.raw)

    def periods(self, source: str = "actual") -> List[str]:
        return sorted(self.ledger.loc[self.ledger["source"] == source, "period"].unique().tolist())

    def latest_actual_period(self) -> str:
        return self.periods("actual")[-1]

    def business_units(self) -> List[str]:
        return sorted(self.ledger["business_unit"].unique().tolist())

    def departments(self) -> List[str]:
        return sorted(self.ledger["department"].unique().tolist())

    def dataset_summary(self, dataset_id: str) -> Dict[str, Any]:
        if dataset_id not in self.raw:
            raise KeyError(dataset_id)
        data = self.raw[dataset_id]
        if isinstance(data, pd.DataFrame):
            out = {"dataset_id": dataset_id, "rows": int(len(data)), "columns": list(data.columns)}
            if "period" in data.columns:
                periods = sorted(data["period"].astype(str).unique())
                out.update(period_start=periods[0], period_end=periods[-1], distinct_periods=len(periods))
            if "business_unit" in data.columns:
                out["business_units"] = sorted(data["business_unit"].unique().tolist())
        else:
            out = {"dataset_id": dataset_id, "rows": len(data.get("scenarios", [])), "columns": []}
        out["description"] = DATASET_DESCRIPTIONS.get(dataset_id, "")
        out["issues"] = [i for i in self.issues if i["dataset"] == dataset_id]
        out["synthetic"] = True
        return out


@lru_cache(maxsize=1)
def get_repository() -> DataRepository:
    return DataRepository()
