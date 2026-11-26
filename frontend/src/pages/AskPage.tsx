import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { AskAnswer, AskBrief, AskResult, Question } from "../api/types";
import { Chip, Highlight, PageHero, QuoteCard, SentimentChip, SourcePill } from "../components/ui";
import { useApi } from "../hooks/useApi";
import { shortDate } from "../utils/format";

const STRENGTH_TONE: Record<string, "pos" | "mix" | "neg"> = { strong: "pos", moderate: "mix", weak: "neg" };
const SHORT: Record<string, string> = { Q1: "After booking", Q2: "Need and timing", Q3: "Alternatives", Q4: "Why rebook", Q5: "Outside the app", Q6: "Returners vs not", Q7: "Segments", Q8: "Unmet needs" };
const TRY = ["Do customers get refunds on time?", "Is the pricing fair?", "What do customers say about customer support?", "Why do people like Urban Company?", "How do customers react when a professional doesn't turn up?", "Do customers trust the professionals who come home?"];

type Mode = { kind: "q"; id: string } | { kind: "free"; q: string };

function Shimmer({ label }: { label: string }) {
  return (
    <div className="ask-card ask-card--wait" role="status">
      <span className="ask-card__label">{label}</span>
      <span className="shim shim--h" /><span className="shim" /><span className="shim shim--s" />
    </div>
  );
}

function Quotes({ items }: { items: Parameters<typeof QuoteCard>[0]["e"][] }) {
  if (!items.length) return null;
  return (
    <section className="ask-evidence">
      <h3 className="ask-evidence__h">What customers actually said</h3>
      <div className="ask-quotes">{items.map((e) => <QuoteCard key={e.review_id + e.quote} compact e={e} />)}</div>
    </section>
  );
}

function PresetAnswer({ id }: { id: string }) {
  const q = useApi<Question>(`/questions/${id}`);
  const brief = useApi<AskBrief>(`/questions/${id}/brief`);
  if (q.loading) return <Shimmer label="Loading the analysed answer" />;
  if (q.error || !q.data) return <div className="ask-card"><p className="ask-card__text">This question could not be loaded: {q.error?.message}</p></div>;
  const d = q.data;
  const sentences = d.summary.split(/(?<=[.!?])\s+/);
  return (
    <>
      <article className="ask-card">
        <span className="ask-card__label">Discovery question {id}</span>
        <h2 className="ask-card__q">{d.question}</h2>
        {brief.loading ? <><span className="shim shim--h" /><span className="shim" /><span className="shim shim--s" /></> : (
          <>
            <p className="ask-card__head">{brief.data?.headline ?? sentences[0]}</p>
            <p className="ask-card__text">{brief.data?.answer ?? sentences.slice(1, 3).join(" ")}</p>
          </>
        )}
        <div className="ask-card__meta">
          <Chip tone={STRENGTH_TONE[d.evidence_strength] ?? "plain"}>{d.evidence_strength} evidence</Chip>
          {brief.data && <Chip tone="violet">AI summary</Chip>}
        </div>
        <details className="ask-more">
          <summary>See the full analysis</summary>
          <p className="ask-card__text">{d.summary}</p>
          {d.gaps.length > 0 && <><h4>Gaps and cautions</h4><ul className="bullets">{d.gaps.map((g) => <li key={g}>{g}</li>)}</ul></>}
        </details>
      </article>
      <Quotes items={(d.evidence_quotes ?? []).slice(0, 3).map((e) => ({ quote: e.quote, source: e.source, source_url: e.source_url, review_date: e.review_date, rating: e.rating, sentiment_label: e.sentiment_label, review_id: e.review_id }))} />
    </>
  );
}

/** Used only when the AI answer is unavailable: real reviews that contain the asker's words. */
function KeywordFallback({ q }: { q: string }) {
  const d = useApi<AskResult>("/ask", { q });
  if (!d.data) return null;
  const r = d.data;
  return (
    <section className="ask-evidence">
      <h3 className="ask-evidence__h">{r.comments.length ? `Reviews that mention “${r.search_words.join(" ")}”` : "No review contains these words"}</h3>
      <div className="ask-quotes">
        {r.comments.map((c) => (
          <figure className="quote quote--compact" key={c.record_id}>
            <blockquote>“<Highlight text={c.excerpt} words={c.matched_words} />”</blockquote>
            <figcaption><SourcePill source={c.source} /><span>{c.record_id}</span><span>{shortDate(c.review_date)}</span><SentimentChip s={c.sentiment_label} /><a href={c.source_url} target="_blank" rel="noopener noreferrer">Open source ↗</a></figcaption>
          </figure>
        ))}
      </div>
    </section>
  );
}

function FreeAnswer({ q, onTry }: { q: string; onTry: (s: string) => void }) {
  const d = useApi<AskAnswer>("/ask/answer", { q });
  if (d.loading) return <><Shimmer label="Writing a short answer" /><KeywordFallback q={q} /></>;   // real matching comments appear at once while the AI writes
  if (d.error) {
    const msg = d.error.code === "llm_not_configured" ? "The AI provider is not configured, so only matching reviews are shown." : d.error.code === "no_searchable_words" ? d.error.message : "The AI answer is unavailable right now. Matching reviews are shown instead.";
    return (
      <>
        <article className="ask-card ask-card--note"><span className="ask-card__label">Your question</span><h2 className="ask-card__q">{q}</h2><p className="ask-card__text">{msg}</p></article>
        {d.error.code !== "no_searchable_words" && <KeywordFallback q={q} />}
      </>
    );
  }
  const a = d.data!;
  if (a.reason === "out_of_scope" || a.reason === "no_match") {
    return (
      <article className="ask-card ask-card--note">
        <span className="ask-card__label">Your question</span>
        <h2 className="ask-card__q">{q}</h2>
        <p className="ask-card__head">{a.reason === "out_of_scope" ? "That one is outside the customer reviews." : "No review talks about this."}</p>
        <p className="ask-card__text">Ask about what customers say: refunds, pricing, support, professionals, cancellations, or a service such as AC repair or salon at home.</p>
        <div className="ask-try">{TRY.slice(0, 3).map((t) => <button type="button" key={t} className="ask-chip" onClick={() => onTry(t)}>{t}</button>)}</div>
      </article>
    );
  }
  return (
    <>
      <article className="ask-card">
        <span className="ask-card__label">Your question</span>
        <h2 className="ask-card__q">{q}</h2>
        {a.headline && <p className="ask-card__head">{a.headline}</p>}
        <p className="ask-card__text">{a.answer}</p>
        <div className="ask-card__meta">
          <Chip tone={STRENGTH_TONE[a.evidence_strength] ?? "plain"}>{a.evidence_strength} evidence</Chip>
          <Chip tone="violet">AI answer</Chip>
          {a.reviews_matching ? <span className="ask-card__basis">Read the {a.reviews_considered} best of {a.reviews_matching.toLocaleString("en-IN")} related reviews</span> : null}
        </div>
      </article>
      <Quotes items={a.citations.map((c) => ({ quote: c.quote, source: c.source, source_url: c.source_url, review_date: c.review_date, rating: null, sentiment_label: c.sentiment_label, review_id: c.review_id }))} />
    </>
  );
}

export default function AskPage() {
  const questions = useApi<Question[]>("/questions");
  const [params, setParams] = useSearchParams();
  const initial = params.get("q") ?? "";
  const [text, setText] = useState("");
  const [mode, setMode] = useState<Mode>(/^Q\d$/.test(initial) ? { kind: "q", id: initial } : initial ? { kind: "free", q: initial } : { kind: "q", id: "Q4" });
  const answerRef = useRef<HTMLDivElement>(null);
  useEffect(() => { if (/^Q\d$/.test(initial)) setMode({ kind: "q", id: initial }); }, [initial]);

  const ask = (q: string) => {
    const t = q.trim();
    if (t.length < 3) return;
    setText(t); setMode({ kind: "free", q: t }); setParams({});
    answerRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  };
  const pick = (id: string) => { setMode({ kind: "q", id }); setParams({}); };

  return (
    <>
      <PageHero eyebrow="Ask questions" title={<>Find the <span className="gradient-text">evidence</span> in customer feedback</>}
        lede="Ask in your own words or pick a discovery question. You get a short answer and the real comments behind it." />
      <div className="ask2">
        <form className="ask-box" onSubmit={(e) => { e.preventDefault(); ask(text); }}>
          <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask anything about Urban Company customers, e.g. Do customers get refunds on time?" aria-label="Your question" maxLength={200} />
          <button className="btn btn--primary" type="submit" disabled={text.trim().length < 3}>Ask</button>
        </form>
        <div className="ask-try" aria-label="Example questions">
          <span className="ask-try__label">Try</span>
          {TRY.slice(0, 4).map((t) => <button type="button" key={t} className="ask-chip" onClick={() => ask(t)}>{t}</button>)}
        </div>

        <section className="ask-pick" aria-label="Discovery questions">
          <h3 className="ask-pick__h">The eight discovery questions</h3>
          <div className="ask-pick__grid">
            {(questions.data ?? Object.keys(SHORT).map((id) => ({ question_id: id, question: "" }))).map((q) => (
              <button type="button" key={q.question_id} title={q.question} className={`ask-q ${mode.kind === "q" && mode.id === q.question_id ? "is-on" : ""}`} onClick={() => pick(q.question_id)}>
                <span className="ask-q__id">{q.question_id}</span><span className="ask-q__t">{SHORT[q.question_id] ?? q.question}</span>
              </button>
            ))}
          </div>
        </section>

        <div className="ask-out" ref={answerRef} aria-live="polite">
          {mode.kind === "q" ? <PresetAnswer id={mode.id} /> : <FreeAnswer key={mode.q} q={mode.q} onTry={ask} />}
        </div>
      </div>
    </>
  );
}
