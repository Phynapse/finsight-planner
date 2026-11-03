from fastapi import APIRouter, Query

from ...schemas.analysis import ScenarioCreateRequest, ScenarioUpdateRequest, SensitivityRequest
from ...services.container import get_services
from ..utils import clean

router = APIRouter()


@router.get("/scenarios")
def list_scenarios():
    return clean({"scenarios": get_services().scenarios.list()})


@router.get("/scenarios/assumptions")
def assumption_registry():
    return clean({"assumptions": get_services().scenarios.assumption_registry()})


@router.post("/scenarios/sensitivity")
def sensitivity(req: SensitivityRequest):
    return clean(get_services().scenarios.sensitivity.analyze(req.assumption, req.values, req.horizon_months, req.department))


@router.get("/scenarios/sensitivity/ranking")
def sensitivity_ranking(metric: str = Query("operating_income", pattern="^(operating_income|ending_cash|revenue|gross_profit)$"),
                        horizon_months: int = Query(12, ge=1, le=24)):
    return clean(get_services().scenarios.sensitivity.rank(horizon_months, metric))


@router.post("/scenarios", status_code=201)
def create_scenario(req: ScenarioCreateRequest):
    return clean(get_services().scenarios.create(req.name, req.description,
                                                 [a.model_dump() for a in req.assumptions], req.horizon_months))


@router.get("/scenarios/{scenario_id}")
def get_scenario(scenario_id: str, horizon_months: int = Query(None, ge=1, le=24)):
    return clean(get_services().scenarios.get(scenario_id, horizon_months))


@router.put("/scenarios/{scenario_id}")
def update_scenario(scenario_id: str, req: ScenarioUpdateRequest):
    return clean(get_services().scenarios.update(scenario_id, [a.model_dump() for a in req.assumptions], req.horizon_months))


@router.get("/scenarios/{scenario_id}/compare")
def compare(scenario_id: str, against: str = "baseline", horizon_months: int = Query(12, ge=1, le=24)):
    return clean(get_services().scenarios.compare(scenario_id, against, horizon_months))
