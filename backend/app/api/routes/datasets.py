from fastapi import APIRouter, HTTPException

from ...data.repository import get_repository, DATASET_DESCRIPTIONS
from ..utils import clean

router = APIRouter()
NAMES = {"actuals": "Actuals", "budget": "Budget", "forecast": "Forecast", "financial_drivers": "Financial Drivers",
         "cash_flow": "Cash Flow", "scenarios": "Scenarios"}


@router.get("/datasets")
def list_datasets():
    repo = get_repository()
    return clean({"datasets": [{"id": k, "name": NAMES[k], "description": DATASET_DESCRIPTIONS[k],
                                "rows": repo.dataset_summary(k)["rows"]} for k in NAMES],
                  "synthetic": True, "issue_count": len(repo.issues)})


@router.get("/datasets/{dataset_id}/summary")
def dataset_summary(dataset_id: str):
    try:
        return clean(get_repository().dataset_summary(dataset_id))
    except KeyError:
        raise HTTPException(404, f"Unknown dataset '{dataset_id}'. Valid: {', '.join(NAMES)}")
