from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class FinancialPeriod(BaseModel):
    period: str = Field(..., pattern=r'^\d{4}-\d{2}$')
    year: int
    month: int


class FinancialLineItem(BaseModel):
    period: str
    business_unit: str
    department: str
    financial_line: str
    amount: float
    currency: str = "USD"
    source_type: str = Field(..., pattern=r'^(actual|budget|forecast)$')


class FinancialMetric(BaseModel):
    metric_name: str
    value: float
    unit: str
    period: str
    source: str
    calculation_description: str


class VarianceResult(BaseModel):
    metric: str
    actual_or_forecast_value: float
    budget_value: float
    absolute_variance: float
    percentage_variance: Optional[float] = None
    favourable_unfavourable: Optional[str] = None
    caveats: List[str] = []


class ForecastAssumption(BaseModel):
    assumption_name: str
    value: float
    unit: str
    period: str
    source: str
    scenario: str = "baseline"


class ScenarioAssumption(BaseModel):
    assumption_name: str
    target: Dict[str, str]
    change_type: str = Field(..., pattern=r'^(percentage|absolute|driver)$')
    change_value: float
    driver: Optional[str] = None
    description: str


class ScenarioDefinition(BaseModel):
    scenario_id: str
    name: str
    description: str
    assumptions: List[ScenarioAssumption] = []
    base_scenario: Optional[str] = None
    metadata: Dict[str, Any] = {}


class ScenarioResult(BaseModel):
    scenario_id: str
    financial_outputs: Dict[str, Any]
    comparison_against_baseline: Dict[str, Any] = {}
    changed_assumptions: List[Dict[str, Any]] = []
    caveats: List[str] = []


