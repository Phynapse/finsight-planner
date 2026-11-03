import logging as pylogging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.ai.analysis_planner import PlanError
from app.api.routes import health, datasets, financials, scenarios, questions
from app.core import logging
from app.scenarios.assumptions import AssumptionError
from app.services.evidence_service import EvidenceError
from app.services.financial_service import InvalidRequest
from app.services.scenario_service import ScenarioNotFound

logging.setup_logging()
log = pylogging.getLogger("finsight.api")

app = FastAPI(
    title="FinSight Planner - Financial Planning & Scenario Intelligence",
    description="Portfolio-grade financial planning and scenario analysis platform - Phynapse. Synthetic data only.",
    version="0.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AssumptionError)
async def _assumption_error(_: Request, exc: AssumptionError):
    return JSONResponse(status_code=422, content={"detail": "Invalid scenario assumptions", "errors": exc.errors})


@app.exception_handler(InvalidRequest)
@app.exception_handler(PlanError)
@app.exception_handler(EvidenceError)
async def _invalid(_: Request, exc: Exception):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(ScenarioNotFound)
async def _not_found(_: Request, exc: ScenarioNotFound):
    return JSONResponse(status_code=404, content={"detail": f"Unknown scenario '{exc.args[0]}'"})


@app.exception_handler(PermissionError)
async def _conflict(_: Request, exc: PermissionError):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def _unhandled(_: Request, exc: Exception):
    log.exception("Unhandled error: %s", type(exc).__name__)
    return JSONResponse(status_code=500, content={"detail": "Internal error"})


app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(datasets.router, prefix="/api", tags=["datasets"])
app.include_router(financials.router, prefix="/api", tags=["financials"])
app.include_router(scenarios.router, prefix="/api", tags=["scenarios"])
app.include_router(questions.router, prefix="/api", tags=["questions"])


@app.get("/")
async def root():
    return {
        "message": "FinSight Planner - Financial Planning & Scenario Intelligence API",
        "docs": "/docs",
        "version": "0.2.0",
        "synthetic_data": True,
    }
