# AI Architecture

Flow (`services/container.py::Services.ask`):

**Question → AnalysisPlan (validated) → deterministic operation → EvidencePackage → explanation → structured response**

## 1. Interpretation (`ai/question_interpreter.py`)

- **Rule-based (always available).** Keyword/regex router that extracts periods (`YYYY-MM` or year), business unit,
  department, scenario, metric, comparison type and what-if assumption changes (e.g. "revenue growth is two percentage
  points lower" → `revenue_growth_adj = -0.02`; "marketing is cut by 15%" → `marketing_pct = -0.15`).
- **LLM-assisted (only when configured).** The model is asked for a JSON plan, never an answer. The JSON is parsed and
  validated with the strict Pydantic `AnalysisPlan` (`extra="forbid"`, `Literal` analysis types/metrics/comparisons,
  bounded lists, period regex). Any provider error, malformed JSON or schema failure falls back to rules and the
  response records `interpretation.llm_status`.
- Unsupported questions return `status: "unsupported"`, a reason and supported examples. They are never routed to an
  unrelated analysis. Ambiguous references ("this scenario") ask the user to name the scenario.

## 2. Planning and execution (`ai/analysis_planner.py`)

Explicit allowlist: `financial_summary, variance_analysis, profitability_analysis, dimension_comparison,
scenario_comparison, what_if, sensitivity_analysis, cash_flow_analysis, forecast_analysis, driver_analysis`.
`validate()` checks business units, departments and periods against the dataset, scenario IDs, and what-if
assumptions through the scenario validator. Invalid plans raise `PlanError` (HTTP 422 / `status: invalid_plan`).
No code from the LLM is ever executed; the LLM has no data or filesystem access.

## 3. Evidence (`services/evidence_service.py`)

Each operation builds an `EvidencePackage` from its computed results: analysis id, question, scope, source datasets
(allowlisted ids → file paths), items (value, comparison, change, unit, period, dimension, source, formula id,
assessment, kind = source/calculated/projection/assumption), assumptions, reconciliation checks, warnings, missing-data
notices and provenance. Non-finite values are rejected; empty packages are marked `complete: false`. Packages are stored
in memory (last 200) and served by `/api/evidence/{id}`.

## 4. Explanation (`ai/explanation_generator.py`)

- **Deterministic explanation** (always built): headline and findings formatted from computed values, assumptions,
  caveats (warnings, reconciliation failures, causal-uncertainty notice, synthetic-data notice), follow-ups.
- **LLM explanation** (configured only): receives the question, analysis type, scope and evidence only. It must return
  JSON (`answer, key_findings, interpretations, caveats, follow_ups`).
- **Numerical grounding:** every number in the LLM text is extracted (handles `$`, commas, `%`, `K/M/B`) and must match
  an evidence value within rounding tolerance (small counts and years are ignored). Any ungrounded figure → the
  deterministic explanation is returned with `llm_status: rejected_ungrounded_figures`.
- `explanation_method` is `llm` only when the LLM output passed validation; otherwise `deterministic_fallback`.
  Interpretations are shown separately from calculated findings in the UI.

## Provider (`ai/providers/openai_compatible.py`)

Env vars (unchanged from Box 1): `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_TIMEOUT`. `is_configured` is false
for empty/placeholder keys, in which case no external call is attempted. `POST {base}/chat/completions` with timeout,
one bounded retry on timeout/429/5xx, clear `ProviderError`s for 4xx, transport errors and malformed/empty responses.
Logs contain only error types/status codes — never prompts or keys.

## Testing

`tests/unit/test_ai_evidence.py` uses a `FakeProvider` and `httpx.MockTransport`; no live LLM calls are made. The
real provider has not been exercised against a live endpoint in this phase.
