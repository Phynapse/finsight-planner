from typing import List, Optional

from fastapi import APIRouter, Query, HTTPException

from ...schemas.analysis import AnalysisRequest
from ...services.container import get_services
from ..utils import clean

router = APIRouter()


@router.get("/financials/meta")
def meta():
    return clean(get_services().financial.meta())


@router.get("/financials/summary")
def financials_summary(period: Optional[str] = None, business_unit: Optional[str] = None,
                       department: Optional[str] = None):
    return clean(get_services().financial.summary(period, business_unit, department))


@router.get("/financials/trend")
def trend(business_unit: Optional[str] = None, department: Optional[str] = None, source: str = "actual"):
    return clean(get_services().financial.trend(business_unit, department, source))


@router.get("/financials/variance")
def variance(comparison: str = "actual_vs_budget", periods: Optional[List[str]] = Query(None),
             business_unit: Optional[str] = None, department: Optional[str] = None,
             group_by: Optional[str] = None, line_type: Optional[str] = None):
    if line_type not in (None, "revenue", "expense", "all"):
        raise HTTPException(422, "line_type must be revenue, expense or all")
    return clean(get_services().financial.variance(comparison, periods, business_unit, department, group_by, line_type))


@router.get("/financials/rollup")
def rollup(source: str = "actual", periods: Optional[List[str]] = Query(None), business_unit: Optional[str] = None,
           department: Optional[str] = None, group_by: str = "department"):
    return clean(get_services().financial.rollup(source, periods, business_unit, department, group_by))


@router.get("/financials/profitability")
def profitability(periods: Optional[List[str]] = Query(None), business_unit: Optional[str] = None,
                  department: Optional[str] = None, group_by: str = "department"):
    svc = get_services().financial
    return clean(svc.rollup("actual", periods or [svc.repo.latest_actual_period()], business_unit, department, group_by))


@router.get("/financials/forecast")
def forecast(horizon_months: int = Query(12, ge=1, le=24)):
    return clean(get_services().financial.forecast(horizon_months))


@router.get("/financials/drivers")
def drivers():
    return clean(get_services().financial.drivers())


@router.get("/financials/cash-flow")
def cash_flow(business_unit: Optional[str] = None, horizon_months: int = Query(12, ge=1, le=24)):
    return clean(get_services().financial.cash_flow(business_unit, horizon_months))


@router.post("/analysis")
def create_analysis(req: AnalysisRequest):
    out = get_services().planner.execute(req)
    return clean({"analysis_id": out["evidence"].analysis_id, "plan": out["plan"], "headline": out["headline"],
                  "findings": out["findings"], "result": out["result"], "evidence": out["evidence"]})


@router.get("/evidence")
def list_evidence():
    return {"analyses": get_services().evidence.list()}


@router.get("/evidence/{analysis_id}")
def get_evidence(analysis_id: str):
    pkg = get_services().evidence.get(analysis_id)
    if pkg is None:
        raise HTTPException(404, f"Unknown analysis_id '{analysis_id}' (evidence is held in memory and lost on restart)")
    return clean(pkg)
