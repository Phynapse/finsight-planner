import { useState } from 'react';
import { financialsApi } from '../services/api';
import { useAsync, Status, Badge, Warnings, label, fmtMetric, fmtChange, signedUsd, usd } from '../components/ui';

const COMPARISONS: Record<string, string> = {
  actual_vs_budget: 'Actual vs Budget', actual_vs_forecast: 'Actual vs Forecast',
  forecast_vs_budget: 'Forecast vs Budget', year_over_year: 'Actual vs prior year (same month)',
};

function FinancialPerformance() {
  const meta = useAsync(() => financialsApi.meta(), []);
  const [comparison, setComparison] = useState('actual_vs_budget');
  const [period, setPeriod] = useState('');
  const [bu, setBu] = useState('');
  const [dept, setDept] = useState('');
  const needsPeriod = comparison === 'year_over_year';
  const effPeriod = needsPeriod && !period ? meta.data?.latest_actual_period : period;
  const v = useAsync(() => (needsPeriod && !effPeriod) ? Promise.resolve(null) : financialsApi.variance({
    comparison, periods: effPeriod ? [effPeriod] : undefined, business_unit: bu || undefined, department: dept || undefined,
    group_by: needsPeriod ? undefined : 'department',
  }), [comparison, effPeriod, bu, dept]);
  const d = v.data;
  const allPeriods = meta.data ? Array.from(new Set([...meta.data.periods.actual, ...meta.data.periods.budget, ...meta.data.periods.forecast])).sort() : [];

  return (
    <div className="page">
      <h2>Financial Performance</h2>
      <div className="info-box"><p>Variances use <code>current − comparison</code>; % = variance ÷ |comparison|. Expense increases are <strong>unfavourable</strong>. Only records present in both datasets are compared.</p></div>
      <div className="filters">
        <label>Comparison<select value={comparison} onChange={e => setComparison(e.target.value)}>
          {Object.entries(COMPARISONS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
        <label>Period<select value={period} onChange={e => setPeriod(e.target.value)}>
          <option value="">{needsPeriod ? `Latest (${meta.data?.latest_actual_period ?? ''})` : 'All matched periods'}</option>
          {allPeriods.map(p => <option key={p}>{p}</option>)}</select></label>
        <label>Business unit<select value={bu} onChange={e => setBu(e.target.value)}>
          <option value="">All</option>{meta.data?.business_units.map(b => <option key={b}>{b}</option>)}</select></label>
        <label>Department<select value={dept} onChange={e => setDept(e.target.value)}>
          <option value="">All</option>{meta.data?.departments.map(b => <option key={b}>{b}</option>)}</select></label>
      </div>
      <Status loading={v.loading} error={v.error}>
        {d && <>
          <p className="scope">{d.matched_records} matched records · periods: {d.matched_periods.join(', ') || 'none'} · excluded (no counterpart): {d.unmatched_current_records} current / {d.unmatched_comparison_records} comparison</p>
          {d.statement ? <>
            <div className="table-container"><table>
              <thead><tr><th>Metric</th><th className="r">Current</th><th className="r">Comparison</th><th className="r">Variance</th><th>Assessment</th></tr></thead>
              <tbody>{Object.entries(d.statement).map(([m, s]) => (
                <tr key={m}><td>{label(m)}</td><td className="r num">{fmtMetric(m, s.value)}</td><td className="r num">{fmtMetric(m, s.comparison_value)}</td>
                  <td className="r num">{fmtChange(m, s.absolute_variance, m.endsWith('_pct') ? undefined : s.percentage_variance)}</td><td><Badge value={s.assessment} /></td></tr>))}</tbody>
            </table></div>
            {d.bridge && <div className="panel">
              <h3>Operating income variance bridge</h3>
              <div className="bridge">
                <div><span>Revenue</span><strong className="num">{signedUsd(d.bridge.revenue_contribution)}</strong></div>
                <div><span>− COGS</span><strong className="num">{signedUsd(d.bridge.cogs_contribution)}</strong></div>
                <div><span>− Operating expenses</span><strong className="num">{signedUsd(d.bridge.operating_expense_contribution)}</strong></div>
                <div className="total"><span>= Operating income variance</span><strong className="num">{signedUsd(d.bridge.calculated_operating_income_variance)}</strong></div>
              </div>
              <p className="note">{d.bridge.formula}. Reconciliation difference {usd(d.bridge.reconciliation_difference)} (tolerance {d.bridge.tolerance}) — <Badge value={d.bridge.reconciled ? 'passed' : 'failed'} /></p>
            </div>}
            {d.groups.length > 0 && <div className="table-container"><h3 className="tbl-title">By department</h3><table>
              <thead><tr><th>Department</th><th className="r">Revenue var.</th><th className="r">COGS var.</th><th className="r">Opex var.</th><th className="r">Operating income var.</th><th>Assessment</th></tr></thead>
              <tbody>{d.groups.map(g => (
                <tr key={String(g.department)}><td>{String(g.department)}</td>
                  {['revenue', 'cogs', 'operating_expenses', 'operating_income'].map(m => <td key={m} className="r num">{fmtChange(m, g.statement[m].absolute_variance, g.statement[m].percentage_variance)}</td>)}
                  <td><Badge value={g.statement.operating_income.assessment} /></td></tr>))}</tbody>
            </table></div>}
            <div className="table-container"><h3 className="tbl-title">Material line variances (|var| ≥ $10,000 and |%| ≥ 5%)</h3>
              {d.material_variances.length === 0 ? <div className="state">None in this scope.</div> : <table>
                <thead><tr><th>Period</th><th>Unit</th><th>Line</th><th className="r">Current</th><th className="r">Comparison</th><th className="r">Variance</th><th>Assessment</th></tr></thead>
                <tbody>{d.material_variances.map((r, i) => (
                  <tr key={i}><td>{r.period}</td><td>{r.business_unit} / {r.department}</td><td>{label(r.metric)}</td>
                    <td className="r num">{usd(r.value)}</td><td className="r num">{usd(r.comparison_value)}</td>
                    <td className="r num">{fmtChange(r.metric, r.absolute_variance, r.percentage_variance)}</td><td><Badge value={r.assessment} /></td></tr>))}</tbody>
              </table>}
            </div>
          </> : <div className="state">No overlapping records for this comparison and scope — no variance can be calculated.</div>}
          <Warnings items={[...d.warnings, 'Variances are calculated differences; causes (volume, price, timing) are not established by the data.']} />
        </>}
      </Status>
    </div>
  );
}

export default FinancialPerformance;
