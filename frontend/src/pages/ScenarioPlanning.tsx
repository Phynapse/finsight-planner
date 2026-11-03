import { useEffect, useState } from 'react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, Legend, CartesianGrid } from 'recharts';
import { scenariosApi, errorMessage } from '../services/api';
import type { AssumptionInput, Scenario } from '../types';
import { useAsync, Status, Badge, Warnings, label, fmtMetric, fmtChange, usd, usdCompact, signedUsd } from '../components/ui';

function ScenarioPlanning() {
  const list = useAsync(() => scenariosApi.list(), []);
  const registry = useAsync(() => scenariosApi.assumptions(), []);
  const baseline = useAsync(() => scenariosApi.get('baseline'), []);
  const ranking = useAsync(() => scenariosApi.ranking(), []);
  const [selected, setSelected] = useState('downside');
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState('My scenario');
  const [draft, setDraft] = useState<AssumptionInput[]>([{ key: 'revenue_growth_adj', value: -0.02 }]);
  const [formErr, setFormErr] = useState<string | null>(null);

  const load = (id: string) => {
    setBusy(true); setLoadErr(null);
    scenariosApi.get(id).then(setScenario).catch(e => { setScenario(null); setLoadErr(errorMessage(e)); }).finally(() => setBusy(false));
  };
  useEffect(() => { load(selected); }, [selected]);

  const submit = async () => {
    setFormErr(null); setBusy(true);
    try {
      const clean = draft.map(a => ({ key: a.key, value: Number(a.value), department: a.department || null }));
      if (clean.some(a => !Number.isFinite(a.value))) throw new Error('Every assumption needs a numeric value');
      const s = await scenariosApi.create(name.trim() || 'Untitled scenario', 'Created in Scenario Planning', clean);
      list.reload();
      setSelected(s.scenario_id);
      setScenario(s);
    } catch (e) { setFormErr(errorMessage(e)); } finally { setBusy(false); }
  };

  const spec = (k: string) => registry.data?.find(r => r.key === k);
  const r = scenario?.result;
  const cashData = r?.cash.rows.map((row, i) => ({ period: row.period, scenario: row.ending_cash, baseline: baseline.data?.result.cash.rows[i]?.ending_cash }));

  return (
    <div className="page">
      <h2>Scenario Planning</h2>
      <div className="info-box"><p>Scenarios are recalculated by the backend projection model from explicit assumptions (horizon: 12 months after the latest actual period). The baseline is never modified.</p></div>
      <div className="two-col">
        <div className="panel">
          <h3>Select scenario</h3>
          <Status loading={list.loading} error={list.error}>
            <select value={selected} onChange={e => setSelected(e.target.value)} aria-label="Scenario">
              {list.data?.map(s => <option key={s.scenario_id} value={s.scenario_id}>{s.name} ({s.origin === 'preset' ? s.preset_type : 'custom'})</option>)}
            </select>
          </Status>
          <h3 style={{ marginTop: '1.25rem' }}>Create scenario</h3>
          <label className="block">Name<input value={name} onChange={e => setName(e.target.value)} maxLength={80} /></label>
          {draft.map((a, i) => {
            const sp = spec(a.key);
            return (
              <div className="assumption-row" key={i}>
                <select value={a.key} aria-label="Assumption" onChange={e => setDraft(draft.map((x, j) => j === i ? { key: e.target.value, value: spec(e.target.value)?.baseline_value ?? 0 } : x))}>
                  {registry.data?.map(s => <option key={s.key} value={s.key}>{s.name}</option>)}
                </select>
                <input type="number" step="any" aria-label="Value" value={a.value} min={sp?.min} max={sp?.max}
                  onChange={e => setDraft(draft.map((x, j) => j === i ? { ...x, value: e.target.value === '' ? NaN : Number(e.target.value) } : x))} />
                {sp?.department_scoped && <select value={a.department || ''} aria-label="Department" onChange={e => setDraft(draft.map((x, j) => j === i ? { ...x, department: e.target.value || null } : x))}>
                  <option value="">All departments</option>{sp.departments?.map(d => <option key={d}>{d}</option>)}</select>}
                <button className="link" onClick={() => setDraft(draft.filter((_, j) => j !== i))} aria-label="Remove assumption">✕</button>
                {sp && <div className="hint">{sp.unit}; range {sp.min} to {sp.max}. {sp.rule}</div>}
              </div>);
          })}
          <div className="actions">
            <button className="secondary" onClick={() => setDraft([...draft, { key: 'cogs_ratio_adj', value: 0.01 }])} disabled={draft.length >= 10}>Add assumption</button>
            <button onClick={submit} disabled={busy}>{busy ? 'Calculating…' : 'Create & calculate'}</button>
          </div>
          {formErr && <div className="state error" role="alert">{formErr}</div>}
        </div>
        <div className="panel">
          <h3>{scenario ? scenario.name : 'Scenario result'}</h3>
          <Status loading={busy && !scenario} error={loadErr} empty={!r}>
            {r && <>
              <p className="scope">{r.periods[0]} to {r.periods[r.periods.length - 1]} · method {r.method}</p>
              <h4>Assumptions applied</h4>
              {r.assumptions.length === 0 ? <p className="note">None (baseline).</p> :
                <ul className="assumptions">{r.assumptions.map((a, i) => <li key={i}><strong>{a.name}</strong>: {a.value} <span className="note">({a.unit}{a.department ? `, ${a.department}` : ', all departments'})</span>{a.description ? <div className="note">{a.description}</div> : null}</li>)}</ul>}
              <table>
                <thead><tr><th>Metric</th><th className="r">Scenario</th><th className="r">Baseline</th><th className="r">Change</th><th></th></tr></thead>
                <tbody>{Object.entries(r.comparison_against_baseline).map(([m, c]) => (
                  <tr key={m}><td>{label(m)}</td><td className="r num">{fmtMetric(m, c.scenario)}</td><td className="r num">{fmtMetric(m, c.baseline)}</td>
                    <td className="r num">{fmtChange(m, c.absolute_change, m.endsWith('_pct') ? undefined : c.percentage_change)}</td><td><Badge value={c.assessment} /></td></tr>))}</tbody>
              </table>
            </>}
          </Status>
        </div>
      </div>
      {r && cashData && <div className="panel">
        <h3>Projected ending cash: scenario vs baseline</h3>
        <ResponsiveContainer width="100%" height={260}>
          <LineChart data={cashData} margin={{ left: 20, right: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" /><XAxis dataKey="period" />
            <YAxis tickFormatter={v => usdCompact(v)} width={80} domain={['auto', 'auto']} /><Tooltip formatter={(v: number) => usd(v)} /><Legend />
            <Line dataKey="baseline" name="Baseline" stroke="#94a3b8" strokeDasharray="4 4" />
            <Line dataKey="scenario" name="Scenario" stroke="#1e3a5f" strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
        <p className="note">Cash model: opening {usd(Number(r.cash.assumptions.opening_cash))}; collection days {String(r.cash.assumptions.collection_days)} (baseline {String(r.cash.assumptions.baseline_collection_days)}); {String(r.cash.assumptions.payment_timing)}. Every month reconciles: <Badge value={r.cash.reconciled ? 'passed' : 'failed'} /></p>
        <Warnings items={r.caveats} />
      </div>}
      <div className="panel">
        <h3>Which assumptions matter most? (operating income, standard one-at-a-time shocks)</h3>
        <Status loading={ranking.loading} error={ranking.error}>
          <table><thead><tr><th>Assumption</th><th className="r">Low shock</th><th className="r">Impact</th><th className="r">High shock</th><th className="r">Impact</th></tr></thead>
            <tbody>{ranking.data?.ranking.map(x => <tr key={x.assumption}><td>{spec(x.assumption)?.name ?? x.assumption}</td>
              <td className="r num">{x.low_value}</td><td className="r num">{signedUsd(x.impact_low)}</td><td className="r num">{x.high_value}</td><td className="r num">{signedUsd(x.impact_high)}</td></tr>)}</tbody></table>
          <p className="note">{ranking.data?.method}</p>
        </Status>
      </div>
    </div>
  );
}

export default ScenarioPlanning;
