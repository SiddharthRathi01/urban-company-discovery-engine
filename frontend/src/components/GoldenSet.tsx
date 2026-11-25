import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, getFresh, postForm, postJson } from "../api/client";
import type { GoldenMeta, GoldenRow, GoldenSummary } from "../api/types";
import { num, pct } from "../utils/format";
import { Card, Chip, Kpi, SentimentChip } from "./ui";

const FIELDS: { key: string; label: string; required?: boolean; hint?: string }[] = [
  { key: "text", label: "Comment text", required: true },
  { key: "id", label: "Record ID (optional)" },
  { key: "human_sentiment", label: "Your sentiment", hint: "Positive / Negative / Neutral / Mixed" },
  { key: "human_return", label: "Your return label", hint: "Return / Non-Return / Insufficient Evidence" },
  { key: "human_theme", label: "Your problem label (optional)" },
  { key: "rating", label: "Star rating (optional)" },
  { key: "source_url", label: "Source URL (optional)" },
];

function parseHeader(text: string): string[] {
  const line = text.split(/\r?\n/).find((l) => l.trim()) ?? "";
  const delim = [",", ";", "\t", "|"].map((d) => [d, line.split(d).length] as const).sort((a, b) => b[1] - a[1])[0][0];
  const out: string[] = []; let cur = "", q = false;
  for (const ch of line) {
    if (ch === '"') q = !q;
    else if (ch === delim && !q) { out.push(cur.trim()); cur = ""; }
    else cur += ch;
  }
  out.push(cur.trim());
  return out.filter(Boolean);
}

const TONE = { "Full match": "pos", "Partial match": "mix", "Non-match": "neg", "Not analysed": "plain" } as const;
const MATCH_COLOR = { "Full match": "var(--pos)", "Partial match": "var(--mix)", "Non-match": "var(--neg)" } as const;
const tick = (m: boolean | null) => (m === null ? "–" : m ? "✓" : "✗");

function csvEscape(v: unknown) { const s = v == null ? "" : String(v); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; }

/** The golden set (hand-labelled comments) compared with what the engine says, plus upload of a new one. */
export default function GoldenSet() {
  const [sets, setSets] = useState<GoldenMeta[] | null>(null);
  const [rows, setRows] = useState<GoldenRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try { setSets((await getFresh<GoldenMeta[]>("/golden")).data); } catch (e) { setError(e instanceof ApiError ? e.message : String(e)); setSets([]); }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);

  const evaluated = (sets ?? []).filter((s) => s.evaluated);
  const shown = evaluated.find((s) => s.primary) ?? evaluated[0] ?? null;
  const ev: GoldenSummary | undefined = shown?.evaluation_summary;

  useEffect(() => {
    if (!shown) { setRows([]); return; }
    getFresh<GoldenRow[]>(`/golden/${shown.golden_id}/rows`, { match: filter, page, page_size: 10 }).then((r) => { setRows(r.data); setTotal(r.meta.total ?? 0); }).catch(() => setRows([]));
  }, [shown?.golden_id, filter, page]); // eslint-disable-line react-hooks/exhaustive-deps

  async function download() {
    if (!shown) return;
    const all: GoldenRow[] = [];
    for (let p = 1; p < 20; p++) {
      const r = await getFresh<GoldenRow[]>(`/golden/${shown.golden_id}/rows`, { page: p, page_size: 200 });
      all.push(...r.data);
      if (all.length >= (r.meta.total ?? 0)) break;
    }
    const head = ["review_id", "review_text", "human_sentiment", "engine_sentiment", "sentiment_match", "human_return", "engine_return", "engine_return_basis", "return_match", "human_theme", "engine_themes", "match_status", "source_url"];
    const csv = [head.join(","), ...all.map((r) => [r.review_id, r.review_text, r.human_sentiment, r.engine_sentiment, r.sentiment_match, r.human_return, r.engine_return, r.engine_return_basis, r.return_match, r.human_theme, r.engine_themes.join("; "), r.match_status, r.source_url].map(csvEscape).join(","))].join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv" })); a.download = `golden_set_comparison_${shown.golden_id}.csv`; a.click();
  }

  return (
    <div className="golden">
      {error && <div className="state state--error">{error}</div>}
      {shown && ev ? (
        <GoldenCard title="Official golden set" sub={`“${shown.name}”. Each comment was labelled by a person; the engine's answer is compared with that label. This set is permanent and cannot be changed or deleted.`} ev={ev} rows={rows} total={total} page={page} setPage={setPage} filter={filter} setFilter={setFilter} onDownload={download} />
      ) : sets !== null && (
        <Card title="Golden set" accent="amber">
          <p className="ans__text">No golden set has been uploaded yet, so <b>no accuracy figure is claimed</b>. Upload a CSV of comments that a person has labelled (sentiment and/or Return / Non-Return). The engine will be run on those comments and its answers compared with yours, exactly like this card.</p>
        </Card>
      )}
      <GoldenUpload />
    </div>
  );
}

function GoldenCard({ title, sub, ev, rows, total, page, setPage, filter, setFilter, onDownload }: { title: string; sub: string; ev: GoldenSummary; rows: GoldenRow[]; total: number; page: number; setPage: (n: number) => void; filter: string; setFilter: (s: string) => void; onDownload: () => void }) {
  return (
    <Card title={`${title}: ${num(ev.rows)} comments labelled by hand`} sub={sub}>
      <div className="gs-bar" role="img" aria-label={Object.entries(ev.match_counts).map(([k, v]) => `${v} ${k}`).join(", ")}>
        {(["Full match", "Partial match", "Non-match"] as const).map((k) => ev.match_counts[k] > 0 && <span key={k} style={{ flex: ev.match_counts[k], background: MATCH_COLOR[k] }}>{ev.match_counts[k]}</span>)}
      </div>
      <div className="gs-key"><span><i style={{ background: MATCH_COLOR["Full match"] }} /><b>{ev.match_counts["Full match"]} full matches</b>: every label you gave agrees with the engine</span>
        <span><i style={{ background: MATCH_COLOR["Partial match"] }} /><b>{ev.match_counts["Partial match"]} partial matches</b>: some labels agree, some do not</span>
        <span><i style={{ background: MATCH_COLOR["Non-match"] }} /><b>{ev.match_counts["Non-match"]} non-matches</b>: none agree{ev.match_counts["Not analysed"] > 0 && ` · ${ev.match_counts["Not analysed"]} not analysed`}</span></div>
      <div className="kpis kpis--3">
        <Kpi tone="violet" label="Sentiment agreement" value={ev.sentiment.agreement_pct == null ? "–" : pct(ev.sentiment.agreement_pct, 0)} sub={`${ev.sentiment.agree} of ${ev.sentiment.compared} · ${ev.sentiment.kappa ?? "–"} agreement beyond chance${ev.sentiment.agreement_pct_excluding_mixed != null ? ` · ${pct(ev.sentiment.agreement_pct_excluding_mixed, 0)} without “Mixed”` : ""}`} />
        <Kpi tone="amber" label="Return / Non-Return agreement" value={ev.return.agreement_pct == null ? "–" : pct(ev.return.agreement_pct, 0)} sub={`${ev.return.agree} of ${ev.return.compared} · ${ev.return.kappa ?? "–"} agreement beyond chance`} />
        <Kpi label="When both gave a call" value={ev.return.agreement_pct_when_both_classified == null ? "–" : pct(ev.return.agreement_pct_when_both_classified, 0)} sub={`${ev.return.both_classified} comments where neither said “Insufficient”`} />
      </div>
      <p className="callout callout--amber">{ev.caution}</p>
      <div className="gs-tools">
        <div className="pills">{["", "Full match", "Partial match", "Non-match"].map((f) => <button key={f} type="button" className={`pill ${filter === f ? "is-on" : ""}`} onClick={() => { setFilter(f); setPage(1); }}>{f || "All comments"}</button>)}</div>
        <div className="chips">
          <button type="button" className="btn" onClick={onDownload}>⬇ Download comparison (CSV)</button>
        </div>
      </div>
      <div className="tablewrap"><table className="tbl gs-table"><thead><tr><th>ID</th><th>Comment</th><th>Your sentiment</th><th>Engine</th><th /><th>Your return label</th><th>Engine</th><th /><th>Your problem label</th><th>Engine themes</th><th>Result</th></tr></thead>
        <tbody>{rows.map((r) => (
          <tr key={r.row_id}><td>{r.review_id}</td><td className="gs-text">{r.review_text.length > 160 ? r.review_text.slice(0, 160) + "…" : r.review_text}</td>
            <td>{r.human_sentiment ? <SentimentChip s={r.human_sentiment as never} /> : "–"}</td><td>{r.engine_sentiment ? <SentimentChip s={r.engine_sentiment as never} /> : "–"}</td><td className={r.sentiment_match ? "ok" : r.sentiment_match === false ? "no" : ""}>{tick(r.sentiment_match)}</td>
            <td>{r.human_return ?? "–"}</td><td>{r.engine_return ?? "–"}{r.engine_return_basis && r.engine_return_basis !== "None" ? <small> · {r.engine_return_basis}</small> : null}</td><td className={r.return_match ? "ok" : r.return_match === false ? "no" : ""}>{tick(r.return_match)}</td>
            <td>{r.human_theme ?? "–"}</td><td>{r.engine_themes.join(", ") || "–"}</td><td><Chip tone={TONE[r.match_status as keyof typeof TONE]}>{r.match_status}</Chip></td></tr>))}</tbody></table></div>
      <div className="lab__nav"><button className="btn" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Previous</button><span className="gcard__sub">Page {page} of {Math.max(1, Math.ceil(total / 10))} · {num(total)} comments</span><button className="btn" disabled={page * 10 >= total} onClick={() => setPage(page + 1)}>Next →</button></div>
    </Card>

  );
}

function GoldenUpload() {
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [header, setHeader] = useState<string[]>([]);
  const [map, setMap] = useState<Record<string, string>>({});
  const [err, setErr] = useState<{ message: string; items: string[] } | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ name: string; ev: GoldenSummary; all: GoldenRow[] } | null>(null);
  const [page, setPage] = useState(1);
  const [filter, setFilter] = useState("");

  async function choose(f: File) {
    setErr(null); setResult(null);
    const h = parseHeader(await f.slice(0, 8192).text());
    setFile(f); setHeader(h);
    try {
      const form = new FormData(); form.append("header", JSON.stringify(h));
      setMap((await postForm<Record<string, string>>("/golden/preview-mapping", form)).data);
    } catch { setMap({}); }
  }
  async function run() {
    if (!file) return;
    setBusy(true); setErr(null); setResult(null); setPage(1); setFilter("");
    try {
      const form = new FormData(); form.append("file", file);
      form.append("mapping", JSON.stringify(Object.fromEntries(Object.entries(map).filter(([, v]) => v))));
      const v = (await postForm<{ rows: unknown[]; filename: string }>("/temp/golden/validate", form)).data;
      const ev = (await postJson<{ summary: GoldenSummary; rows: GoldenRow[] }>("/temp/golden/evaluate", { rows: v.rows })).data;
      setResult({ name: v.filename, ev: ev.summary, all: ev.rows });
    } catch (e) {
      if (e instanceof ApiError) {
        const list = ((e.details as { errors?: { message: string; code: string }[] } | undefined)?.errors ?? []).map((x) => `${x.code}: ${x.message}`);
        setErr({ message: e.message, items: list });
      } else setErr({ message: String(e), items: [] });
    } finally { setBusy(false); if (input.current) input.current.value = ""; }
  }
  const view = result ? result.all.filter((r) => !filter || r.match_status === filter) : [];
  function downloadTemp() {
    if (!result) return;
    const head = ["review_id", "review_text", "human_sentiment", "engine_sentiment", "human_return", "engine_return", "match_status"];
    const csv = [head.join(","), ...result.all.map((r) => [r.review_id, r.review_text, r.human_sentiment, r.engine_sentiment, r.human_return, r.engine_return, r.match_status].map(csvEscape).join(","))].join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob(["\ufeff" + csv], { type: "text/csv" })); a.download = "my_golden_set_comparison.csv"; a.click();
  }
  return (
    <>
      <Card title="Test the engine on your own hand-labelled comments" accent="blue" className="golden__upload">
        <p className="gcard__sub">Upload a CSV with the comment text and your own labels, and the engine will read every comment and compare. Your file is used for this visit only: nothing is stored, the official golden set above is never changed, and your result disappears when you leave or close this tab.</p>
        <div className="upload__row">
          <label className="btn btn--primary">Choose a CSV file<input ref={input} type="file" accept=".csv,text/csv" hidden onChange={(e) => e.target.files?.[0] && choose(e.target.files[0])} /></label>
          <span className="gcard__sub">{file ? file.name : "No file chosen"}</span>
        </div>
        {file && header.length > 0 && (
          <div className="gmap">
            <div className="gmap__grid">
              {FIELDS.map((f) => (
                <label key={f.key}>{f.label}{f.required && " *"}
                  <select className="sel" value={map[f.key] ?? ""} onChange={(e) => setMap({ ...map, [f.key]: e.target.value })}><option value="">{f.required ? "Choose a column" : "(none)"}</option>{header.map((h) => <option key={h}>{h}</option>)}</select>
                  {f.hint && <small>{f.hint}</small>}
                </label>))}
            </div>
            <p className="gcard__sub">Needs the comment text and at least one of your sentiment or your return label. Up to 100 comments.</p>
            <button type="button" className="btn btn--primary" disabled={busy || !map.text || (!map.human_sentiment && !map.human_return)} onClick={run}>Run the engine</button>
          </div>
        )}
        {err && <div className="state state--error" role="alert"><strong>{err.message}</strong>{err.items.map((x) => <span key={x}>{x}</span>)}</div>}
        {busy && <div className="callout"><b>Running the engine</b>: reading your comments. This takes about half a minute for 20 comments; keep this page open.<div className="progress"><i style={{ width: "40%" }} /></div></div>}
      </Card>
      {result && <GoldenCard title="Your temporary golden set" sub={`“${result.name}”. Shown for this visit only; it is not stored and will be gone when you close this tab.`} ev={result.ev} rows={view.slice((page - 1) * 10, page * 10)} total={view.length} page={page} setPage={setPage} filter={filter} setFilter={(f) => { setFilter(f); setPage(1); }} onDownload={downloadTemp} />}
    </>
  );
}
