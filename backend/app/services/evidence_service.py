"""Evidence packages built only from deterministic analytics outputs. Never from LLM prose."""
import math
import threading
import uuid
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from ..schemas.analysis import EvidencePackage, EvidenceItem, ReconciliationCheck

ENGINE_VERSION = "finsight-engine-0.2.0"
MAX_STORED = 200
DATASET_FILES = {"actuals": "data/actuals.csv", "budget": "data/budget.csv", "forecast": "data/forecast.csv",
                 "financial_drivers": "data/financial_drivers.csv", "cash_flow": "data/cash_flow.csv",
                 "scenarios": "data/scenarios.json", "model": "computed (projection model)"}


class EvidenceError(ValueError):
    pass


def _finite(x) -> Optional[float]:
    if x is None:
        return None
    x = float(x)
    if not math.isfinite(x):
        raise EvidenceError("non-finite value in evidence")
    return x


class EvidenceService:
    def __init__(self):
        self._store: "OrderedDict[str, EvidencePackage]" = OrderedDict()
        self._lock = threading.Lock()

    def build(self, analysis_type: str, scope: Dict[str, Any], items: List[Dict[str, Any]],
              source_datasets: List[str], question: Optional[str] = None,
              assumptions: Optional[List[Dict[str, Any]]] = None,
              reconciliation: Optional[List[Dict[str, Any]]] = None,
              warnings: Optional[List[str]] = None, missing_data: Optional[List[str]] = None) -> EvidencePackage:
        aid = f"AN-{uuid.uuid4().hex[:10]}"
        ev_items = []
        for n, it in enumerate(items, start=1):
            it = dict(it)
            for k in ("value", "comparison_value", "absolute_change", "percentage_change"):
                it[k] = _finite(it.get(k))
            it.setdefault("evidence_id", f"{aid}-E{n:02d}")
            ev_items.append(EvidenceItem(**it))
        unknown = [d for d in source_datasets if d not in DATASET_FILES]
        if unknown:
            raise EvidenceError(f"unknown source datasets: {unknown}")
        missing = list(missing_data or [])
        complete = bool(ev_items) and not any(i.value is None for i in ev_items if i.kind != "assumption")
        if not ev_items:
            missing.append("No computed values available for the requested scope")
        pkg = EvidencePackage(
            analysis_id=aid, question=question, analysis_type=analysis_type, scope=scope,
            source_datasets=source_datasets, items=ev_items, assumptions=assumptions or [],
            reconciliation=[ReconciliationCheck(**r) for r in (reconciliation or [])],
            warnings=list(dict.fromkeys(warnings or [])), missing_data=missing, complete=complete,
            provenance={"engine_version": ENGINE_VERSION, "generated_at": datetime.now(timezone.utc).isoformat(),
                        "files": {d: DATASET_FILES[d] for d in source_datasets},
                        "data_notice": "All data is synthetic (Asteron Group, fictional).",
                        "generated_by": "deterministic analytics (Python/Pandas)"})
        with self._lock:
            self._store[aid] = pkg
            while len(self._store) > MAX_STORED:
                self._store.popitem(last=False)
        return pkg

    def get(self, analysis_id: str) -> Optional[EvidencePackage]:
        return self._store.get(analysis_id)

    def list(self) -> List[Dict[str, Any]]:
        return [{"analysis_id": p.analysis_id, "analysis_type": p.analysis_type, "question": p.question,
                 "created_at": p.created_at, "item_count": len(p.items), "complete": p.complete}
                for p in reversed(self._store.values())]

    @staticmethod
    def numeric_values(pkg: EvidencePackage) -> List[float]:
        vals = []
        for i in pkg.items:
            vals += [v for v in (i.value, i.comparison_value, i.absolute_change, i.percentage_change) if v is not None]
        for a in pkg.assumptions:
            v = a.get("value")
            if isinstance(v, (int, float)):
                vals.append(float(v))
        for r in pkg.reconciliation:
            if r.difference is not None:
                vals.append(r.difference)
        return vals
