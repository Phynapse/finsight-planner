import { FormEvent, useState } from 'react';
import { Link } from 'react-router-dom';
import { questionsApi, errorMessage } from '../services/api';
import type { QuestionResponse } from '../types';
import { useAsync, Warnings, Badge, label, fmtMetric, fmtChange } from '../components/ui';

function AskFinance() {
  const examples = useAsync(() => questionsApi.examples(), []);
  const [question, setQuestion] = useState('');
  const [result, setResult] = useState<QuestionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const ask = async (q: string) => {
    const text = q.trim();
    if (text.length < 3) { setError('Enter a question of at least 3 characters.'); return; }
    setLoading(true); setError(null); setResult(null);
    try { setResult(await questionsApi.ask(text)); } catch (e) { setError(errorMessage(e)); } finally { setLoading(false); }
  };
  const onSubmit = (e: FormEvent) => { e.preventDefault(); ask(question); };
  const ex = result?.explanation;
  const ev = result?.evidence;

  return (
    <div className="page">
      <h2>Ask Finance</h2>
      <div className="info-box"><p>Question → validated analysis plan → deterministic calculation → evidence → explanation. Numbers come only from the evidence package.
        {examples.data && <> LLM provider: <strong>{examples.data.llm_configured ? 'configured' : 'not configured (deterministic mode)'}</strong>.</>}</p></div>
      <form className="panel ask" onSubmit={onSubmit}>
        <label htmlFor="q" className="sr-only">Question</label>
        <input id="q" value={question} maxLength={500} onChange={e => setQuestion(e.target.value)} placeholder="e.g. Why is operating income below budget?" />
        <button type="submit" disabled={loading}>{loading ? 'Analysing…' : 'Ask'}</button>
      </form>
      <div className="examples">
        {examples.data?.examples.map(q => <button key={q} className="chip" onClick={() => { setQuestion(q); ask(q); }} disabled={loading}>{q}</button>)}
      </div>
      {error && <div className="state error" role="alert">{error}</div>}
      {result && <div className="panel answer">
        <div className="meta-row">
          <span>Question: <em>{result.question}</em></span>
          <span className="badge neutral">interpretation: {result.interpretation.method}</span>
          <span className={`badge ${result.explanation_method === 'llm' ? 'favourable' : 'neutral'}`}>explanation: {result.explanation_method === 'llm' ? 'LLM (grounded)' : result.explanation_method === 'deterministic_fallback' ? 'deterministic' : 'none'}</span>
          {ex?.llm_status && ex.llm_status !== 'ok' && ex.llm_status !== 'not_configured' && <span className="badge unfavourable">LLM: {ex.llm_status}</span>}
        </div>
        <p className="answer-text">{result.answer}</p>
        {result.status !== 'answered' && result.supported_examples && <p className="note">Try one of the supported examples above.</p>}
        {ex && <>
          <h4>Calculated findings</h4>
          <ul>{(ex.computed_findings ?? ex.key_findings).map((f, i) => <li key={i}>{f}</li>)}</ul>
          {ex.interpretations && ex.interpretations.length > 0 && <><h4>Possible interpretations (not established by data)</h4><ul>{ex.interpretations.map((f, i) => <li key={i}>{f}</li>)}</ul></>}
          {ex.assumptions.length > 0 && <><h4>Model assumptions</h4><ul>{ex.assumptions.map((f, i) => <li key={i}>{f}</li>)}</ul></>}
          <Warnings items={ex.caveats} />
        </>}
        {ev && <>
          <h4>Evidence <Link to={`/evidence?id=${ev.analysis_id}`}>{ev.analysis_id} →</Link></h4>
          <p className="scope">Scope: {Object.entries(ev.scope).filter(([, v]) => v !== null && v !== undefined).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : String(v)}`).join(' · ')}</p>
          <div className="table-container"><table>
            <thead><tr><th>Metric</th><th>Period</th><th>Dimension</th><th className="r">Value</th><th className="r">Comparison</th><th className="r">Change</th><th>Source</th></tr></thead>
            <tbody>{ev.items.slice(0, 15).map(i => (
              <tr key={i.evidence_id}><td>{label(i.metric)}</td><td>{i.period}</td><td>{i.dimension}</td>
                <td className="r num">{fmtMetric(i.unit === '%' ? '_pct' : i.metric, i.value)}</td>
                <td className="r num">{i.comparison_value === null ? '' : fmtMetric(i.unit === '%' ? '_pct' : i.metric, i.comparison_value)}</td>
                <td className="r num">{i.absolute_change === null ? '' : fmtChange(i.unit === '%' ? '_pct' : i.metric, i.absolute_change, i.unit === '%' ? undefined : i.percentage_change)} {i.assessment && <Badge value={i.assessment} />}</td>
                <td>{i.source_dataset}{i.comparison_source ? ` vs ${i.comparison_source}` : ''}</td></tr>))}</tbody>
          </table></div>
        </>}
      </div>}
    </div>
  );
}

export default AskFinance;
