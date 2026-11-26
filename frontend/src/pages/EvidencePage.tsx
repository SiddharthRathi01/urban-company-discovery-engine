import { useState } from "react";
import { Link } from "react-router-dom";
import type { Behaviour, Evidence, ReviewRow, Theme, Trust } from "../api/types";
import { Funnel, SentimentBar } from "../components/charts";
import { Async, Card, Chip, Kpi, PageHero, QuoteCard, Section, SentimentChip, SourcePill } from "../components/ui";
import { useApi } from "../hooks/useApi";
import { shortDate, num, pct } from "../utils/format";


/** "Follow one comment": pick a quoted review and see how it was read and where it ends up. */
function FollowOne() {
  const ev = useApi<Evidence[]>("/evidence", { page_size: 200 });
  const themes = useApi<Theme[]>("/themes");
  const [sel, setSel] = useState<string | null>(null);
  const items = ev.data ?? [];
  const chosen = sel ?? items[0]?.evidence_id ?? null;
  const e = items.find((x) => x.evidence_id === chosen) ?? null;
  const detail = useApi<ReviewRow>(e ? `/reviews/${e.review_id}` : null);
  const names = Object.fromEntries((themes.data ?? []).flatMap((t) => t.subthemes.map((s) => [s.subtheme_id.split(".")[1], s.name])));
  const pick = (delta?: number) => {
    if (!items.length) return;
    const i = delta === undefined ? Math.floor(Math.random() * items.length) : (items.findIndex((x) => x.evidence_id === chosen) + delta + items.length) % items.length;
    setSel(items[i].evidence_id);
  };
  return (
    <Section id="lab" eyebrow="Follow one comment" title="How one comment becomes an insight" lede="Pick any quoted review and see how it was read, and which problem area and opportunity it feeds.">
      <Async state={ev}>
        {() => (
          <>
            <div className="lab__pick">
              <select className="sel" value={chosen ?? ""} onChange={(x) => setSel(x.target.value)} aria-label="Choose a comment">
                {items.map((x) => <option key={x.evidence_id} value={x.evidence_id}>{x.review_id} · {x.quote.slice(0, 80)}{x.quote.length > 80 ? "…" : ""}</option>)}
              </select>
              <button type="button" className="btn" onClick={() => pick()}>Show another comment</button>
            </div>
            {e && (
              <Async state={detail}>
                {(r) => (
                  <ol className="lab">
                    <li><h4>The comment</h4>
                      <div className="rv__meta"><SourcePill source={r.source} /><span>{r.record_id}</span><span>{shortDate(r.review_date)}</span>{r.rating && <span>★ {r.rating}</span>}</div>
                      {r.review_title && <p><b>{r.review_title}</b></p>}
                      <p className="lab__text">{r.review_text}</p>
                      <QuoteCard e={e} compact />
                    </li>
                    <li><h4>Is it a real customer comment?</h4>
                      <p>Yes: a public review or post on <b>{r.source}</b> with its own page. <a href={r.source_url} target="_blank" rel="noopener noreferrer">Open the original ↗</a></p>
                    </li>
                    <li><h4>How it was read</h4>
                      <div className="chips"><SentimentChip s={r.sentiment_label} /><Chip tone="violet">Return evidence: {r.return_class}</Chip>{r.issues.map((i) => <Chip key={i}>{names[i] ?? i}</Chip>)}{!r.issues.length && <Chip>No problem phrase matched</Chip>}</div>
                      <p className="gcard__sub">Mood comes from the words and rating; problem types come from phrase rules, then a read of the matched text.</p>
                    </li>
                    <li><h4>Which problem area it belongs to</h4>
                      <div className="chips">{r.themes.map((t) => <Chip key={t} tone="blue">{t} · {(themes.data ?? []).find((x) => x.theme_id === t)?.name ?? t}</Chip>)}{!r.themes.length && <Chip>Not in a theme</Chip>}</div>
                    </li>
                    <li><h4>What it tells us</h4>
                      {r.opportunities?.length ? <ul className="bullets">{r.opportunities.map((o) => <li key={o.opportunity_id}><b>{o.opportunity_id} · {o.title}</b> ({o.priority} priority, rank {o.priority_rank})</li>)}</ul> : <p className="gcard__sub">This review is shown as evidence for a theme but does not feed a ranked opportunity.</p>}
                      {r.unmet_needs.length > 0 && <p className="gcard__sub">Unmet needs flagged: {r.unmet_needs.join(", ")}.</p>}
                    </li>
                  </ol>
                )}
              </Async>
            )}
            <div className="lab__nav"><button type="button" className="btn" onClick={() => pick(-1)}>← Previous</button><button type="button" className="btn" onClick={() => pick(1)}>Next →</button></div>
          </>
        )}
      </Async>
    </Section>
  );
}

/** Stacked bar showing how each review's Return / Non-Return label was decided. */
function Ladder({ b }: { b: Behaviour }) {
  const s = b.summary;
  const parts = [{ k: "Stated", n: s.by_basis.Stated.n, c: "var(--pos)", d: "said in the first person" }, { k: "Signalled", n: s.by_basis.Signalled.n, c: "var(--blue)", d: "advises against the app, switching, distrust, or recommends" },
                 { k: "Inferred", n: s.by_basis.Inferred.n, c: "var(--violet)", d: "from sentiment and star rating" }, { k: "Insufficient", n: s.insufficient, c: "var(--slate)", d: "no clear signal" }];
  const total = parts.reduce((a, x) => a + x.n, 0);
  return (
    <div className="ladder">
      <div className="sbar" style={{ height: 16 }} role="img" aria-label={parts.map((x) => `${x.n} ${x.k}`).join(", ")}>{parts.map((x) => <span key={x.k} style={{ flex: x.n, background: x.c }} title={`${x.k}: ${num(x.n)}`} />)}</div>
      <ul className="ladder__key">{parts.map((x) => <li key={x.k}><i style={{ background: x.c }} /><b>{x.k}</b> · {num(x.n)} ({pct((100 * x.n) / total)})<small>{x.d}</small></li>)}</ul>
    </div>
  );
}

export default function EvidencePage() {
  const t = useApi<Trust>("/trust");
  const beh = useApi<Behaviour>("/behaviour");
  return (
    <>
      <PageHero eyebrow="AI Evidence Log" title={<>How the results <span className="gradient-text">were checked</span></>}
        lede="Every theme, score and quote links back to a review you can read. This page shows where the data came from, what was removed, how bias was handled and how the results were validated." />
      <div className="evlog">
        <div className="evlog__icon" aria-hidden="true">📄</div>
        <div className="evlog__text">
          <h3>The full AI Evidence Log</h3>
          <p>Sources and cleaning, how the engine works, the golden-set validation, safeguards, limitations and the files behind it, in one PDF.</p>
        </div>
        <div className="evlog__actions">
          <a className="btn btn--primary" href="/downloads/evidence-log.pdf" target="_blank" rel="noopener noreferrer">Read the AI Evidence Log ↗</a>
          <a className="btn" href="/downloads/evidence-log.pdf?download=true" download>⬇ Download PDF</a>
        </div>
      </div>
      <Async state={t}>
        {(d) => (
          <>
            <div className="kpis kpis--4">{d.tiles.map((x, i) => <Kpi key={x.label} tone={(["violet", undefined, "amber", "blue"] as const)[i]} label={x.label} value={x.value} />)}</div>

            <Section id="sources" eyebrow="1 · Where the data came from" title="Sources and what was kept" lede="Only public sources, and only reviews that can be traced to their own page.">
              <div className="grid2">
                <Card title="From collected to analysed" sub="Every removal is logged in the master workbook (QC Log and Excluded Records sheets)."><Funnel steps={d.funnel} /></Card>
                <Card title="Sources analysed">
                  <div className="srcs">{d.sources.map((s) => (
                    <div key={s.source} className="srcs__row">
                      <div><SourcePill source={s.source} /> <Chip>{s.kind}</Chip><b className="srcs__n">{num(s.reviews)}</b></div>
                      <SentimentBar row={{ positive: s.sentiment_pct.Positive ?? 0, neutral: s.sentiment_pct.Neutral ?? 0, negative: s.sentiment_pct.Negative ?? 0, mixed: s.sentiment_pct.Mixed ?? 0, uncertain: 0, n: 100 }} height={8} />
                      <small>{s.what_it_adds} {s.how}</small>
                    </div>))}</div>
                </Card>
              </div>
            </Section>

            <Section id="bias" eyebrow="2 · The two biases" title="How the engine accounts for what public posts hide" lede="Public posts over-represent bad experiences, and customers who simply never came back leave no trace. Here is what was done about each, and what could not be done.">
              <div className="grid2">
                {(["negative_voice", "silent_churn"] as const).map((k) => {
                  const b = d.bias[k];
                  return (
                    <Card key={k} title={b.title} accent={k === "negative_voice" ? "violet" : "amber"}>
                      <h4>What the data shows</h4><ul className="bullets">{b.facts.map((x) => <li key={x}>{x}</li>)}</ul>
                      {k === "silent_churn" && <Async state={beh}>{(bh) => <><h4>How each review was placed</h4><Ladder b={bh} /></>}</Async>}
                      <h4>What we did</h4><ul className="bullets">{b.what_we_did.map((x) => <li key={x}>{x}</li>)}</ul>
                      {b.gap && <p className="callout callout--amber"><b>What cannot be seen.</b> {b.gap}</p>}
                      {b.equal_weight && (
                        <div className="eqw"><h4>Theme size: pooled vs. sources weighted equally</h4>
                          {Object.keys(b.equal_weight.pooled).map((th) => (
                            <div key={th} className="eqw__row"><span>{th}</span><div className="hbar"><i style={{ width: `${b.equal_weight!.pooled[th]}%`, background: "var(--violet)" }} /><span>{pct(b.equal_weight!.pooled[th], 0)}</span></div><div className="hbar"><i style={{ width: `${b.equal_weight!.equal_weight_across_4_sources[th]}%`, background: "var(--amber)" }} /><span>{pct(b.equal_weight!.equal_weight_across_4_sources[th], 0)}</span></div></div>
                          ))}
                          <div className="legend"><span><i style={{ background: "var(--violet)" }} />Pooled</span><span><i style={{ background: "var(--amber)" }} />Equal weight per source</span></div>
                        </div>)}
                    </Card>
                  );
                })}
              </div>
            </Section>

            <Section id="validation" eyebrow="3 · What was checked" title="Validation we ran" lede={<>These are real checks with real numbers: spot-checks and traceability checks. The comparison with hand-made labels is on the <Link to="/overview/golden">Golden data set</Link> page.</>}>
              <div className="kpis kpis--4">
                <Kpi tone="violet" label="Quotes verified" value={`${d.validation.quotes.verified}/${d.validation.quotes.total}`} sub={d.validation.quotes.note} />
                <Kpi label="Sentiment spot-check" value={`${d.validation.sentiment.agreement_pct}%`} sub={`${d.validation.sentiment.agreed} of ${d.validation.sentiment.sample} sampled labels agreed`} />
                <Kpi tone="amber" label="Source URLs" value={num(d.validation.urls.individually_verified)} sub="reviews opened and matched to their page" />
                <Kpi tone="blue" label="Automated tests" value={d.validation.tests.automated_tests} sub={d.validation.tests.covers} />
              </div>
              <div>
                <Card title="Problem-rule precision" sub={d.validation.rule_precision_note}>
                  <div className="prec">{d.validation.rule_precision.map((p) => <div key={p.code} className="prec__row"><span>{p.issue}</span><div className="hbar"><i style={{ width: `${p.precision_pct}%`, background: p.precision_pct >= 85 ? "var(--pos)" : "var(--amber)" }} /><span>{p.precision_pct}%</span></div></div>)}</div>
                </Card>
              </div>
            </Section>


            <FollowOne />

          </>
        )}
      </Async>
    </>
  );
}
