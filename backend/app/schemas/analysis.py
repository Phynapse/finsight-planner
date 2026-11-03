"""Analysis, evidence and request schemas (strict at API and LLM boundaries)."""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Literal

from pydantic import BaseModel, Field, ConfigDict, field_validator

from .financial import *  # noqa: F401,F403  (backward-compatible re-export)

AnalysisType = Literal["financial_summary", "variance_analysis", "profitability_analysis", "dimension_comparison",
                       "scenario_comparison", "what_if", "sensitivity_analysis", "cash_flow_analysis",
                       "forecast_analysis", "driver_analysis"]
ANALYSIS_TYPES = list(AnalysisType.__args__)
Comparison = Literal["actual_vs_budget", "actual_vs_forecast", "forecast_vs_budget", "year_over_year"]
Metric = Literal["revenue", "cogs", "gross_profit", "operating_expenses", "operating_income",
                 "gross_margin_pct", "operating_margin_pct", "ending_cash"]


class AssumptionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    key: str = Field(..., min_length=1, max_length=50)
    value: float
    department: Optional[str] = Field(None, max_length=80)
    description: Optional[str] = Field(None, max_length=300)


class AnalysisPlan(BaseModel):
    """Constrained plan. Only allowlisted analysis types and typed parameters are accepted."""
    model_config = ConfigDict(extra="forbid")
    analysis_type: AnalysisType
    metric: Optional[Metric] = None
    periods: List[str] = Field(default_factory=list, max_length=36)
    comparison: Optional[Comparison] = None
    business_unit: Optional[str] = Field(None, max_length=80)
    department: Optional[str] = Field(None, max_length=80)
    dimension: Optional[Literal["business_unit", "department"]] = None
    line_type: Optional[Literal["revenue", "expense", "all"]] = None
    scenario_id: Optional[str] = Field(None, max_length=80)
    assumptions: List[AssumptionInput] = Field(default_factory=list, max_length=10)
    horizon_months: int = Field(12, ge=1, le=24)
    reasoning_goal: str = Field("", max_length=300)

    @field_validator("periods")
    @classmethod
    def _periods(cls, v):
        import re
        for p in v:
            if not re.match(r"^\d{4}-(0[1-9]|1[0-2])$", p):
                raise ValueError(f"invalid period '{p}' (expected YYYY-MM)")
        return v


class EvidenceItem(BaseModel):
    evidence_id: str
    metric: str
    value: Optional[float] = None
    comparison_value: Optional[float] = None
    absolute_change: Optional[float] = None
    percentage_change: Optional[float] = None
    unit: str = "USD"
    period: str
    dimension: str
    source_dataset: str
    comparison_source: Optional[str] = None
    calculation_description: str
    formula_id: Optional[str] = None
    assessment: Optional[str] = None
    kind: Literal["source", "calculated", "projection", "assumption"] = "calculated"


class ReconciliationCheck(BaseModel):
    check: str
    status: Literal["passed", "failed", "not_applicable"]
    difference: Optional[float] = None
    tolerance: Optional[float] = None
    detail: str = ""


class EvidencePackage(BaseModel):
    analysis_id: str
    question: Optional[str] = None
    analysis_type: str
    scope: Dict[str, Any] = {}
    source_datasets: List[str] = []
    items: List[EvidenceItem] = []
    assumptions: List[Dict[str, Any]] = []
    reconciliation: List[ReconciliationCheck] = []
    warnings: List[str] = []
    missing_data: List[str] = []
    provenance: Dict[str, Any] = {}
    complete: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class FinancialInsight(BaseModel):
    question: str
    answer: str
    key_findings: List[str] = []
    evidence_references: List[str] = []
    recommendations: List[str] = []
    caveats: List[str] = []


class ScenarioCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=80)
    description: str = Field("", max_length=300)
    assumptions: List[AssumptionInput] = Field(default_factory=list, max_length=20)
    horizon_months: int = Field(12, ge=1, le=24)


class ScenarioUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assumptions: List[AssumptionInput] = Field(default_factory=list, max_length=20)
    horizon_months: Optional[int] = Field(None, ge=1, le=24)


class SensitivityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assumption: str
    values: List[float] = Field(..., min_length=1, max_length=9)
    department: Optional[str] = None
    horizon_months: int = Field(12, ge=1, le=24)


class AnalysisRequest(AnalysisPlan):
    pass


class QuestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(..., min_length=3, max_length=500)
