"""Application service wiring (process-wide singletons; state is in-memory)."""
from functools import lru_cache
from typing import Optional, Dict, Any
import uuid

from ..ai.analysis_planner import AnalysisPlanner, PlanError
from ..ai.explanation_generator import ExplanationGenerator
from ..ai.providers.base import LLMProvider
from ..ai.providers.openai_compatible import get_provider
from ..ai.question_interpreter import QuestionInterpreter, EXAMPLES
from ..data.repository import get_repository
from .evidence_service import EvidenceService
from .financial_service import FinancialService
from .scenario_service import ScenarioService


class Services:
    def __init__(self, provider: Optional[LLMProvider] = None):
        self.repo = get_repository()
        self.financial = FinancialService(self.repo)
        self.scenarios = ScenarioService(self.repo, self.financial)
        self.evidence = EvidenceService()
        self.planner = AnalysisPlanner(self.financial, self.scenarios, self.evidence)
        self.provider = provider if provider is not None else get_provider()
        self.interpreter = QuestionInterpreter(self.repo.business_units(), self.repo.departments(),
                                               self.repo.periods("actual"), self.provider)
        self.explainer = ExplanationGenerator(self.provider)

    async def ask(self, question: str) -> Dict[str, Any]:
        interp = await self.interpreter.interpret_async(question)
        base = {"question": question, "interpretation": interp.to_dict(),
                "llm_configured": bool(self.provider and self.provider.is_configured)}
        if interp.plan is None:
            return {**base, "status": "unsupported", "answer": f"I can't answer that with the available analytics. {interp.unsupported_reason}",
                    "supported_examples": EXAMPLES, "evidence": None, "explanation_method": "none"}
        try:
            analysis = self.planner.execute(interp.plan, question)
        except PlanError as e:
            return {**base, "status": "invalid_plan", "answer": f"The request could not be resolved: {e}",
                    "supported_examples": EXAMPLES, "evidence": None, "explanation_method": "none"}
        explanation = await self.explainer.explain(question, analysis["evidence"], analysis)
        return {**base, "status": "answered", "answer": explanation["answer"], "explanation": explanation,
                "explanation_method": explanation["method"], "plan": analysis["plan"],
                "evidence": analysis["evidence"].model_dump(), "result": analysis["result"]}


@lru_cache(maxsize=1)
def get_services() -> Services:
    return Services()
