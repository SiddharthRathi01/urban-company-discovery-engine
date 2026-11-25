import { useState } from "react";
import type { Behaviour, BehaviourDetail, CompareGroup, SegmentSplit } from "../../api/types";
import { Donut } from "../../components/charts";
import { Async, Card, Chip, QuoteCard, Section } from "../../components/ui";
import { useApi } from "../../hooks/useApi";
import { THEME_SHORT, num, pct } from "../../utils/format";

const C_RETURN = "var(--pos)", C_NON = "var(--neg)", C_INS = "var(--slate)";

function Split({ r }: { r: SegmentSplit }) {
  return (
    <div className="segsplit__row" title={`${r.segment}: ${r.return_pct}% Return, ${r.non_return_pct}% Non-Return, ${r.insufficient_pct}% Insufficient`}>
      <span>{r.segment}<small> n={num(r.n)}</small></span>
      <div className="sbar" style={{ height: 12 }}><span style={{ flex: r.return_pct, background: C_RETURN }} /><span style={{ flex: r.non_return_pct, background: C_NON }} /><span style={{ flex: r.insufficient_pct, background: C_INS }} /></div>
      <small>{pct(r.return_pct, 0)} / {pct(r.non_return_pct, 0)}</small>
    </div>
  );
}

function OwnWords({ slug, title, tone }: { slug: string; title: string; tone: "pos" | "neg" }) {
  const d = useApi<BehaviourDetail>(`/behaviour/classes/${slug}`);
  return (
    <Card title={title} accent={tone === "pos" ? "violet" : "amber"}>
      <Async state={d}>
        {(c) => {
          const by = Object.fromEntries(c.evidence_quotes.map((e) => [e.evidence_id, e]));
          const pick = (ids: string[] = [], k: number) => ids.slice(0, k).map((i) => by[i]).filter(Boolean);
          const stated = pick(c.representative_evidence_ids, 3);
          const sig = Object.entries(c.signalled_reasons ?? {}).filter(([, v]) => v.evidence_ids.length).map(([k, v]) => [k, v.n, pick(v.evidence_ids, 1)] as const);
          const inferred = pick(c.inferred_evidence_ids, 2);
          return (
            <>
              <h4>Said in the first person <Chip tone="pos">{c.by_basis.Stated ?? 0}</Chip></h4>
              <div className="quotes">{stated.map((e) => <QuoteCard key={e.evidence_id} e={e} compact />)}</div>
              <h4>Signalled <Chip tone="blue">{num(c.by_basis.Signalled ?? 0)}</Chip></h4>
              {sig.map(([reason, n, qs]) => <div key={reason}><p className="gcard__sub">{reason} · {num(n)}</p><div className="quotes">{qs.map((e) => <QuoteCard key={e.evidence_id} e={e} compact />)}</div></div>)}
              <h4>Inferred from the experience described <Chip tone="violet">{num(c.by_basis.Inferred ?? 0)}</Chip></h4>
              <div className="quotes">{inferred.map((e) => <QuoteCard key={e.evidence_id} e={e} compact />)}</div>
            </>
          );
        }}
      </Async>
    </Card>
  );
}

export default function BehaviourSection() {
  const b = useApi<Behaviour>("/behaviour");
  const [view, setView] = useState<"strong" | "all">("strong");
  return (
    <Section id="behaviour" eyebrow="3 · Return and non-return" title="Will customers book again?" lede="Every review is placed as Return (likely to book again), Non-Return (unlikely to), or Insufficient Evidence, and carries how that was decided and how sure we are. These are predictions from what customers wrote, not observed rebooking.">
      <Async state={b}>
        {(d) => {
          const s = d.summary, cmp = d.comparison, g = (k: CompareGroup) => (view === "strong" ? (k === "return" ? "return_stated_signalled" : "non_return_stated_signalled") : k) as CompareGroup;
          return (
            <>
              <Card className="rr-card">
                <div className="rr-hero">
                  <div>
                    <div className="rr-big"><b>{pct(s.classified_pct, 1)}</b><span>of {num(s.classified + s.insufficient)} reviews could be placed as Return or Non-Return.</span></div>
                    <div className="rr-split">
                      <div><span>Return</span><div className="hbar"><i style={{ width: `${s.return_pct}%`, background: C_RETURN }} /><span>{num(s.return)}</span></div><small>{pct(s.return_pct)}</small></div>
                      <div><span>Non-Return</span><div className="hbar"><i style={{ width: `${s.non_return_pct}%`, background: C_NON }} /><span>{num(s.non_return)}</span></div><small>{pct(s.non_return_pct)}</small></div>
                      <div><span>Insufficient</span><div className="hbar"><i style={{ width: `${s.insufficient_pct}%`, background: C_INS }} /><span>{num(s.insufficient)}</span></div><small>{pct(s.insufficient_pct)}</small></div>
                    </div>
                  </div>
                  <div className="donutrow"><Donut size={180} parts={[{ label: "Return", value: s.return, color: C_RETURN }, { label: "Non-Return", value: s.non_return, color: C_NON }, { label: "Insufficient", value: s.insufficient, color: C_INS }]} />
                    <ul className="classlist">{d.distribution.map((x) => <li key={x.class}><i style={{ background: x.class === "Return" ? C_RETURN : x.class === "Non-Return" ? C_NON : C_INS }} /><div><b>{x.class}</b><small>{d.definitions[x.class]}</small></div></li>)}</ul></div>
                </div>
              </Card>

              <div className="grid3">
                {(["Stated", "Signalled", "Inferred"] as const).map((k) => (
                  <Card key={k} title={`${k} · ${num(s.by_basis[k].n)}`} sub={`${pct(s.by_basis[k].pct_of_dataset)} of reviews · ${k === "Stated" ? "high" : k === "Signalled" ? "medium" : "medium to low"} confidence`}>
                    <p className="gcard__sub">{d.basis_definitions[k]}</p>
                  </Card>
                ))}
              </div>

              <div className="grid2">
                <Card title="What the evidence says"><ul className="bullets">{d.patterns.map((p) => <li key={p}>{p}</li>)}</ul></Card>
                <Card title="What separates customers who return from customers who do not" sub={`Share of each group's reviews that raise each theme. ${num(cmp.groups[g("return")])} Return vs ${num(cmp.groups[g("non_return")])} Non-Return reviews.`}>
                  <div className="pills" role="tablist" aria-label="Which reviews to compare">
                    <button type="button" className={`pill ${view === "strong" ? "is-on" : ""}`} onClick={() => setView("strong")}>Stated + signalled (stronger evidence)</button>
                    <button type="button" className={`pill ${view === "all" ? "is-on" : ""}`} onClick={() => setView("all")}>All classified</button>
                  </div>
                  <div className="legend"><span><i style={{ background: C_RETURN }} />Return</span><span><i style={{ background: C_NON }} />Non-Return</span></div>
                  <div className="cmpgrid4">
                    {Object.keys(cmp.theme_prevalence_pct).map((t) => (
                      <div className="cmpgrid4__row" key={t}><span className="cmpgrid__label">{THEME_SHORT[t]}</span>
                        <div className="cmpgrid4__bars">
                          {(["return", "non_return"] as const).map((k) => <div key={k} className="hbar"><i style={{ width: `${Math.min(100, cmp.theme_prevalence_pct[t][g(k)])}%`, background: k === "return" ? C_RETURN : C_NON }} /><span>{pct(cmp.theme_prevalence_pct[t][g(k)], 0)}</span></div>)}
                        </div></div>))}
                  </div>
                </Card>
              </div>

              <div className="grid2">
                <Card title="What pushes customers away" sub="Problems far more common in Non-Return (stated or signalled) than in Return reviews.">
                  <div className="cmpgrid4">{cmp.top_leaving_drivers.map((x) => (
                    <div className="cmpgrid4__row" key={x.code}><span className="cmpgrid__label">{x.issue}</span><div className="cmpgrid4__bars">
                      <div className="hbar"><i style={{ width: `${Math.min(100, x.non_return_pct * 2)}%`, background: C_NON }} /><span>{pct(x.non_return_pct, 0)} of Non-Return</span></div>
                      <div className="hbar"><i style={{ width: `${Math.min(100, x.return_pct * 2)}%`, background: C_RETURN }} /><span>{pct(x.return_pct, 0)} of Return</span></div></div></div>))}</div>
                </Card>
                <Card title="What keeps customers" sub="Positive experiences far more common in Return (stated or signalled) reviews.">
                  <div className="cmpgrid4">{cmp.top_staying_drivers.map((x) => (
                    <div className="cmpgrid4__row" key={x.code}><span className="cmpgrid__label">{x.issue}</span><div className="cmpgrid4__bars">
                      <div className="hbar"><i style={{ width: `${Math.min(100, x.return_pct)}%`, background: C_RETURN }} /><span>{pct(x.return_pct, 0)} of Return</span></div>
                      <div className="hbar"><i style={{ width: `${Math.min(100, x.non_return_pct)}%`, background: C_NON }} /><span>{pct(x.non_return_pct, 0)} of Non-Return</span></div></div></div>))}</div>
                </Card>
              </div>
              <p className="callout callout--amber">{cmp.caution} {d.stated_returners_dissatisfied.n} of {d.stated_returners_dissatisfied.of} ({pct(d.stated_returners_dissatisfied.pct, 0)}) customers who say they came back are themselves Negative or Mixed: loyal, but unhappy.</p>

              <div className="grid3">
                {([["By service category", cmp.return_share_by_segment.service_category], ["By source", cmp.return_share_by_segment.source], ["By city", cmp.return_share_by_segment.city]] as const).map(([title, rows]) => (
                  <Card key={title} title={title} sub="Return / Non-Return share of each group's reviews (rest is Insufficient).">
                    <div className="legend"><span><i style={{ background: C_RETURN }} />Return</span><span><i style={{ background: C_NON }} />Non-Return</span><span><i style={{ background: C_INS }} />Insufficient</span></div>
                    <div className="segsplit">{rows.map((r) => <Split key={r.segment} r={r} />)}</div>
                  </Card>
                ))}
              </div>

              <div className="grid2">
                <OwnWords slug="return" title="In their own words: likely to return" tone="pos" />
                <OwnWords slug="non-return" title="In their own words: unlikely to return" tone="neg" />
              </div>
            </>
          );
        }}
      </Async>
    </Section>
  );
}
