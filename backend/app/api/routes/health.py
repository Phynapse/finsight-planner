from fastapi import APIRouter

from ...services.container import get_services

router = APIRouter()


@router.get("/health")
def health():
    svc = get_services()
    return {"status": "healthy", "service": "Financial Planning & Scenario Intelligence",
            "data_loaded": not svc.repo.ledger.empty, "data_issues": len(svc.repo.issues),
            "llm_configured": bool(svc.provider and svc.provider.is_configured), "synthetic_data": True}
