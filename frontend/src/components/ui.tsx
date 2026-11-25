import type { ReactNode } from "react";
import type { ApiError } from "../api/client";
import type { ApiState } from "../hooks/useApi";
import type { Evidence } from "../api/types";
import { SOURCE_SHORT, shortDate } from "../utils/format";

export function Card({ title, sub, children, className = "", accent }: { title?: ReactNode; sub?: ReactNode; children: ReactNode; className?: string; accent?: "violet" | "amber" | "blue" }) {
  return (
    <div className={`gcard ${accent ? `gcard--${accent}` : ""} ${className}`}>
      {title && <h3 className="gcard__title">{title}</h3>}
      {sub && <p className="gcard__sub">{sub}</p>}
      {children}
    </div>
  );
}

export function Section({ id, eyebrow, title, lede, children }: { id?: string; eyebrow?: string; title: string; lede?: ReactNode; children: ReactNode }) {
  return (
    <section className="sec" id={id}>
      <header className="sec__head">
        {eyebrow && <p className="sec__eyebrow">{eyebrow}</p>}
        <h2>{title}</h2>
        {lede && <p className="sec__lede">{lede}</p>}
      </header>
      {children}
    </section>
  );
}

export function PageHero({ eyebrow, title, lede, children }: { eyebrow: string; title: ReactNode; lede: ReactNode; children?: ReactNode }) {
  return (
    <header className="phero">
      <p className="sec__eyebrow">{eyebrow}</p>
      <h1>{title}</h1>
      <p className="phero__lede">{lede}</p>
      {children}
    </header>
  );
}

export function Kpi({ label, value, sub, tone }: { label: string; value: ReactNode; sub?: ReactNode; tone?: "violet" | "amber" | "blue" }) {
  return (
    <div className={`kpi ${tone ? `kpi--${tone}` : ""}`}>
      <span className="kpi__label">{label}</span>
      <span className="kpi__value">{value}</span>
      {sub && <span className="kpi__sub">{sub}</span>}
    </div>
  );
}

export function Chip({ children, tone = "plain" }: { children: ReactNode; tone?: "plain" | "pos" | "neg" | "mix" | "violet" | "amber" | "blue" }) {
  return <span className={`chip chip--${tone}`}>{children}</span>;
}

export function Loading({ label = "Loading from the backend…" }: { label?: string }) {
  return (
    <div className="state state--loading" role="status">
      <span className="spinner" aria-hidden="true" />
      {label}
    </div>
  );
}

export function ErrorBox({ error }: { error: ApiError }) {
  return (
    <div className="state state--error" role="alert">
      <strong>Could not load this data.</strong>
      <span>{error.message}</span>
      {error.status === 0 && <span>Start the whole product with <code>start-app.cmd</code>, or run the API on port 8000 next to <code>npm run dev</code>.</span>}
    </div>
  );
}

/** Renders loading / error states and calls children once data has arrived. */
export function Async<T>({ state, children }: { state: ApiState<T>; children: (data: T, meta: ApiState<T>["meta"]) => ReactNode }) {
  if (state.error) return <ErrorBox error={state.error} />;
  if (state.loading || !state.data) return <Loading />;
  return <>{children(state.data, state.meta)}</>;
}

export function SourcePill({ source }: { source: string }) {
  return <span className={`src src--${source.replace(/[^A-Za-z]/g, "").toLowerCase()}`}>{SOURCE_SHORT[source] ?? source}</span>;
}

const SENT_TONE = { Positive: "pos", Negative: "neg", Mixed: "mix", Neutral: "plain", Uncertain: "plain", Unclear: "plain" } as const;

export function SentimentChip({ s }: { s: keyof typeof SENT_TONE }) {
  return <Chip tone={SENT_TONE[s]}>{s}</Chip>;
}

/** A verified quote with its source, date, rating and a link to the original. */
export function QuoteCard({ e, compact = false }: { e: Pick<Evidence, "quote" | "source" | "source_url" | "review_date" | "rating" | "sentiment_label" | "review_id">; compact?: boolean }) {
  return (
    <figure className={`quote ${compact ? "quote--compact" : ""}`}>
      <blockquote>“{e.quote}”</blockquote>
      <figcaption>
        <SourcePill source={e.source} />
        <span>{e.review_id}</span>
        <span>{shortDate(e.review_date)}</span>
        {e.rating && <span>{"★".repeat(Math.round(Number(e.rating)))} {e.rating}</span>}
        <SentimentChip s={e.sentiment_label} />
        <a href={e.source_url} target="_blank" rel="noopener noreferrer">Open source ↗</a>
      </figcaption>
    </figure>
  );
}

export function Highlight({ text, words }: { text: string; words: string[] }) {
  if (!words.length) return <>{text}</>;
  const rx = new RegExp(`(${words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "gi");
  return (
    <>
      {text.split(rx).map((part, i) => (i % 2 ? <mark key={i}>{part}</mark> : <span key={i}>{part}</span>))}
    </>
  );
}
