import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { Experience, UploadAnalysis, UploadAnalysisReview, UploadEvidence } from "../api/types";
import { SentimentBar, SentimentLegend } from "../components/charts";
import { Card, Chip, Kpi, PageHero, QuoteCard, Section, SentimentChip } from "../components/ui";
import { isTemp, loadTemp } from "../utils/tempSession";
import { num, pct } from "../utils/format";

type Ev = Record<string, UploadEvidence>;
const asQuote = (e: UploadEvidence) => ({ ...e, review_id: e.review_id, source: e.source ?? "Uploaded file", source_url: e.source_url ?? "", sentiment_label: (e.sentiment || "Unclear") as never });

function Quotes({ ids, ev }: { ids: string[]; ev: Ev }) {
  return <div className="quotes">{ids.map((i) => ev[i]).filter(Boolean).map((e) => <UploadQuote key={e.evidence_id} e={e} />)}</div>;
}

/** QuoteCard needs a source URL; uploads may not have one, so fall back to a plain caption. */
function UploadQuote({ e }: { e: UploadEvidence }) {
  if (e.source_url) return <QuoteCard e={asQuote(e)} compact />;
  return (
    <figure className="quote quote--compact"><blockquote>“{e.quote}”</blockquote>
      <figcaption><span>{e.review_id}</span>{e.source && <span>{e.source}</span>}{e.rating && <span>★ {e.rating}</span>}<SentimentChip s={(e.sentiment || "Unclear") as never} /><span>no source URL in the file</span></figcaption></figure>
  );
}

function ExperienceCard({ title, x, ev, tone }: { title: string; x: Experience; ev: Ev; tone: "violet" | "amber" }) {
  return (
    <Card title={title} accent={tone}>
      <p className="gcard__sub"><b>{num(x.review_count)}</b> reviews ({pct(x.pct_of_analysed)} of those analysed)</p>
      {x.summary && <p className="ans__text">{x.summary}</p>}
      {x.top_themes.length > 0 && <div className="chips">{x.top_themes.map((t) => <Chip key={t.theme}>{t.theme} · {t.review_count}</Chip>)}</div>}
      <Quotes ids={x.evidence_ids} ev={ev} />
    </Card>
  );
}

function ReviewTable({ reviews, themes }: { reviews: UploadAnalysisReview[]; themes: string[] }) {
  const [theme, setTheme] = useState(""), [sent, setSent] = useState(""), [page, setPage] = useState(1);
  const list = reviews.filter((r) => (!theme || r.theme_names.includes(theme)) && (!sent || r.sentiment.toLowerCase() === sent.toLowerCase()));
  const total = list.length, pages = Math.max(1, Math.ceil(total / 15));
  const rows = list.slice((page - 1) * 15, page * 15);
  return (
    <>
      <div className="lab__pick">
        <select className="sel" value={theme} onChange={(e) => { setTheme(e.target.value); setPage(1); }} aria-label="Filter by theme"><option value="">All themes</option>{themes.map((t) => <option key={t}>{t}</option>)}</select>
        <select className="sel" value={sent} onChange={(e) => { setSent(e.target.value); setPage(1); }} aria-label="Filter by sentiment"><option value="">All sentiments</option>{["Positive", "Negative", "Mixed", "Neutral", "Unclear"].map((t) => <option key={t}>{t}</option>)}</select>
      </div>
      <>
        {(() => (
          <>
            <div className="tablewrap"><table className="tbl"><thead><tr><th>Review ID</th><th>Sentiment</th><th>Themes</th><th>Evidence excerpt</th><th>Source</th></tr></thead>
              <tbody>{rows.map((r) => (
                <tr key={r.review_id}><td>{r.review_id}</td><td><SentimentChip s={r.sentiment as never} /></td><td>{r.theme_names.join(", ") || "—"}</td><td>{r.evidence_quote}</td>
                  <td>{r.source_url ? <a href={r.source_url} target="_blank" rel="noopener noreferrer">{r.source ?? "open"} ↗</a> : r.source ?? "—"}</td></tr>))}</tbody></table></div>
            <div className="lab__nav"><button className="btn" disabled={page <= 1} onClick={() => setPage(page - 1)}>← Previous</button><span className="gcard__sub">Page {page} of {pages} · {num(total)} reviews</span><button className="btn" disabled={page >= pages} onClick={() => setPage(page + 1)}>Next →</button></div>
          </>
        ))()}
      </>
    </>
  );
}

function Results({ a, reviews }: { a: UploadAnalysis; reviews: UploadAnalysisReview[] }) {
  const ev: Ev = Object.fromEntries(a.evidence.map((e) => [e.evidence_id, e]));
  const s = a.sentiment, n = a.dataset.reviews_analysed;
  const row = { positive: s.Positive?.n ?? 0, neutral: s.Neutral?.n ?? 0, negative: s.Negative?.n ?? 0, mixed: s.Mixed?.n ?? 0, uncertain: s.Unclear?.n ?? 0, n };
  const u = a.usage;
  return (
    <>
      <div className="kpis">
        <Kpi tone="violet" label="Reviews analysed" value={num(n)} sub={`of ${num(a.dataset.rows_in_upload)} rows in the file`} />
        <Kpi label="Themes found" value={a.themes.length} sub={`${a.insights.length} insights · ${a.opportunities.length} opportunities`} />
        <Kpi tone="amber" label="Negative / positive" value={`${pct(s.Negative?.pct ?? 0, 0)} / ${pct(s.Positive?.pct ?? 0, 0)}`} sub={`${s.Mixed?.n ?? 0} mixed · ${s.Neutral?.n ?? 0} neutral`} />
        <Kpi tone="blue" label="AI requests" value={u.requests} sub={`${u.failed_requests} failed · ${u.processing_seconds}s`} />
        <Kpi label="Neurons used" value={u.neurons.toFixed(1)} sub={`${num(u.input_tokens)} in · ${num(u.output_tokens)} out tokens`} />
      </div>
      {(a.dataset.rows_not_analysed_due_to_limit > 0 || a.dataset.extraction_failed > 0) && (
        <p className="callout callout--amber">{a.dataset.rows_not_analysed_due_to_limit > 0 && <>{num(a.dataset.rows_not_analysed_due_to_limit)} rows beyond the {a.dataset.analysis_row_limit}-review limit were <b>not analysed</b>. </>}
          {a.dataset.extraction_failed > 0 && <>{a.dataset.extraction_failed} reviews could not be read by the model and are excluded from the counts.</>}</p>
      )}

      <Section id="mood" eyebrow="1 · How people feel" title="Positive and negative experiences" lede="Sentiment was read by the model for each review; the totals are counted in code.">
        <Card><SentimentBar row={row} height={18} /><SentimentLegend items={["Positive", "Neutral", "Mixed", "Negative"]} /></Card>
        <div className="grid2"><ExperienceCard title="What customers valued" x={a.positive_experiences} ev={ev} tone="violet" /><ExperienceCard title="What went wrong" x={a.negative_experiences} ev={ev} tone="amber" /></div>
      </Section>

      <Section id="themes" eyebrow="2 · Themes and how often" title="What keeps coming up" lede="The model grouped recurring topics into at most five themes. A review can belong to more than one theme, so percentages can add up to more than 100%.">
        <div className="themes">{a.themes.map((t) => (
          <article className="theme" key={t.theme_id}>
            <header><span className="theme__id">{t.theme_id}</span><div><h3>{t.name}</h3><p className="gcard__sub">{t.description}</p></div><div className="theme__count"><b>{num(t.review_count)}</b><small>{pct(t.pct_of_analysed)} of reviews</small></div></header>
            <SentimentBar row={{ positive: t.sentiment.Positive ?? 0, neutral: t.sentiment.Neutral ?? 0, negative: t.sentiment.Negative ?? 0, mixed: t.sentiment.Mixed ?? 0, uncertain: t.sentiment.Unclear ?? 0, n: t.review_count }} />
            <div className="chips">{t.labels.slice(0, 8).map((l) => <Chip key={l}>{l}</Chip>)}</div>
            <Quotes ids={t.evidence_ids} ev={ev} />
          </article>))}</div>
      </Section>

      <Section id="insights" eyebrow="3 · Insights" title="What the feedback tells us" lede="Written by the model from the computed counts and verbatim quotes. Every insight cites reviews you can open.">
        <div className="themes">{a.insights.map((i) => <article className="theme" key={i.insight_id}><h3>{i.title}</h3><p className="ans__text">{i.insight}</p><Quotes ids={i.evidence_ids} ev={ev} /></article>)}</div>
        {!a.insights.length && <p className="gcard__sub">No insight passed the evidence checks.</p>}
      </Section>

      <Section id="opportunities" eyebrow="4 · Product opportunities" title="Where to act" lede="Opportunities are hypotheses generated from the evidence; the impact score is the model's judgement, not a measurement.">
        <div className="themes">{a.opportunities.map((o) => (
          <article className="theme" key={o.opportunity_id}>
            <header><span className="theme__id">{o.opportunity_id}</span><div><h3>{o.name}</h3><div className="chips">{o.related_themes.map((t) => <Chip key={t} tone="blue">{t}</Chip>)}</div></div>
              <div className="theme__count"><b>{o.impact_score_1_to_5_analyst_judgement ?? "–"}/5</b><small>impact (AI judgement)</small></div></header>
            <p className="theme__read"><b>What customers said.</b> {o.customer_problem}</p><p className="theme__read"><b>Why it matters.</b> {o.why_it_matters}</p>
            <div className="takeaway"><h4>Hypotheses <Chip tone="amber">not findings</Chip></h4><p><b>What to try.</b> {o.suggested_improvement_hypothesis}</p><p><b>Link to repeat booking.</b> {o.repeat_booking_link_hypothesis}</p></div>
            <Quotes ids={o.evidence_ids} ev={ev} />
          </article>))}</div>
        {!a.opportunities.length && <p className="gcard__sub">No opportunity passed the evidence checks.</p>}
      </Section>

      <Section id="usage" eyebrow="5 · How this was produced" title="AI usage and quality checks" lede={a.method}>
        <div className="grid2">
          <Card title="Cloudflare Workers AI usage" sub={`Model ${a.model}. Saved with the results, so viewing this page costs nothing.`}>
            <table className="cmp"><tbody>
              <tr><td>Requests (failed)</td><td>{u.requests} ({u.failed_requests})</td></tr><tr><td>Input tokens</td><td>{num(u.input_tokens)}</td></tr><tr><td>Output tokens</td><td>{num(u.output_tokens)}</td></tr>
              <tr><td>Neurons consumed</td><td>{u.neurons.toFixed(2)}</td></tr><tr><td>Processing time</td><td>{u.processing_seconds}s</td></tr><tr><td>Served from cache</td><td>{u.cache_hits ?? 0}</td></tr></tbody></table>
            <div className="tablewrap"><table className="tbl"><thead><tr><th>Step</th><th>Requests</th><th>Neurons</th></tr></thead><tbody>{Object.entries(u.by_purpose).map(([k, v]) => <tr key={k}><td>{k.split("_").pop()}</td><td>{v.requests}</td><td>{v.neurons.toFixed(1)}</td></tr>)}</tbody></table></div>
          </Card>
          <Card title="Evidence checks">
            <ul className="bullets">
              <li>{num(a.quality.reviews_with_model_quote)} reviews have a quote the model copied exactly; {num(a.quality.reviews_with_review_start_excerpt)} use the start of the review instead because the model’s quote was not verbatim.</li>
              <li>{a.quality.citations_dropped_unverifiable} cited quotes were dropped because they could not be found in the review.</li>
              <li>{a.quality.items_dropped_for_digits} generated items were dropped for stating numbers; {a.quality.items_dropped_without_evidence} for having no verifiable evidence.</li>
              <li>Original review IDs and source URLs from your file are kept on every quote.</li>
              <li>These results are AI-generated, not human-validated, and are kept separate from the approved Urban Company analysis.</li>
            </ul>
          </Card>
        </div>
      </Section>

      <Section id="reviews" eyebrow="6 · Every review" title="Per-review results">
        <ReviewTable reviews={reviews} themes={a.themes.map((t) => t.name)} />
      </Section>
    </>
  );
}

export default function ResultsPage() {
  const { uploadId = "" } = useParams();
  const t = isTemp(uploadId) ? loadTemp(uploadId) : null;
  return (
    <>
      <PageHero eyebrow="Your uploaded file" title={<>AI insights from <span className="gradient-text">{t?.analysis.source_file ?? "your reviews"}</span></>}
        lede="Generated by an LLM from the file you uploaded. It is held only in this browser tab: nothing is stored on the server, and it disappears when you close the tab.">
        <div className="chips"><Chip tone="violet">AI-generated</Chip><Chip>Temporary</Chip><Link to="/overview/feedback" className="btn">← Back to the dataset</Link></div>
      </PageHero>
      {t ? <Results a={t.analysis} reviews={t.reviews} /> : (
        <Card title="This temporary result is no longer here" accent="amber">
          <p className="ans__text">Results of your own file are kept only in the browser tab where you ran them, so they are gone once the tab is closed or reloaded in a new window. Upload the file again to see them.</p>
          <Link to="/overview/feedback" className="btn btn--primary">Go to the dataset page</Link>
        </Card>
      )}
    </>
  );
}
