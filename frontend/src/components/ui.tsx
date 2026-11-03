import { useCallback, useEffect, useRef, useState, ReactNode } from 'react';
import { errorMessage } from '../services/api';

export const usd = (v: number | null | undefined) =>
  v === null || v === undefined ? 'n/a' : (v < 0 ? '-' : '') + '$' + Math.abs(v).toLocaleString('en-US', { maximumFractionDigits: 0 });
export const usdCompact = (v: number | null | undefined) =>
  v === null || v === undefined ? 'n/a' : (v < 0 ? '-' : '') + '$' + (Math.abs(v) >= 1e6 ? (Math.abs(v) / 1e6).toFixed(2) + 'M' : (Math.abs(v) / 1e3).toFixed(0) + 'K');
export const signedUsd = (v: number | null | undefined) => (v === null || v === undefined ? 'n/a' : (v >= 0 ? '+' : '') + usd(v));
export const pct = (v: number | null | undefined, signed = false) =>
  v === null || v === undefined ? 'n/a' : (signed && v >= 0 ? '+' : '') + v.toFixed(1) + '%';
export const pp = (v: number | null | undefined) => (v === null || v === undefined ? 'n/a' : (v >= 0 ? '+' : '') + v.toFixed(1) + ' pp');
export const label = (s: string) => s.replace(/_pct$/, ' %').replace(/_/g, ' ').replace(/^\w/, c => c.toUpperCase());
export const fmtMetric = (metric: string, v: number | null | undefined) => (metric.endsWith('_pct') ? pct(v) : usd(v));
export const fmtChange = (metric: string, abs: number | null | undefined, rel?: number | null) =>
  metric.endsWith('_pct') ? pp(abs) : `${signedUsd(abs)}${rel !== undefined ? ` (${pct(rel, true)})` : ''}`;

/** Fetch hook: tracks loading/error and discards stale responses. */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const seq = useRef(0);
  const run = useCallback(() => {
    const id = ++seq.current;
    setLoading(true);
    setError(null);
    fn().then(d => { if (id === seq.current) setData(d); })
      .catch(e => { if (id === seq.current) { setData(null); setError(errorMessage(e)); } })
      .finally(() => { if (id === seq.current) setLoading(false); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(() => { run(); }, [run]);
  return { data, error, loading, reload: run };
}

export function Status({ loading, error, empty, children }: { loading: boolean; error: string | null; empty?: boolean; children?: ReactNode }) {
  if (loading) return <div className="state" role="status">Loading…</div>;
  if (error) return <div className="state error" role="alert">Error: {error}</div>;
  if (empty) return <div className="state">No data for this selection.</div>;
  return <>{children}</>;
}

export function Badge({ value }: { value: string | null | undefined }) {
  if (!value) return <span className="badge">n/a</span>;
  return <span className={`badge ${value}`}>{value}</span>;
}

export function Warnings({ items }: { items?: string[] }) {
  if (!items?.length) return null;
  return (
    <div className="warn-box">
      <strong>Data notes & limitations</strong>
      <ul>{items.map((w, i) => <li key={i}>{w}</li>)}</ul>
    </div>
  );
}

export function Kpi({ title, value, sub, tone }: { title: string; value: string; sub?: string; tone?: string | null }) {
  return (
    <div className={`metric-card ${tone || ''}`}>
      <h3>{title}</h3>
      <div className="value num">{value}</div>
      {sub && <div className="subtext">{sub}</div>}
    </div>
  );
}
