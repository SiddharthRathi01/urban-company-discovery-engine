import { useState } from "react";
import type { Segment } from "../../api/types";
import { HeatGrid } from "../../components/charts";
import { Async, Card, Chip, QuoteCard, Section } from "../../components/ui";
import { useApi } from "../../hooks/useApi";
import { THEME_SHORT, num } from "../../utils/format";

const COLS = Object.keys(THEME_SHORT).map((k) => ({ key: k, label: THEME_SHORT[k].split(" ")[0] + " " + (THEME_SHORT[k].split(" ")[1] ?? "") }));

function Heat({ dimension, min }: { dimension: string; min: number }) {
  const s = useApi<Segment[]>(`/segments/${dimension}`, { min_n: min, page_size: 40 });
  return (
    <Async state={s}>
      {(items) => {
        const rows = items.filter((x) => !x.segment_id.endsWith("STATED")).sort((a, b) => (b.n ?? 0) - (a.n ?? 0));
        return (
          <>
            <HeatGrid rows={rows.map((r) => ({ key: r.segment_id, label: r.name, n: r.n ?? 0 }))} cols={COLS} cell={(r, c) => rows.find((x) => x.segment_id === r)!.theme_prevalence[c].pct} />
            <ul className="bullets bullets--tight">{rows.slice(0, 6).map((r) => <li key={r.segment_id}><b>{r.name}</b> (n={num(r.n ?? 0)}{r.small_sample ? ", small sample" : ""}): {r.important_difference}.</li>)}</ul>
          </>
        );
      }}
    </Async>
  );
}

function Vetted({ dimension, title, lede }: { dimension: string; title: string; lede: string }) {
  const s = useApi<Segment[]>(`/segments/${dimension}`, { page_size: 40 });
  const [open, setOpen] = useState<string | null>(null);
  const detail = useApi<Segment>(open ? `/segments/${dimension}/${open}` : null);
  return (
    <Card title={title} sub={lede}>
      <Async state={s}>
        {(items) => (
          <div className="vet">
            {items.map((x) => (
              <div key={x.segment_id}>
                <button type="button" className={`vet__row ${open === x.segment_id ? "is-open" : ""}`} onClick={() => setOpen(open === x.segment_id ? null : x.segment_id)} aria-expanded={open === x.segment_id}>
                  <span>{x.name}</span><Chip>{x.n_vetted_examples} examples</Chip>
                </button>
                {open === x.segment_id && (
                  <div className="vet__body"><Async state={detail}>{(d) => <div className="quotes">{(d.evidence_quotes ?? []).slice(0, 3).map((e) => <QuoteCard key={e.evidence_id} e={e} compact />)}</div>}</Async></div>
                )}
              </div>
            ))}
          </div>
        )}
      </Async>
    </Card>
  );
}

export default function SegmentsSection() {
  return (
    <Section id="segments" eyebrow="5 · Who differs" title="How do the patterns differ by service, city, household and how customers found Urban Company?" lede="Heat cells show the share of each group's reviews that raise a problem theme. Rows with few reviews are small samples; household type and discovery channel are only stated in a few dozen reviews, so those are shown as hand-picked examples, not percentages.">
      <div className="grid2">
        <Card title="By service category (at least 30 reviews)"><Heat dimension="service_category" min={30} /></Card>
        <Card title="By city (at least 8 reviews)"><Heat dimension="city" min={8} /></Card>
      </div>
      <div className="grid2">
        <Vetted dimension="household_type" title="By household type: examples" lede="Open a row to read the reviews. These are vetted examples, not prevalence." />
        <Vetted dimension="discovery_channel" title="By how they found Urban Company: examples" lede="Referral, ads, research and marketplace purchases that customers mention." />
      </div>
      <Vetted dimension="booking_triggers" title="What triggers a booking: examples" lede="When or why customers decided they needed a service (a breakdown, a move, a festival…)." />
    </Section>
  );
}
