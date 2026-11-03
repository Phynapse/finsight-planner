"""Source data validation. Issues are reported, never silently corrected."""
import re
from typing import List, Dict, Any

import pandas as pd

PERIOD_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def validate_financial_data(df, value_col: str = "amount"):
    """Raise if required ledger columns are missing (kept for backward compatibility)."""
    required_cols = ['period', 'business_unit', 'department', 'financial_line', value_col]
    for col in required_cols:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")
    return True


def ledger_issues(df: pd.DataFrame, dataset: str, value_col: str) -> List[Dict[str, Any]]:
    """Return data-quality issues for a long-format ledger file."""
    issues: List[Dict[str, Any]] = []
    bad_period = df[~df["period"].astype(str).str.match(PERIOD_RE)]
    for _, r in bad_period.iterrows():
        issues.append({"dataset": dataset, "type": "invalid_period", "detail": f"Invalid period '{r['period']}'"})
    values = pd.to_numeric(df[value_col], errors="coerce")
    for idx in df.index[values.isna()]:
        r = df.loc[idx]
        issues.append({"dataset": dataset, "type": "missing_or_non_numeric_value",
                       "detail": f"{r['period']} {r['business_unit']} / {r['department']} {r['financial_line']}: value missing or non-numeric; row excluded"})
    neg = df[values < 0]
    for _, r in neg.iterrows():
        issues.append({"dataset": dataset, "type": "negative_amount",
                       "detail": f"{r['period']} {r['business_unit']} / {r['department']} {r['financial_line']} is negative ({r[value_col]}); convention expects positive amounts"})
    key = ["period", "business_unit", "department", "financial_line"]
    dups = df[df.duplicated(key, keep="first")]
    for _, r in dups.iterrows():
        issues.append({"dataset": dataset, "type": "duplicate_record",
                       "detail": f"Duplicate {r['period']} {r['business_unit']} / {r['department']} {r['financial_line']}; first occurrence kept"})
    return issues


def cash_flow_issues(df: pd.DataFrame) -> List[Dict[str, Any]]:
    issues = []
    dups = df[df.duplicated(["period", "business_unit"], keep=False)]
    for (p, bu), g in dups.groupby(["period", "business_unit"]):
        issues.append({"dataset": "cash_flow", "type": "conflicting_duplicate",
                       "detail": f"{len(g)} rows for {bu} {p} with ending cash {sorted(g['ending_cash'].tolist())}; both shown, excluded from projection anchors"})
    return issues
