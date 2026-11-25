import { useCallback, useEffect, useState } from "react";
import { ApiError, get, type Params } from "../api/client";
import type { ReviewRow, SentimentName } from "../api/types";
import { num, shortDate } from "../utils/format";
import { Chip, SentimentChip, SourcePill } from "./ui";

const SENTS: (SentimentName | "All")[] = ["All", "Negative", "Mixed", "Neutral", "Positive"];
const SOURCES = ["All", "Google Play Store", "Reddit", "PissedConsumer", "ConsumerComplaints.in"];

export interface DrawerTarget { title: string; subtitle?: string; base: Params; initialSentiment?: string }

/** Full-height panel listing the real reviews behind a number, with filters and links to the original source. */
export default function CommentsDrawer({ target, onClose }: { target: DrawerTarget | null; onClose: () => void }) {
  const [sent, setSent] = useState<string>("All");
  const [src, setSrc] = useState<string>("All");
  const [rows, setRows] = useState<ReviewRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const key = target ? JSON.stringify([target.base, target.initialSentiment]) : "";
  useEffect(() => { setSent(target?.initialSentiment ?? "All"); setSrc("All"); }, [key]); // eslint-disable-line react-hooks/exhaustive-deps

  const load = useCallback(async (p: number, replace: boolean) => {
    if (!target) return;
    setLoading(true); setError(null);
    try {
      const r = await get<ReviewRow[]>("/reviews", { ...target.base, sentiment: sent === "All" ? undefined : sent, source: src === "All" ? undefined : src, include_text: true, page: p, page_size: 15 });
      setRows((old) => (replace ? r.data : [...old, ...r.data]));
      setTotal(r.meta.total ?? 0);
      setPage(p);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
      if (replace) { setRows([]); setTotal(0); }
    } finally { setLoading(false); }
  }, [target, sent, src]);

  useEffect(() => { if (target) load(1, true); }, [load, target]);
  useEffect(() => {
    if (!target) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.removeEventListener("keydown", onKey); document.body.style.overflow = prev; };
  }, [target, onClose]);

  if (!target) return null;
  return (
    <div className="drawer" role="dialog" aria-modal="true" aria-label={target.title} onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="drawer__panel">
        <header className="drawer__head">
          <div>
            <p className="sec__eyebrow">Comments behind this</p>
            <h2>{target.title}</h2>
            {target.subtitle && <p className="gcard__sub">{target.subtitle}</p>}
          </div>
          <button type="button" className="drawer__close" onClick={onClose} aria-label="Close">×</button>
        </header>
        <div className="drawer__filters">
          <div className="pills" aria-label="Filter by mood">{SENTS.map((s) => <button key={s} type="button" className={`pill ${sent === s ? "is-on" : ""}`} onClick={() => setSent(s)}>{s}</button>)}</div>
          <div className="pills" aria-label="Filter by source">{SOURCES.map((s) => <button key={s} type="button" className={`pill ${src === s ? "is-on" : ""}`} onClick={() => setSrc(s)}>{s === "All" ? "All sources" : s}</button>)}</div>
          <p className="drawer__count">{loading && !rows.length ? "Loading…" : `Showing ${num(rows.length)} of ${num(total)} comments`}</p>
        </div>
        <div className="drawer__list">
          {error && <div className="state state--error">{error}</div>}
          {rows.map((r) => (
            <article className="rv" key={r.record_id}>
              <div className="rv__meta">
                <SourcePill source={r.source} /><span>{r.record_id}</span><span>{shortDate(r.review_date)}</span>
                {r.rating && <span>★ {r.rating}</span>}<SentimentChip s={r.sentiment_label} />
                {r.service_category && <Chip>{r.service_category}</Chip>}{r.city && <Chip>{r.city}</Chip>}
              </div>
              {r.review_title && <h4>{r.review_title}</h4>}
              <p>{r.review_text}</p>
              <a href={r.source_url} target="_blank" rel="noopener noreferrer">Open the original on {r.source} ↗</a>
            </article>
          ))}
          {!loading && !rows.length && !error && <p className="gcard__sub">No comments match these filters.</p>}
          {rows.length < total && <button type="button" className="btn" disabled={loading} onClick={() => load(page + 1, false)}>{loading ? "Loading…" : "Show more comments"}</button>}
        </div>
      </div>
    </div>
  );
}
