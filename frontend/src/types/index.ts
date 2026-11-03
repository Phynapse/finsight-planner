// Types mirror backend responses (backend/app/services, backend/app/schemas/analysis.py).
export type N = number | null;

export interface FinancialMetric { metric_name: string; value: number; unit: string; period: string; }

export interface VarianceResult {
  metric: string; actual_or_forecast_value: number; budget_value: number; absolute_variance: number;
  percentage_variance?: number; favourable_unfavourable?: string; caveats: string[];
}

export interface Statement {
  revenue: N; cogs: N; gross_profit: N; operating_expenses: N; operating_income: N;
  gross_margin_pct: N; operating_margin_pct: N; missing_lines: string[];
  units_with_missing_lines?: { unit: string; missing_lines: string[] }[];
  period?: string; business_unit?: string; department?: string; units?: string[];
}

export interface MetricVariance {
  metric: string; value: N; comparison_value: N; absolute_variance: N; percentage_variance: N;
  assessment: string | null; note?: string | null; period?: string; business_unit?: string; department?: string;
}

export interface Bridge {
  revenue_contribution: number; cogs_contribution: number; operating_expense_contribution: number;
  calculated_operating_income_variance: number; actual_operating_income_difference: number;
  reconciliation_difference: number; tolerance: number; reconciled: boolean; formula: string;
}

export interface Variance {
  comparison: string; matched_records: number; unmatched_current_records: number; unmatched_comparison_records: number;
  matched_periods: string[]; line_variances: MetricVariance[]; material_variances: MetricVariance[];
  statement: Record<string, MetricVariance> | null; bridge: Bridge | null;
  groups: ({ statement: Record<string, MetricVariance>; bridge: Bridge } & Record<string, unknown>)[];
  warnings: string[]; convention: string;
}

export interface Summary {
  period: string; scope: { business_unit: string | null; department: string | null; units: string[] };
  statement: Statement; year_over_year: Variance & { prior_year_period: string }; prior_year_period: string;
  budget_comparison: Variance; cash: { ending_cash: number; business_units: string[] } | null; warnings: string[];
}

export interface Trend { source: string; rows: (Statement & { period: string; units: string[] })[]; warnings: string[]; }

export interface Meta {
  business_units: string[]; departments: string[]; periods: Record<string, string[]>; latest_actual_period: string;
  comparisons: string[]; data_issues: { dataset: string; type: string; detail: string }[];
}

export interface AssumptionSpec {
  key: string; name: string; kind: string; min: number; max: number; unit: string; rule: string;
  department_scoped: boolean; departments?: string[]; baseline_value?: number;
}
export interface AssumptionInput { key: string; value: number; department?: string | null; description?: string | null; }
export interface AppliedAssumption extends AssumptionInput { name: string; unit: string; kind: string; rule: string; }

export interface ComparisonEntry {
  scenario: N; baseline: N; absolute_change: N; percentage_change: N; unit?: string; assessment: string | null; note?: string | null;
}

export interface CashRow {
  period: string; status: string; opening_cash: number; customer_collections: number; cash_inflows: number;
  operating_payments?: number; capital_expenditure: number; debt_repayments: number; cash_outflows: number;
  net_cash_movement: number; ending_cash?: number; receivables?: number;
  ending_cash_reported?: number; ending_cash_calculated?: number; reconciliation_difference?: number | null;
  reconciled?: boolean; business_unit?: string; duplicate?: boolean; payroll_payments?: number; other_cash_movements?: number;
}

export interface ModelResult {
  method: string; base_period: string; periods: string[]; summary: Record<string, N>;
  total: (Statement & { period: string; status: string })[];
  units: { business_unit: string; department: string; rows: Record<string, unknown>[] }[];
  cash: { rows: CashRow[]; reconciled: boolean | null; assumptions: Record<string, unknown> };
  trace: Record<string, unknown>[];
  assumptions: AppliedAssumption[]; comparison_against_baseline: Record<string, ComparisonEntry>;
  baseline_summary: Record<string, N>; caveats: string[];
}

export interface ScenarioListItem {
  scenario_id: string; name: string; description: string; origin: 'preset' | 'user'; preset_type: string;
  assumptions: AssumptionInput[]; horizon_months: number;
}
export interface Scenario extends Omit<ScenarioListItem, 'assumptions'> { result: ModelResult; }
export interface ScenarioCompare { comparison: Record<string, ComparisonEntry>; periods: string[]; }

export interface SensitivityRanking {
  metric: string; horizon_months: number; method: string;
  ranking: { assumption: string; low_value: number; high_value: number; impact_low: N; impact_high: N; range: N }[];
}

export interface CashFlow {
  history: { rows: CashRow[]; warnings: string[]; reconciled_rows: number; total_rows: number;
    continuity: { business_unit: string; from_period: string; to_period: string; consecutive_months: boolean; difference: number; continuous: boolean }[] };
  projection: ModelResult['cash'] | null; projection_scope: string[]; warnings: string[];
}

export interface Forecast {
  method: string; base_period: string; forecast_periods: string[]; historical_periods: string[];
  projection: ModelResult; reference_forecast_comparison: Variance; warnings: string[]; limitations: string[];
  assumptions: Record<string, unknown>[];
}

export interface EvidenceItem {
  evidence_id: string; metric: string; value: N; comparison_value: N; absolute_change: N; percentage_change: N;
  unit: string; period: string; dimension: string; source_dataset: string; comparison_source: string | null;
  calculation_description: string; formula_id: string | null; assessment: string | null; kind: string;
}
export interface EvidencePackage {
  analysis_id: string; question: string | null; analysis_type: string; scope: Record<string, unknown>;
  source_datasets: string[]; items: EvidenceItem[]; assumptions: Record<string, unknown>[];
  reconciliation: { check: string; status: string; difference: N; tolerance: N; detail: string }[];
  warnings: string[]; missing_data: string[]; provenance: Record<string, unknown>; complete: boolean; created_at: string;
}
export interface EvidenceListItem { analysis_id: string; analysis_type: string; question: string | null; created_at: string; item_count: number; complete: boolean; }

export interface QuestionResponse {
  question: string; status: 'answered' | 'unsupported' | 'invalid_plan'; answer: string;
  explanation_method: 'llm' | 'deterministic_fallback' | 'none'; llm_configured: boolean;
  interpretation: { method: string; llm_status: string; unsupported_reason: string | null };
  explanation?: { key_findings: string[]; assumptions: string[]; caveats: string[]; follow_ups: string[];
    interpretations?: string[]; computed_findings?: string[]; llm_status?: string };
  plan?: Record<string, unknown>; evidence: EvidencePackage | null; supported_examples?: string[];
}
