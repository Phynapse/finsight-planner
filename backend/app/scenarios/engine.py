"""Scenario engine: validates assumptions, runs the projection model on an isolated copy and
compares against the baseline. The shared baseline inputs are immutable (frozen dataclasses)."""
from typing import Dict, Any, List, Optional

from ..analytics.forecasting import BaselineInputs, run_model, DEFAULT_HORIZON
from .assumptions import validate_assumptions
from .comparison import compare_summaries


class ScenarioEngine:
    def __init__(self, inputs: BaselineInputs):
        self.inputs = inputs

    def validate_assumptions(self, assumptions: List[Dict[str, Any]]):
        return validate_assumptions(assumptions, self.inputs)

    def baseline(self, horizon: int = DEFAULT_HORIZON) -> Dict[str, Any]:
        return run_model(self.inputs, {}, None, horizon)

    def run(self, assumptions: List[Dict[str, Any]], horizon: int = DEFAULT_HORIZON) -> Dict[str, Any]:
        params, days, normalised = validate_assumptions(assumptions, self.inputs)
        result = run_model(self.inputs, params, days, horizon)
        base = self.baseline(horizon)
        result["assumptions"] = normalised
        result["comparison_against_baseline"] = compare_summaries(result["summary"], base["summary"])
        result["baseline_summary"] = base["summary"]
        result["caveats"] = list(self.inputs.warnings) + [
            "Projection is assumption-driven, not a statistically validated forecast.",
            f"Scope: {', '.join(f'{u.business_unit} / {u.department}' for u in self.inputs.units)}."]
        return result
