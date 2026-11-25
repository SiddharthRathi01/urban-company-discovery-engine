import { useState } from "react";
import type { NeedItem, NeedDetail } from "../../api/types";
import type { DrawerTarget } from "../../components/CommentsDrawer";
import { Async, Chip, QuoteCard, Section } from "../../components/ui";
import { useApi } from "../../hooks/useApi";
import { num, pct } from "../../utils/format";

function Detail({ id }: { id: string }) {
  const d = useApi<NeedDetail>(`/unmet-needs/${id}`);
  return <Async state={d}>{(n) => <div className="quotes">{(n.evidence_quotes ?? []).slice(0, 3).map((e) => <QuoteCard key={e.evidence_id} e={e} compact />)}</div>}</Async>;
}

export default function NeedsSection({ onOpen }: { onOpen: (t: DrawerTarget) => void }) {
  const n = useApi<NeedItem[]>("/unmet-needs");
  const [open, setOpen] = useState<string | null>(null);
  return (
    <Section id="needs" eyebrow="6 · Unmet needs" title="What do customers keep asking for?" lede="Needs that come up again and again across reviews, with how often, and which opportunity they feed. Counts are indicative: each need is a phrase rule with a measured precision.">
      <Async state={n}>
        {(items) => {
          const max = Math.max(...items.map((x) => x.n_reviews));
          return (
            <div className="needs">
              {items.map((x) => (
                <div className="need" key={x.unmet_need_id}>
                  <button type="button" className="need__row" aria-expanded={open === x.unmet_need_id} onClick={() => setOpen(open === x.unmet_need_id ? null : x.unmet_need_id)}>
                    <span className="need__rank">{x.rank_by_frequency}</span>
                    <span className="need__name">{x.name}<small>{x.definition}</small></span>
                    <span className="need__bar"><i style={{ width: `${(100 * x.n_reviews) / max}%` }} /></span>
                    <span className="need__n"><b>{num(x.n_reviews)}</b><small>{pct(x.pct_of_dataset)}</small></span>
                    <Chip tone="violet">→ {x.linked_opportunity}</Chip>
                  </button>
                  {open === x.unmet_need_id && (
                    <div className="need__body">
                      <p className="gcard__sub">Rule precision (spot-check): {Math.round(x.rule_precision_estimate * 100)}% · {num(x.return_relevance.non_return_stated_or_signalled)} of these say or signal they will leave · {pct(x.return_relevance.switching_or_warning_signals_pct)} leave signals (dataset: {pct(x.return_relevance.baseline_switching_or_warning_signals_pct)}).</p>
                      <Detail id={x.unmet_need_id} />
                      <button type="button" className="btn" onClick={() => onOpen({ title: x.name, subtitle: x.definition, base: { unmet_need: x.unmet_need_id } })}>Read all {num(x.n_reviews)} comments →</button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          );
        }}
      </Async>
    </Section>
  );
}
