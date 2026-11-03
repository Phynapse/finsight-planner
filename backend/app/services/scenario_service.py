"""Scenario service: presets from scenarios.json plus user scenarios held in memory (lost on restart)."""
import threading
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from ..analytics.sensitivity_analyzer import SensitivityAnalyzer
from ..data.repository import DataRepository
from ..scenarios.assumptions import preset_assumptions, registry, PRESET_TYPES
from ..scenarios.comparison import compare_scenarios
from ..scenarios.engine import ScenarioEngine
from .financial_service import FinancialService

MAX_USER_SCENARIOS = 100


class ScenarioNotFound(KeyError):
    pass


class ScenarioService:
    def __init__(self, repo: DataRepository, financial: FinancialService):
        self.repo = repo
        self.engine = ScenarioEngine(financial.inputs)
        self.sensitivity = SensitivityAnalyzer(self.engine)
        self._user: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
        self._lock = threading.Lock()
        self._presets = {s["scenario_id"]: s for s in repo.scenarios["scenarios"]}

    def assumption_registry(self) -> List[Dict[str, Any]]:
        return registry(self.engine.inputs)

    def _definition(self, scenario_id: str) -> Dict[str, Any]:
        if scenario_id in self._presets:
            s = self._presets[scenario_id]
            return {"scenario_id": scenario_id, "name": s["name"], "description": s["description"], "origin": "preset",
                    "preset_type": PRESET_TYPES.get(s.get("metadata", {}).get("type"), "custom"),
                    "assumptions": preset_assumptions(s, self.repo.drivers, self.engine.inputs), "horizon_months": 12}
        if scenario_id in self._user:
            return self._user[scenario_id]
        raise ScenarioNotFound(scenario_id)

    def list(self) -> List[Dict[str, Any]]:
        out = []
        for sid in list(self._presets) + list(self._user):
            d = self._definition(sid)
            out.append({k: d.get(k) for k in ("scenario_id", "name", "description", "origin", "preset_type",
                                               "assumptions", "horizon_months", "created_at")})
        return out

    def get(self, scenario_id: str, horizon: Optional[int] = None) -> Dict[str, Any]:
        d = self._definition(scenario_id)
        res = self.engine.run(d["assumptions"], horizon or d["horizon_months"])
        return {**{k: d.get(k) for k in ("scenario_id", "name", "description", "origin", "preset_type", "created_at")},
                "horizon_months": horizon or d["horizon_months"], "result": res}

    def create(self, name: str, description: str, assumptions: List[Dict[str, Any]], horizon: int) -> Dict[str, Any]:
        self.engine.validate_assumptions(assumptions)  # raises AssumptionError before storing
        sid = f"scn-{uuid.uuid4().hex[:8]}"
        with self._lock:
            self._user[sid] = {"scenario_id": sid, "name": name, "description": description, "origin": "user",
                               "preset_type": "custom", "assumptions": [dict(a) for a in assumptions],
                               "horizon_months": horizon, "created_at": datetime.now(timezone.utc).isoformat()}
            while len(self._user) > MAX_USER_SCENARIOS:
                self._user.popitem(last=False)
        return self.get(sid)

    def update(self, scenario_id: str, assumptions: List[Dict[str, Any]], horizon: Optional[int]) -> Dict[str, Any]:
        if scenario_id not in self._user:
            if scenario_id in self._presets:
                raise PermissionError("Preset scenarios are read-only; create a new scenario instead")
            raise ScenarioNotFound(scenario_id)
        self.engine.validate_assumptions(assumptions)
        with self._lock:
            d = dict(self._user[scenario_id])
            d["assumptions"] = [dict(a) for a in assumptions]
            if horizon:
                d["horizon_months"] = horizon
            self._user[scenario_id] = d
        return self.get(scenario_id)

    def compare(self, scenario_id: str, against: str = "baseline", horizon: int = 12) -> Dict[str, Any]:
        a, b = self.get(scenario_id, horizon), self.get(against, horizon)
        return {"scenario": {"scenario_id": scenario_id, "name": a["name"], "assumptions": a["result"]["assumptions"]},
                "against": {"scenario_id": against, "name": b["name"], "assumptions": b["result"]["assumptions"]},
                "horizon_months": horizon, "periods": a["result"]["periods"],
                "comparison": compare_scenarios(a["result"], b["result"]),
                "caveats": a["result"]["caveats"]}
