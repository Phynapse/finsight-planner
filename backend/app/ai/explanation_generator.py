"""Grounded explanation generation.

The deterministic explanation is assembled from computed findings. An optional LLM rewrite receives only
the question, analysis metadata and evidence; every number in its output must match an evidence value,
otherwise the deterministic explanation is used and the reason is reported.
"""
import json
import logging
import re
from typing import Dict, Any, List, Optional

from ..schemas.analysis import EvidencePackage
from ..services.evidence_service import EvidenceService
from .providers.base import LLMProvider, Message, ProviderError

logger = logging.getLogger("finsight.ai")
NUM_RE = re.compile(r"(?<![\w-])(-?\$?-?\d[\d,]*(?:\.\d+)?)\s*(%|pp|percentage points?|[kKmMbB]\b|million|thousand|billion)?")
LIMITATION = "All figures derive from synthetic Asteron Group data and deterministic calculations."


def extract_numbers(text: str) -> List[Dict[str, Any]]:
    out = []
    for m in NUM_RE.finditer(text):
        raw, suffix = m.group(1), (m.group(2) or "").lower()
        try:
            v = float(raw.replace("$", "").replace(",", ""))
        except ValueError:
            continue
        mult = {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6, "b": 1e9, "billion": 1e9}.get(suffix, 1)
        out.append({"raw": m.group(0).strip(), "value": v * mult, "is_money": "$" in raw, "suffix": suffix, "scaled": mult != 1})
    return out


def is_grounded_number(n: Dict[str, Any], allowed: List[float]) -> bool:
    v = n["value"]
    # Ignore plain small counts, years and YYYY-MM fragments that are not financial figures.
    if not n["is_money"] and not n["suffix"] and (abs(v) <= 31 and float(v).is_integer() or 2000 <= abs(v) <= 2100):
        return True
    for a in allowed:
        for cand in (a, -a):
            tol = 0.051 if abs(cand) < 100 else 0.006 * abs(cand) + 1
            if n["scaled"]:
                tol = max(tol, 0.051 * abs(cand))
            if abs(v - cand) <= tol:
                return True
            if abs(cand) <= 1.5 and abs(v - cand * 100) <= 0.051 * max(1, abs(cand * 100)):  # decimal shown as percent
                return True
    return False


class ExplanationGenerator:
    def __init__(self, provider: Optional[LLMProvider] = None):
        self.provider = provider

    # Backward-compatible signature
    def generate(self, evidence: EvidencePackage, results: Dict[str, Any]) -> Dict[str, Any]:
        return self.deterministic(evidence, results)

    def deterministic(self, evidence: EvidencePackage, analysis: Dict[str, Any]) -> Dict[str, Any]:
        caveats = list(evidence.warnings) + list(evidence.missing_data) + [LIMITATION]
        failed = [r.check for r in evidence.reconciliation if r.status == "failed"]
        if failed:
            caveats.insert(0, "Reconciliation failed: " + "; ".join(failed))
        return {"answer": analysis["headline"], "key_findings": analysis["findings"],
                "assumptions": [f"{a.get('name') or a.get('key')}: {a.get('value')}" for a in evidence.assumptions],
                "caveats": caveats, "follow_ups": analysis.get("follow_ups", []),
                "method": "deterministic_fallback"}

    async def explain(self, question: str, evidence: EvidencePackage, analysis: Dict[str, Any]) -> Dict[str, Any]:
        base = self.deterministic(evidence, analysis)
        if self.provider is None or not self.provider.is_configured:
            base["llm_status"] = "not_configured"
            return base
        payload = {"question": question, "analysis_type": evidence.analysis_type, "scope": evidence.scope,
                   "evidence": [i.model_dump(exclude={"evidence_id"}) for i in evidence.items],
                   "assumptions": evidence.assumptions, "warnings": evidence.warnings,
                   "reconciliation": [r.model_dump() for r in evidence.reconciliation]}
        system = ("You are a careful FP&A analyst. Explain ONLY the supplied evidence. Use only numbers that appear in the "
                  "evidence (you may round). Do not compute new figures. Do not claim causes the data does not establish; "
                  "label interpretations as possible explanations. Respond with JSON: {\"answer\": str, "
                  "\"key_findings\": [str], \"interpretations\": [str], \"caveats\": [str], \"follow_ups\": [str]}.")
        try:
            resp = await self.provider.complete([Message("system", system),
                                                 Message("user", json.dumps(payload, default=str)[:12000])],
                                                temperature=0, max_tokens=700)
            text = re.sub(r"^```(json)?|```$", "", resp.content.strip(), flags=re.M).strip()
            data = json.loads(text)
            if not isinstance(data, dict) or not isinstance(data.get("answer"), str):
                raise ValueError("missing answer")
            findings = [str(x) for x in data.get("key_findings", []) if isinstance(x, (str, int, float))][:10]
            interps = [str(x) for x in data.get("interpretations", [])][:5]
            all_text = " ".join([data["answer"]] + findings + interps)
            allowed = EvidenceService.numeric_values(evidence)
            bad = [n["raw"] for n in extract_numbers(all_text) if not is_grounded_number(n, allowed)]
            if bad:
                logger.warning("LLM explanation contained %d ungrounded figures; using deterministic explanation", len(bad))
                base["llm_status"] = "rejected_ungrounded_figures"
                base["rejected_figures"] = bad[:10]
                return base
        except (ProviderError, ValueError, TypeError) as e:
            logger.warning("LLM explanation unavailable (%s); using deterministic explanation", type(e).__name__)
            base["llm_status"] = f"fallback: {type(e).__name__}"
            return base
        return {"answer": data["answer"], "key_findings": findings or base["key_findings"],
                "interpretations": interps, "assumptions": base["assumptions"],
                "caveats": base["caveats"] + [str(c) for c in data.get("caveats", [])][:5],
                "follow_ups": [str(x) for x in data.get("follow_ups", [])][:3] or base["follow_ups"],
                "computed_findings": base["key_findings"], "method": "llm", "llm_status": "ok"}
