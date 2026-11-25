import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/client";
import type { LlmStatus } from "../api/types";
import { useApi } from "../hooks/useApi";
import { analyseTemp, validateFile, type Progress, type TempValidation } from "../utils/tempSession";
import { num } from "../utils/format";
import { Card, Kpi } from "./ui";

/** Your own CSV: checked, read by the engine in short steps, and shown in this browser tab. Nothing is stored on the server. */
export default function UploadPanel({ title = true }: { title?: boolean }) {
  const input = useRef<HTMLInputElement>(null);
  const status = useApi<LlmStatus>("/llm/status");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<{ message: string; items: string[] } | null>(null);
  const [val, setVal] = useState<TempValidation | null>(null);
  const [prog, setProg] = useState<{ phase: string; done: number; total: number; message: string } | null>(null);
  const [resultId, setResultId] = useState<string | null>(null);
  const configured = status.data?.configured ?? false;

  const fail = (e: unknown) => {
    if (e instanceof ApiError) {
      const list = ((e.details as { errors?: { message: string; code: string }[] } | undefined)?.errors ?? []).map((x) => `${x.code}: ${x.message}`);
      setErr({ message: e.message, items: list });
    } else setErr({ message: String(e), items: [] });
  };
  async function onFile(f: File) {
    setBusy(true); setErr(null); setVal(null); setProg(null); setResultId(null);
    try { setVal(await validateFile(f)); } catch (e) { fail(e); } finally { setBusy(false); if (input.current) input.current.value = ""; }
  }
  async function analyse() {
    if (!val) return;
    setBusy(true); setErr(null); setResultId(null);
    const onProgress: Progress = (phase, done, total, message) => setProg({ phase, done, total, message });
    try { setResultId(await analyseTemp(val, onProgress)); } catch (e) { fail(e); setProg(null); } finally { setBusy(false); }
  }
  const pctDone = prog && prog.total ? Math.round((100 * prog.done) / prog.total) : 5;
  const s = val?.summary;
  return (
    <div id="upload">
      {title && <h2 className="panel__title">Analyse your own comments with AI</h2>}
      <Card accent="blue">
        {configured
          ? <p className="callout">Your file is read by an LLM and shown on the next page. It is used for this visit only: <b>nothing is stored</b> on the server, nobody else can see it, and the result disappears when you close this tab. Results are AI-generated and every quote is checked against your file. Large files are limited to the first {val?.analysis_row_limit ?? 300} reviews.</p>
          : <p className="callout callout--amber">The AI provider is not configured on the backend, so files can be checked but <b>not analysed</b>.</p>}
        <div className="upload__row">
          <label className="btn btn--primary">Choose a CSV file<input ref={input} type="file" accept=".csv,text/csv" hidden disabled={busy} onChange={(e) => e.target.files?.[0] && onFile(e.target.files[0])} /></label>
          <span className="gcard__sub">Needs a review-text column (text, review, comment…). Optional: review_id, rating, date, source, source_url, city, category.</span>
        </div>
        {busy && !prog && <p className="gcard__sub">Checking your file…</p>}
        {err && <div className="state state--error" role="alert"><strong>{err.message}</strong>{err.items.map((x) => <span key={x}>{x}</span>)}</div>}
        {val && s && (
          <div className="upload__out">
            <div className="kpis kpis--4">
              <Kpi label="Rows in file" value={num(s.rows_in_file)} /><Kpi tone="violet" label="Accepted" value={num(s.accepted)} />
              <Kpi tone="amber" label="Rejected" value={num(s.rejected)} sub={`${s.duplicates_in_file} duplicates · ${s.malformed} malformed`} /><Kpi label="Already in dataset" value={num(s.already_in_approved_dataset)} />
            </div>
            <p className="gcard__sub">Columns recognised: {Object.entries(val.validation.column_mapping).map(([k, v]) => `${k} ← “${v}”`).join(" · ")}</p>
            {val.validation.issues.length > 0 && <div className="tablewrap"><table className="tbl"><thead><tr><th>Line</th><th>Type</th><th>Code</th><th>Message</th></tr></thead><tbody>{val.validation.issues.slice(0, 12).map((i, k) => <tr key={k}><td>{i.line}</td><td>{i.severity}</td><td>{i.code}</td><td>{i.message}</td></tr>)}</tbody></table></div>}
            {!busy && !resultId && <button type="button" className="btn btn--primary" onClick={analyse} disabled={!configured}>Analyse with AI</button>}
            {busy && prog && (
              <div className="callout"><b>Analysing</b>: {prog.message}
                <div className="progress" role="progressbar" aria-valuenow={pctDone} aria-valuemin={0} aria-valuemax={100}><i style={{ width: `${pctDone}%` }} /></div>
                <small>Step: {prog.phase}{prog.total ? ` (${prog.done}/${prog.total})` : ""}. This can take a minute or more; please keep this page open.</small></div>)}
            {resultId && <div className="callout"><b>Analysis complete.</b> <div className="chips"><Link to={`/results/${resultId}`} className="btn btn--primary">View the results →</Link></div></div>}
          </div>
        )}
      </Card>
    </div>
  );
}
