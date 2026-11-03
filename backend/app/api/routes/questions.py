from fastapi import APIRouter

from ...ai.question_interpreter import EXAMPLES
from ...schemas.analysis import QuestionRequest
from ...services.container import get_services
from ..utils import clean

router = APIRouter()


@router.post("/questions")
async def ask_question(req: QuestionRequest):
    return clean(await get_services().ask(req.question.strip()))


@router.get("/questions/examples")
def examples():
    svc = get_services()
    return {"examples": EXAMPLES, "llm_configured": bool(svc.provider and svc.provider.is_configured)}
