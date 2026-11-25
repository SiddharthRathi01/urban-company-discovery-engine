import { useState } from "react";
import type { MoodRow, Opportunity } from "../api/types";
import { SENT_COLORS, num } from "../utils/format";

/** Horizontal stacked bar of sentiment counts. */
export function SentimentBar({ row, height = 14 }: { row: Pick<MoodRow, "positive" | "neutral" | "negative" | "mixed" | "uncertain" | "n">; height?: number }) {
  const parts: [string, number][] = [["Positive", row.positive], ["Neutral", row.neutral], ["Mixed", row.mixed], ["Negative", row.negative], ["Uncertain", row.uncertain]];
  return (
    <div className="sbar" style={{ height }} role="img" aria-label={parts.map(([k, v]) => `${v} ${k}`).join(", ")}>
      {parts.filter(([, v]) => v > 0).map(([k, v]) => (
        <span key={k} style={{ flex: v, background: SENT_COLORS[k] }} title={`${k}: ${num(v)} (${((100 * v) / row.n).toFixed(1)}%)`} />
      ))}
    </div>
  );
}

export function SentimentLegend({ items = ["Positive", "Neutral", "Mixed", "Negative"] }: { items?: string[] }) {
  return (
    <div className="legend">
      {items.map((k) => (
        <span key={k}><i style={{ background: SENT_COLORS[k] }} />{k}</span>
      ))}
    </div>
  );
}

/** Mood per row: stacked sentiment bar with the row label and count. */
export function MoodBars({ rows, labelWidth = 190, onPick }: { rows: MoodRow[]; labelWidth?: number; onPick?: (r: MoodRow) => void }) {
  return (
    <div className="moodbars">
      {rows.map((r) => (
        <div className="moodbars__row" key={r.key} style={{ gridTemplateColumns: `${labelWidth}px 1fr 78px` }}>
          {onPick ? (
            <button type="button" className="moodbars__label moodbars__label--btn" onClick={() => onPick(r)}>{r.label}<small>{num(r.n)} reviews</small></button>
          ) : (
            <span className="moodbars__label">{r.label}<small>{num(r.n)} reviews</small></span>
          )}
          <SentimentBar row={r} />
          <span className="moodbars__tag">{r.negative_share}% unhappy</span>
        </div>
      ))}
    </div>
  );
}

/** Unhappy (left, coral) vs positive (right, mint) review counts per row, on a shared scale. */
export function DivergingBars({ rows }: { rows: MoodRow[] }) {
  const max = Math.max(1, ...rows.map((r) => Math.max(r.negative + r.mixed, r.positive)));
  return (
    <div className="div">
      {rows.map((r) => (
        <div className="div__row" key={r.key}>
          <span className="div__label">{r.label}</span>
          <div className="div__bars" title={`${r.negative + r.mixed} unhappy (Negative + Mixed) and ${r.positive} positive of ${r.n} reviews`}>
            <span className="div__neg"><i style={{ width: `${(100 * (r.negative + r.mixed)) / max}%` }} /></span>
            <span className="div__pos"><i style={{ width: `${(100 * r.positive) / max}%` }} /></span>
          </div>
          <span className="div__n">{num(r.n)}</span>
        </div>
      ))}
    </div>
  );
}

const SCORE_PARTS = [
  { key: "frequency", label: "How many mention it", w: 0.25, color: "var(--violet)" },
  { key: "severity", label: "How unhappy they are", w: 0.2, color: "var(--neg)" },
  { key: "evidence_strength", label: "How strong the evidence is", w: 0.2, color: "var(--blue)" },
  { key: "repeat_relevance", label: "Link to switching and not returning", w: 0.2, color: "var(--amber)" },
] as const;

export function scoreParts(o: Opportunity) {
  const p = o.prioritisation;
  return [
    ...SCORE_PARTS.map((s) => ({ label: s.label, color: s.color, points: 100 * s.w * p[s.key] })),
    { label: "Analyst impact judgement", color: "var(--pink)", points: 100 * 0.15 * (p.impact_judgement_1_to_5 / 5) },
  ];
}

/** Stacked bar showing which of the scoring ingredients pushed the score up. */
export function ScoreStack({ o, legend = false }: { o: Opportunity; legend?: boolean }) {
  const parts = scoreParts(o);
  return (
    <div>
      <div className="sbar sbar--score" role="img" aria-label={parts.map((p) => `${p.label}: ${p.points.toFixed(0)} points`).join(", ")}>
        {parts.map((p) => (
          <span key={p.label} style={{ flex: p.points, background: p.color }} title={`${p.label}: ${p.points.toFixed(1)} points`} />
        ))}
      </div>
      {legend && (
        <div className="legend legend--wrap">
          {parts.map((p) => (
            <span key={p.label}><i style={{ background: p.color }} />{p.label} · {p.points.toFixed(0)}</span>
          ))}
        </div>
      )}
    </div>
  );
}

/** Bubble chart: x = how many reviews mention it, y = how strongly it links to switching / warning / not returning, size = priority score. */
export function BubbleChart({ items, onPick, selected }: { items: Opportunity[]; onPick?: (id: string) => void; selected?: string | null }) {
  const [hover, setHover] = useState<string | null>(null);
  const W = 560, H = 390, L = 56, R = 18, T = 16, B = 50;
  const xs = items.map((o) => o.evidence.pct_of_dataset), ys = items.map((o) => o.evidence.switching_or_warning_or_non_return_pct);
  const xmin = 0, xmax = Math.max(...xs) * 1.18, ymin = 0, ymax = Math.max(...ys) * 1.2;
  const X = (v: number) => L + ((v - xmin) / (xmax - xmin)) * (W - L - R);
  const Y = (v: number) => T + (1 - (v - ymin) / (ymax - ymin)) * (H - T - B);
  const maxS = Math.max(...items.map((o) => o.prioritisation.score));
  const rad = (sc: number) => 10 + 20 * (sc / maxS) ** 2;
  const mx = X((xmin + xmax) / 2), my = Y((ymin + ymax) / 2);
  const active = items.find((o) => o.opportunity_id === (hover ?? selected));
  return (
    <div className="bubble">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Opportunities by share of reviews and link to switching or not returning">
        <rect x={L} y={T} width={W - L - R} height={H - T - B} rx="12" className="bubble__plot" />
        <line x1={mx} y1={T} x2={mx} y2={H - B} className="bubble__guide" />
        <line x1={L} y1={my} x2={W - R} y2={my} className="bubble__guide" />
        <text x={L + 10} y={T + 20} className="bubble__quad">Smaller, tied to leaving: check</text>
        <text x={W - R - 10} y={T + 20} textAnchor="end" className="bubble__quad bubble__quad--hi">Widespread, tied to leaving: act</text>
        <text x={L + 10} y={H - B - 12} className="bubble__quad">Smaller, less tied to leaving</text>
        <text x={W - R - 10} y={H - B - 12} textAnchor="end" className="bubble__quad">Widespread, less tied</text>
        {[0, 5, 10, 15, 20].filter((v) => v <= xmax).map((v) => <text key={v} x={X(v)} y={H - B + 16} textAnchor="middle" className="bubble__tick">{v}%</text>)}
        {[0, 5, 10, 15, 20].filter((v) => v <= ymax).map((v) => <text key={v} x={L - 8} y={Y(v) + 4} textAnchor="end" className="bubble__tick">{v}%</text>)}
        {items.map((o) => {
          const cx = X(o.evidence.pct_of_dataset), cy = Y(o.evidence.switching_or_warning_or_non_return_pct), r = rad(o.prioritisation.score);
          const on = o.opportunity_id === (hover ?? selected);
          return (
            <g key={o.opportunity_id} className={`bubble__dot ${on ? "is-on" : ""}`} onMouseEnter={() => setHover(o.opportunity_id)} onMouseLeave={() => setHover(null)}
               onClick={() => onPick?.(o.opportunity_id)} tabIndex={0} role="button" aria-label={`${o.opportunity_id} ${o.title}`} onKeyDown={(e) => e.key === "Enter" && onPick?.(o.opportunity_id)}>
              <circle cx={cx} cy={cy} r={r} fill={o.priority === "High" ? "var(--violet)" : o.priority === "Medium" ? "var(--blue)" : "var(--slate)"} fillOpacity={on ? 0.9 : 0.6} stroke="#fff" strokeOpacity={on ? 0.95 : 0.3} />
              <text x={cx} y={cy + 4.5} textAnchor="middle" className="bubble__id">{o.opportunity_id}</text>
            </g>
          );
        })}
        <text x={(L + W - R) / 2} y={H - 8} textAnchor="middle" className="bubble__axis">Share of all reviews that mention it →</text>
        <text transform={`translate(13 ${(T + H - B) / 2}) rotate(-90)`} textAnchor="middle" className="bubble__axis">Reviews that warn, switch or leave →</text>
      </svg>
      <div className="bubble__legend"><span><i style={{ background: "var(--violet)" }} />High priority</span><span><i style={{ background: "var(--blue)" }} />Medium</span><span><i style={{ background: "var(--slate)" }} />Low</span><span>Bigger bubble = higher score</span></div>
      <p className="bubble__tip">{active ? <><b>{active.opportunity_id} · {active.title}</b>: {num(active.evidence.reviews)} reviews ({active.evidence.pct_of_dataset}% of all), {active.evidence.switching_or_warning_or_non_return_pct}% warn, switch or leave, score {Math.round(active.prioritisation.score * 100)}</> : "Hover or click a bubble."}</p>
    </div>
  );
}

/** Heat grid: rows × columns, cell shade shows a percentage. */
export function HeatGrid({ rows, cols, cell }: { rows: { key: string; label: string; n: number }[]; cols: { key: string; label: string }[]; cell: (rowKey: string, colKey: string) => number }) {
  const max = Math.max(1, ...rows.flatMap((r) => cols.map((c) => cell(r.key, c.key))));
  return (
    <div className="heat" style={{ gridTemplateColumns: `minmax(150px, 1.4fr) repeat(${cols.length}, minmax(64px, 1fr))` }}>
      <span />
      {cols.map((c) => <span key={c.key} className="heat__col">{c.label}</span>)}
      {rows.map((r) => (
        <div className="heat__rowwrap" key={r.key}>
          <span className="heat__row">{r.label}<small>n={num(r.n)}</small></span>
          {cols.map((c) => {
            const v = cell(r.key, c.key);
            return <span key={c.key} className="heat__cell" style={{ background: `rgba(140, 108, 255, ${0.08 + 0.7 * (v / max)})` }} title={`${r.label} · ${c.label}: ${v}%`}>{Math.round(v)}%</span>;
          })}
        </div>
      ))}
    </div>
  );
}

/** Donut of the four return-behaviour classes. */
export function Donut({ parts, size = 168 }: { parts: { label: string; value: number; color: string }[]; size?: number }) {
  const total = parts.reduce((a, p) => a + p.value, 0), r = 62, c = 2 * Math.PI * r;
  let off = 0;
  return (
    <svg width={size} height={size} viewBox="0 0 160 160" role="img" aria-label={parts.map((p) => `${p.label} ${p.value}`).join(", ")}>
      <circle cx="80" cy="80" r={r} fill="none" stroke="rgba(255,255,255,0.06)" strokeWidth="18" />
      {parts.map((p) => {
        const len = (p.value / total) * c;
        const el = <circle key={p.label} cx="80" cy="80" r={r} fill="none" stroke={p.color} strokeWidth="18" strokeDasharray={`${Math.max(len - 2, 0.5)} ${c}`} strokeDashoffset={-off} transform="rotate(-90 80 80)" />;
        off += len;
        return el;
      })}
      <text x="80" y="78" textAnchor="middle" className="donut__n">{num(total)}</text>
      <text x="80" y="96" textAnchor="middle" className="donut__l">reviews</text>
    </svg>
  );
}

/** Funnel of record counts, widths relative to the first step. */
export function Funnel({ steps }: { steps: { step: string; n: number; note: string }[] }) {
  const top = steps[0].n;
  return (
    <ol className="funnel">
      {steps.map((s, i) => (
        <li key={s.step}>
          <div className="funnel__bar" style={{ width: `${Math.max(14, (100 * s.n) / top)}%` }}><b>{num(s.n)}</b></div>
          <div className="funnel__text"><span>{i + 1}. {s.step}</span><small>{s.note}</small></div>
        </li>
      ))}
    </ol>
  );
}
