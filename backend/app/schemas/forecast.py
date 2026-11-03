# Additional schemas
from pydantic import BaseModel
from typing import List, Optional, Dict, Any


class IncomeStatement(BaseModel):
    period: str
    business_unit: Optional[str] = None
    department: Optional[str] = None
    revenue: float = 0.0
    cogs: float = 0.0
    gross_profit: float = 0.0
    operating_expenses: float = 0.0
    operating_income: float = 0.0
    gross_margin_pct: Optional[float] = None
    operating_margin_pct: Optional[float] = None


class DatasetSummary(BaseModel):
    dataset_id: str
    name: str
    rows: int
    columns: List[str]
    description: str
