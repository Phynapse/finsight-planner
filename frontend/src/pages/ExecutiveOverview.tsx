import { useState } from 'react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, Legend, CartesianGrid } from 'recharts';
import { financialsApi } from '../services/api';
import { useAsync, Status, Kpi, Warnings, usd, usdCompact, pct, fmtChange } from '../components/ui';

function ExecutiveOverview() {
  const meta = useAsync(() => financialsApi.meta(), []);
  const [period, setPeriod] = useState('');
  const [bu, setBu] = useState('North America');
  const summary = useAsync(() => financialsApi.summary({ period: period || undefined, business_unit: bu || undefined }), [period, bu]);
  const trend = useAsync(() => financialsApi.trend({ business_unit: bu || undefined }), [bu]);
  const s = summary.data;
  const st = s?.statement;
  const yoyRev = s?.year_over_year?.statement?.revenue;
  const bud = s?.budget_comparison?.statement?.operating_income;

  return (
    <div className="page">
      <h2>Executive Overview</h2>
      <div className="info-box"><p><strong>Asteron Group</strong> — entirely synthetic data. All figures are calculated by the backend from the CSV datasets.</p></div>
      <div className="filters">
        <label>Period
          <select value={period} onChange={e => setPeriod(e.target.value)}>
            <option value="">Latest actual ({meta.data?.latest_actual_period ?? '…'})</option>
            {meta.data?.periods.actual.map(p => <option key={p}>{p}</option>)}
          </select>
        </label>
        <label>Business unit
          <select value={bu} onChange={e => setBu(e.target.value)}>
            <option value="">All reporting units</option>
            {meta.data?.business_units.map(b => <option key={b}>{b}</option>)}
          </select>
        </label>
      </div>
      <Status loading={summary.loading} error={summary.error} empty={!st}>
        {s && st && <>
          <p className="scope">Period <strong>{s.period}</strong> · Units: {s.scope.units.join(', ')}</p>
          <div className="metrics-grid">
            <Kpi title="Revenue" value={usd(st.revenue)} sub={yoyRev ? `vs ${s.prior_year_period}: ${fmtChange('revenue', yoyRev.absolute_variance, yoyRev.percentage_variance)} (matched records)` : `No ${s.prior_year_period} comparison`} tone={yoyRev?.assessment} />
            <Kpi title="Gross profit" value={usd(st.gross_profit)} sub={`Gross margin ${pct(st.gross_margin_pct)}`} />
            <Kpi title="Operating expenses" value={usd(st.operating_expenses)} sub={st.missing_lines.length ? `Unreported lines: ${st.missing_lines.join(', ')}` : 'All lines reported'} />
            <Kpi title="Operating income" value={usd(st.operating_income)} sub={`Operating margin ${pct(st.operating_margin_pct)}`} />
            <Kpi title="Operating income vs budget" value={bud ? fmtChange('operating_income', bud.absolute_variance, bud.percentage_variance) : 'No budget'}
              sub={bud ? `${s.budget_comparison.matched_records} matched budget records` : `Budget has no records for ${s.period} in this scope`} tone={bud?.assessment} />
            <Kpi title="Ending cash (reported)" value={s.cash ? usd(s.cash.ending_cash) : 'n/a'} sub={s.cash ? s.cash.business_units.join(', ') : 'No cash row for this period/scope'} />
          </div>
          <Warnings items={s.warnings} />
        </>}
      </Status>
      <div className="panel">
        <h3>Actuals trend {bu ? `— ${bu}` : '— all units'}</h3>
        <Status loading={trend.loading} error={trend.error} empty={!trend.data?.rows.length}>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={trend.data?.rows ?? []} margin={{ left: 20, right: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="period" />
              <YAxis tickFormatter={v => usdCompact(v)} width={80} />
              <Tooltip formatter={(v: number) => usd(v)} />
              <Legend />
              <Line type="monotone" dataKey="revenue" name="Revenue" stroke="#1e3a5f" strokeWidth={2} />
              <Line type="monotone" dataKey="operating_expenses" name="Operating expenses" stroke="#b45309" />
              <Line type="monotone" dataKey="operating_income" name="Operating income" stroke="#15803d" />
            </LineChart>
          </ResponsiveContainer>
          <p className="note">Actuals cover 13 sampled months (not a continuous series); the x-axis shows only reported months.</p>
          <Warnings items={trend.data?.warnings} />
        </Status>
      </div>
    </div>
  );
}

export default ExecutiveOverview;
