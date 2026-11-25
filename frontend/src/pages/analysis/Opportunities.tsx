import { useState } from "react";
import type { Opportunity } from "../../api/types";
import { BubbleChart, ScoreStack, SentimentBar } from "../../components/charts";
import type { DrawerTarget } from "../../components/CommentsDrawer";
import { Async, Card, Chip, QuoteCard, Section } from "../../components/ui";
import { useApi } from "../../hooks/useApi";
import { THEME_SHORT, num, pct } from "../../utils/format";

const score = (o: Opportunity) => Math.round(o.prioritisation.score * 100);
const PRIORITY_TONE = { High: "violet", Medium: "blue", Low: "plain" } as const;

function sentRow(o: Opportunity) {
  const s = o.evidence.sentiment;
  return { positive: s.Positive.n, neutral: s.Neutral.n, negative: s.Negative.n, mixed: s.Mixed.n, uncertain: s.Uncertain.n, n: o.evidence.reviews };
}

const REC_TONE = { "Start now": "violet", "Quick win": "pos", "Plan next": "blue", "Validate first": "amber" } as const;

function OppDetail({ o }: { o: Opportunity }) {
  const d = useApi<Opportunity>(`/opportunities/${o.opportunity_id}`);
  const pm = o.pm_brief, ev = o.evidence;
  return (
    <div className="opp__detail pm">
      <div className="pm__head">
        <Chip tone={REC_TONE[pm.recommendation]}>{pm.recommendation}</Chip>
        <Chip>Effort {pm.effort} · {pm.effort_note}</Chip>
        <Chip tone={pm.evidence_confidence === "High" ? "pos" : pm.evidence_confidence === "Medium" ? "mix" : "neg"}>Evidence confidence: {pm.evidence_confidence}</Chip>
      </div>
      <div className="pm__grid">
        <div>
          <h4>The problem</h4>
          <p>{pm.problem}</p>
          <p><b>Who feels it.</b> {pm.who_is_affected}</p>
          <div className="mini">
            <span><b>{num(ev.reviews)}</b> reviews ({pct(ev.pct_of_dataset)} of the dataset)</span><span><b>{pct(ev.negative_share_pct)}</b> negative</span>
            <span><b>{pct(ev.switching_or_warning_or_non_return_pct)}</b> say or signal they will leave (dataset: {pct(ev.baseline_switching_or_warning_or_non_return_pct)})</span>
          </div>
          <div className="chips">{Object.entries(o.top_service_categories_in_evidence).map(([k, v]) => <Chip key={k}>{k} · {v}</Chip>)}</div>
        </div>
        <div>
          <h4>Why it happens <Chip tone="amber">hypotheses to test</Chip></h4>
          <ul className="bullets">{pm.why_it_happens_hypotheses.map((x) => <li key={x}>{x}</li>)}</ul>
          <h4>What made the priority score</h4>
          <ScoreStack o={o} legend />
        </div>
      </div>
      <h4>What we would build</h4>
      <ol className="pm__proposal">{pm.proposal.map((x) => <li key={x.title}><b>{x.title}.</b> {x.what}</li>)}</ol>
      <div className="pm__grid">
        <div><h4>Why it should lift repeat booking <Chip tone="amber">hypothesis</Chip></h4><p>{pm.why_it_should_lift_repeat_booking}</p></div>
        <div><h4>Success looks like</h4><p>{pm.success_looks_like}</p><p className="pm__note"><b>Watch out.</b> {pm.watch_outs}</p></div>
      </div>
      <h4>What customers actually said</h4>
      <Async state={d}>{(x) => <div className="quotes">{(x.evidence_quotes ?? []).slice(0, 4).map((e) => <QuoteCard key={e.evidence_id} e={e} />)}</div>}</Async>
      <p className="pm__note">{pm.labels}</p>
    </div>
  );
}

export function OpportunityList({ items, onOpen }: { items: Opportunity[]; onOpen: (t: DrawerTarget) => void }) {
  const [open, setOpen] = useState<string | null>(items[0]?.opportunity_id ?? null);
  return (
    <div className="opps">
      {items.map((o) => {
        const on = open === o.opportunity_id;
        return (
          <article className={`opp ${on ? "is-open" : ""}`} key={o.opportunity_id}>
            <button type="button" className="opp__head" aria-expanded={on} onClick={() => setOpen(on ? null : o.opportunity_id)}>
              <span className="opp__rank">{String(o.priority_rank).padStart(2, "0")}</span>
              <span className="opp__main">
                <span className="opp__title">{o.title}</span>
                <span className="opp__chips"><Chip tone={PRIORITY_TONE[o.priority]}>{o.priority} priority</Chip><Chip>{THEME_SHORT[o.evidence.related_theme]}</Chip></span>
                <span className="opp__meta">{num(o.evidence.reviews)} reviews · {pct(o.evidence.pct_of_dataset)} of the dataset · {pct(o.evidence.negative_share_pct)} negative · {o.pm_brief.recommendation} · effort {o.pm_brief.effort}</span>
                <ScoreStack o={o} />
              </span>
              <span className="opp__score"><b>{score(o)}</b><small>PRIORITY</small></span>
            </button>
            {on && (
              <div className="opp__body">
                <div className="opp__read">
                  <div><b>Read the actual comments behind this priority</b><span>{num(o.evidence.reviews)} reviews, in full, with source links</span></div>
                  <button type="button" className="btn btn--primary" onClick={() => onOpen({ title: o.title, subtitle: o.customer_problem, base: { opportunity: o.opportunity_id }, initialSentiment: "Negative" })}>Read the comments →</button>
                </div>
                <SentimentBar row={sentRow(o)} height={10} />
                <OppDetail o={o} />
              </div>
            )}
          </article>
        );
      })}
    </div>
  );
}

function Compare({ items }: { items: Opportunity[] }) {
  const [a, setA] = useState(items[0].opportunity_id), [b, setB] = useState(items[1].opportunity_id);
  const A = items.find((o) => o.opportunity_id === a)!, B = items.find((o) => o.opportunity_id === b)!;
  const rows: [string, (o: Opportunity) => string][] = [
    ["Priority score", (o) => `${score(o)}`], ["Reviews", (o) => num(o.evidence.reviews)], ["Share unhappy (negative)", (o) => pct(o.evidence.negative_share_pct)],
    ["Say or signal they will leave", (o) => pct(o.evidence.switching_or_warning_or_non_return_pct)], ["Classed as Non-Return (all)", (o) => pct(o.evidence.non_return_pct)], ["Effort", (o) => o.pm_brief.effort], ["Evidence confidence", (o) => o.pm_brief.evidence_confidence], ["PM call", (o) => o.pm_brief.recommendation],
    ["Evidence strength", (o) => `${Math.round(o.prioritisation.evidence_strength * 100)}/100`], ["Analyst impact (1–5)", (o) => `${o.prioritisation.impact_judgement_1_to_5}`],
  ];
  const sel = (v: string, set: (s: string) => void, label: string) => (
    <select className="sel" value={v} onChange={(e) => set(e.target.value)} aria-label={label}>{items.map((o) => <option key={o.opportunity_id} value={o.opportunity_id}>{o.opportunity_id} · {o.title}</option>)}</select>
  );
  return (
    <Card title="Compare two problem areas">
      <div className="cmp__pick">{sel(a, setA, "Area A")}<span>vs</span>{sel(b, setB, "Area B")}</div>
      <table className="cmp"><thead><tr><th /><th>{A.opportunity_id}</th><th>{B.opportunity_id}</th></tr></thead>
        <tbody>{rows.map(([k, f]) => <tr key={k}><td>{k}</td><td>{f(A)}</td><td>{f(B)}</td></tr>)}</tbody></table>
      <p className="gcard__sub">{score(A) === score(B) ? "Same priority score." : `${score(A) > score(B) ? A.title : B.title} has a priority score ${Math.abs(score(A) - score(B))} points higher.`}</p>
    </Card>
  );
}

export default function OpportunitiesSection({ onOpen }: { onOpen: (t: DrawerTarget) => void }) {
  const opps = useApi<Opportunity[]>("/opportunities");
  const [pick, setPick] = useState<string | null>(null);
  return (
    <Section id="opportunities" eyebrow="1 · What to fix first" title="Where to act first" lede="Nine opportunity areas, ranked, each written as a product manager would: the problem, why it happens, what to build, why it should lift repeat booking, and how we would know. Open one for the full brief and the real comments behind it.">
      <Async state={opps}>
        {(items) => (
          <>
            <Card title="How the priority score works" accent="violet">
              <p className="gcard__sub">Every area gets a priority score from 0 to 100. A higher score means “look at this sooner”. The score goes up when:</p>
              <div className="explain">
                <span><i style={{ background: "var(--violet)" }} /><b>More customers</b> mention it</span>
                <span><i style={{ background: "var(--neg)" }} /><b>More of them are unhappy</b> about it</span>
                <span><i style={{ background: "var(--blue)" }} />The <b>evidence is strong</b>: many reviews across several sources</span>
                <span><i style={{ background: "var(--amber)" }} />It links to <b>switching, warning others or not returning</b></span>
                <span><i style={{ background: "var(--pink)" }} />The analyst judges the <b>impact on repeat booking</b> to be high (a hypothesis)</span>
              </div>
              <p className="gcard__sub">The coloured bar under each area shows which of these pushed its score up. The explanations marked “hypothesis” are product ideas, not proven findings.</p>
            </Card>
            <OpportunityList items={items} onOpen={onOpen} />
            <div className="grid2">
              <Card title="Big problems vs. link to leaving" sub="Further right = more of all reviews mention it. Higher = more of its reviews warn others, mention switching or say they will not return. Click a bubble to jump to the list.">
                <BubbleChart items={items} selected={pick} onPick={(id) => { setPick(id); document.getElementById("opportunities")?.scrollIntoView({ behavior: "smooth" }); }} />
              </Card>
              <Compare items={items} />
            </div>
            <details className="more">
              <summary>See all areas in a table</summary>
              <div className="tablewrap"><table className="tbl tbl--pm"><thead><tr><th>#</th><th>Opportunity</th><th>PM call</th><th>Customer problem</th><th>What we would build</th><th>Why it should lift repeat booking (hypothesis)</th><th>Evidence</th><th>Effort</th><th>Confidence</th></tr></thead>
                <tbody>{items.map((o) => (
                  <tr key={o.opportunity_id}><td>{o.priority_rank}</td><td><b>{o.title}</b><br /><small>score {score(o)} · {o.priority}</small></td><td>{o.pm_brief.recommendation}</td><td>{o.customer_problem}</td>
                    <td>{o.pm_brief.proposal.map((x) => x.title).join(" · ")}</td><td>{o.pm_brief.why_it_should_lift_repeat_booking.split(". ")[0]}.</td>
                    <td>{num(o.evidence.reviews)} reviews · {pct(o.evidence.negative_share_pct)} negative · {pct(o.evidence.switching_or_warning_or_non_return_pct)} leave signals</td><td>{o.pm_brief.effort}</td><td>{o.pm_brief.evidence_confidence}</td></tr>))}</tbody></table></div>
            </details>
          </>
        )}
      </Async>
    </Section>
  );
}
