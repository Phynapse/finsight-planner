import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { evidenceApi, financialsApi, errorMessage } from '../services/api';
import { useAsync, Status, Badge, Warnings, label, fmtMetric, fmtChange, usd } from '../components/ui';

function FinancialEvidence() {
  const [params, setParams] = useSearchParams();
  const id = params.get('id') || '';
  const list = useAsync(() => evidenceApi.list(), []);
  const pkg = useAsync(() => (id ? evidenceApi.get(id) : Promise.resolve(null)), [id]);
  const cash = useAsync(() => financialsApi.cashFlow(), []);
  const [runErr, setRunErr] = useState<string | null>(null);

  useEffect(() => {
    if (!id && list.data?.length) setParams({ id: list.data[0].analysis_id }, { replace: true });
  }, [id, list.data, setParams]);

  const run = async (body: Record<string, unknown>) => {
    setRunErr(null);
    try { const r = await evidenceApi.runAnalysis(body); list.reload(); setParams({ id: r.analysis_id }); }
    catch (e) { setRunErr(errorMessage(e)); }
  };
  const p = pkg.data;

  return (
    <div className="page">
      <h2>Financial Evidence</h2>
      <div className="info-box"><p>Evidence packages are produced by the deterministic analytics for each analysis (Ask Finance or direct analyses). They are held in memory and cleared when the API restarts.</p></div>
      <div className="filters">
        <label>Analysis<select value={id} onChange={e => setParams({ id: e.target.value })}>
          <option value="">{list.data?.length ? 'Select…' : 'No analyses yet'}</option>
          {list.data?.map(a => <option key={a.analysis_id} value={a.analysis_id}>{a.analysis_id} · {a.analysis_type}{a.question ? ` · ${a.question.slice(0, 50)}` : ''}</option>)}
        </select></label>
        <button className="secondary" onClick={() => run({ analysis_type: 'variance_analysis', comparison: 'actual_vs_budget' })}>Run actual vs budget analysis</button>
        <button className="secondary" onClick={() => run({ analysis_type: 'cash_flow_analysis' })}>Run cash-flow analysis</button>
      </div>
      {runErr && <div className="state error">{runErr}</div>}
      <Status loading={pkg.loading} error={pkg.error} empty={!p}>
        {p && <>
          <div className="panel">
            <div className="meta-row"><strong>{p.analysis_id}</strong><span>{p.analysis_type}</span><Badge value={p.complete ? 'complete' : 'incomplete'} /><span className="note">{p.created_at}</span></div>
            {p.question && <p>Question: <em>{p.question}</em></p>}
            <p className="scope">Scope: {Object.entries(p.scope).filter(([, v]) => v !== null && v !== undefined).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : String(v)}`).join(' · ') || 'all data'}</p>
            <p className="scope">Sources: {p.source_datasets.map(d => `${d} (${String((p.provenance.files as Record<string, string>)?.[d] ?? '')})`).join(', ')} · {String(p.provenance.generated_by)} · {String(p.provenance.engine_version)}</p>
          </div>
          <div className="table-container"><table>
            <thead><tr><th>ID</th><th>Metric</th><th>Kind</th><th>Period</th><th>Dimension</th><th className="r">Value</th><th className="r">Comparison</th><th className="r">Change</th><th>Source</th><th>Calculation</th></tr></thead>
            <tbody>{p.items.map(i => {
              const m = i.unit === '%' ? '_pct' : i.metric;
              return (<tr key={i.evidence_id}><td className="mono">{i.evidence_id.split('-').pop()}</td><td>{label(i.metric)}</td><td>{i.kind}</td><td>{i.period}</td><td>{i.dimension}</td>
                <td className="r num">{fmtMetric(m, i.value)}</td><td className="r num">{i.comparison_value === null ? '' : fmtMetric(m, i.comparison_value)}</td>
                <td className="r num">{i.absolute_change === null ? '' : fmtChange(m, i.absolute_change, i.unit === '%' ? undefined : i.percentage_change)} {i.assessment && <Badge value={i.assessment} />}</td>
                <td>{i.source_dataset}{i.comparison_source ? ` vs ${i.comparison_source}` : ''}</td><td className="small">{i.formula_id ? `${i.formula_id}: ` : ''}{i.calculation_description}</td></tr>);
            })}</tbody>
          </table></div>
          {p.reconciliation.length > 0 && <div className="table-container"><h3 className="tbl-title">Reconciliation</h3><table>
            <thead><tr><th>Check</th><th>Status</th><th className="r">Difference</th><th>Detail</th></tr></thead>
            <tbody>{p.reconciliation.map((r, k) => <tr key={k}><td>{r.check}</td><td><Badge value={r.status} /></td><td className="r num">{r.difference === null ? '' : r.difference.toFixed(2)}</td><td>{r.detail}</td></tr>)}</tbody>
          </table></div>}
          {p.assumptions.length > 0 && <div className="table-container"><h3 className="tbl-title">Assumptions</h3><table>
            <thead><tr><th>Assumption</th><th className="r">Value</th><th>Unit / note</th><th>Department</th></tr></thead>
            <tbody>{p.assumptions.map((a, k) => <tr key={k}><td>{String(a.name ?? a.key)}</td><td className="r num">{String(a.value)}</td><td>{String(a.unit ?? a.note ?? '')}</td><td>{String(a.department ?? 'all')}</td></tr>)}</tbody>
          </table></div>}
          <Warnings items={[...p.warnings, ...p.missing_data]} />
        </>}
      </Status>
      <div className="panel">
        <h3>Cash-flow source reconciliation (cash_flow.csv)</h3>
        <Status loading={cash.loading} error={cash.error}>
          {cash.data && <>
            <p className="scope">{cash.data.history.reconciled_rows} of {cash.data.history.total_rows} rows satisfy Ending = Opening + Collections + Other − Payments − Payroll − Capex − Debt.</p>
            <div className="table-container scroll"><table>
              <thead><tr><th>Period</th><th>BU</th><th>Status</th><th className="r">Opening</th><th className="r">Inflows</th><th className="r">Outflows</th><th className="r">Reported ending</th><th className="r">Calculated</th><th className="r">Difference</th><th></th></tr></thead>
              <tbody>{cash.data.history.rows.map((r, k) => <tr key={k}><td>{r.period}</td><td>{r.business_unit}{r.duplicate ? ' (duplicate)' : ''}</td><td>{r.status}</td>
                <td className="r num">{usd(r.opening_cash)}</td><td className="r num">{usd(r.cash_inflows)}</td><td className="r num">{usd(r.cash_outflows)}</td>
                <td className="r num">{usd(r.ending_cash_reported)}</td><td className="r num">{usd(r.ending_cash_calculated)}</td><td className="r num">{usd(r.reconciliation_difference)}</td>
                <td><Badge value={r.reconciled ? 'passed' : 'failed'} /></td></tr>)}</tbody>
            </table></div>
            <Warnings items={cash.data.history.warnings} />
          </>}
        </Status>
      </div>
    </div>
  );
}

export default FinancialEvidence;
