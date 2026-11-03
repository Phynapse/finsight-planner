import axios, { AxiosError } from 'axios';
import type {
  Summary, Trend, Variance, Scenario, ScenarioListItem, AssumptionSpec, AssumptionInput,
  QuestionResponse, EvidencePackage, EvidenceListItem, CashFlow, Forecast, SensitivityRanking, ScenarioCompare, Meta,
} from '../types';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api',
  timeout: 60000,
});

export function errorMessage(e: unknown): string {
  const err = e as AxiosError<{ detail?: unknown; errors?: string[] }>;
  if (err?.response?.data) {
    const d = err.response.data;
    if (d.errors?.length) return d.errors.join('; ');
    if (typeof d.detail === 'string') return d.detail;
    if (Array.isArray(d.detail)) return d.detail.map((x: { msg?: string }) => x.msg).join('; ');
  }
  if (err?.request && !err.response) return 'Backend unreachable. Start the API on port 8000.';
  return (err as Error)?.message || 'Unexpected error';
}

type Params = Record<string, string | number | string[] | undefined | null>;
const clean = (p: Params) => Object.fromEntries(Object.entries(p).filter(([, v]) => v !== undefined && v !== null && v !== ''));
const get = <T,>(url: string, params: Params = {}) =>
  api.get<T>(url, { params: clean(params), paramsSerializer: { indexes: null } }).then(r => r.data);

export const healthApi = { getHealth: () => api.get('/health') };
export const datasetsApi = { listDatasets: () => api.get('/datasets') };

export const financialsApi = {
  meta: () => get<Meta>('/financials/meta'),
  summary: (p: Params = {}) => get<Summary>('/financials/summary', p),
  trend: (p: Params = {}) => get<Trend>('/financials/trend', p),
  variance: (p: Params = {}) => get<Variance>('/financials/variance', p),
  forecast: (horizon = 12) => get<Forecast>('/financials/forecast', { horizon_months: horizon }),
  cashFlow: (p: Params = {}) => get<CashFlow>('/financials/cash-flow', p),
};

export const scenariosApi = {
  list: () => get<{ scenarios: ScenarioListItem[] }>('/scenarios').then(d => d.scenarios),
  assumptions: () => get<{ assumptions: AssumptionSpec[] }>('/scenarios/assumptions').then(d => d.assumptions),
  get: (id: string) => get<Scenario>(`/scenarios/${encodeURIComponent(id)}`),
  create: (name: string, description: string, assumptions: AssumptionInput[], horizon_months = 12) =>
    api.post<Scenario>('/scenarios', { name, description, assumptions, horizon_months }).then(r => r.data),
  update: (id: string, assumptions: AssumptionInput[]) =>
    api.put<Scenario>(`/scenarios/${encodeURIComponent(id)}`, { assumptions }).then(r => r.data),
  compare: (id: string, against = 'baseline') => get<ScenarioCompare>(`/scenarios/${encodeURIComponent(id)}/compare`, { against }),
  ranking: (metric = 'operating_income') => get<SensitivityRanking>('/scenarios/sensitivity/ranking', { metric }),
};

export const questionsApi = {
  ask: (question: string) => api.post<QuestionResponse>('/questions', { question }).then(r => r.data),
  examples: () => get<{ examples: string[]; llm_configured: boolean }>('/questions/examples'),
};

export const evidenceApi = {
  list: () => get<{ analyses: EvidenceListItem[] }>('/evidence').then(d => d.analyses),
  get: (id: string) => get<EvidencePackage>(`/evidence/${encodeURIComponent(id)}`),
  runAnalysis: (body: Record<string, unknown>) =>
    api.post<{ analysis_id: string }>('/analysis', body).then(r => r.data),
};

export default api;
