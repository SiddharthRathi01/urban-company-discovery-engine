import type { Alternative } from "../../api/types";
import { Async, Card, Chip, Section } from "../../components/ui";
import { useApi } from "../../hooks/useApi";
import { num } from "../../utils/format";

export default function AlternativesSection() {
  const a = useApi<Alternative[]>("/alternatives");
  return (
    <Section id="alternatives" eyebrow="4 · Where else customers turn" title="What do customers do outside the app?" lede="Only reviews where a customer names who they used or considered are counted. Real use is kept apart from advice to others and general comparisons.">
      <Async state={a}>
        {(items, meta) => (
          <>
            <div className="kpis kpis--3">
              <div className="kpi kpi--violet"><span className="kpi__label">Alternatives named</span><span className="kpi__value">{meta.summary.vetted_mentions_total}</span><span className="kpi__sub">reviews, each read by hand</span></div>
              <div className="kpi"><span className="kpi__label">Reported actual use</span><span className="kpi__value">{meta.summary.reported_use}</span><span className="kpi__sub">“I used / hired / switched”</span></div>
              <div className="kpi kpi--amber"><span className="kpi__label">Considering or general advice</span><span className="kpi__value">{meta.summary.considering + meta.summary.general_or_hypothetical}</span><span className="kpi__sub">{meta.summary.considering} deciding · {meta.summary.general_or_hypothetical} general</span></div>
            </div>
            <div className="altgrid">
              {items.map((x) => (
                <Card key={x.alternative_id} className="alt">
                  <h3 className="gcard__title">{x.alternative_type}</h3>
                  <div className="chips"><Chip tone="violet">{x.relevant_mentions} reviews</Chip><Chip tone="pos">{x.by_tier.reported_use} used</Chip><Chip tone="blue">{x.by_tier.considering} considering</Chip><Chip>{x.by_tier.general_or_hypothetical} general</Chip></div>
                  <p className="gcard__sub"><b>Used for.</b> {x.used_for}</p>
                  <h4>Why customers choose it</h4><ul className="bullets">{x.why_customers_choose_it.map((w) => <li key={w}>{w}</li>)}</ul>
                  <div className="proscons">
                    <div><h4>Advantages (customer-reported)</h4><ul className="bullets">{x.customer_reported_advantages.map((w) => <li key={w}>{w}</li>)}</ul></div>
                    <div><h4>Disadvantages</h4><ul className="bullets">{x.customer_reported_disadvantages.map((w) => <li key={w}>{w}</li>)}</ul></div>
                  </div>
                </Card>
              ))}
            </div>
            <Card title="WhatsApp, society and neighbour groups" accent="amber">
              <p className="gcard__sub">{meta.whatsapp_and_community_groups.finding} {num(meta.whatsapp_and_community_groups.reddit_posts_asking_for_recommendations)} Reddit posts ask other users for experiences or recommendations. Absence of evidence is not evidence of absence: these networks are invisible in public reviews.</p>
            </Card>
          </>
        )}
      </Async>
    </Section>
  );
}
