import type { Opportunity, Theme } from "../../api/types";
import { SentimentBar } from "../../components/charts";
import type { DrawerTarget } from "../../components/CommentsDrawer";
import { Async, Card, Chip, QuoteCard, Section } from "../../components/ui";
import { useApi } from "../../hooks/useApi";
import { SOURCE_SHORT, THEME_SHORT, num, pct } from "../../utils/format";
import type { Evidence } from "../../api/types";

interface ThemeDetail extends Theme { evidence_quotes: Evidence[]; negative_evidence_ids?: string[] }

function ThemeCard({ t, opps, onOpen }: { t: Theme; opps: Opportunity[]; onOpen: (d: DrawerTarget) => void }) {
  const d = useApi<ThemeDetail>(`/themes/${t.theme_id}`);
  const s = t.sentiment, hurt = s.Negative.n + s.Mixed.n;
  const help = opps.filter((o) => o.evidence.related_theme === t.theme_id);
  const quote = d.data?.evidence_quotes.find((e) => e.sentiment_label === "Negative") ?? d.data?.evidence_quotes[0];
  return (
    <article className="theme">
      <header>
        <span className="theme__id">{t.theme_id}</span>
        <div><h3>{t.name}</h3><p className="gcard__sub">{t.definition}</p></div>
        <div className="theme__count"><b>{num(t.review_count)}</b><small>{pct(t.pct_of_dataset)} of reviews</small></div>
      </header>
      <SentimentBar row={{ positive: s.Positive.n, neutral: s.Neutral.n, negative: s.Negative.n, mixed: s.Mixed.n, uncertain: s.Uncertain.n, n: t.review_count }} />
      <p className="theme__read"><Chip tone="neg">{num(hurt)} unhappy</Chip> of {num(t.review_count)} reviews ({pct((100 * hurt) / t.review_count)}). Seen in {t.by_source.filter((b) => b.pct_of_source_reviews >= 5).length} of 4 sources: {t.by_source.map((b) => `${SOURCE_SHORT[b.source]} ${pct(b.pct_of_source_reviews, 0)}`).join(" · ")}.</p>
      <div className="chips">{t.subthemes.filter((x) => x.n >= 5).sort((a, b) => b.n - a.n).slice(0, 6).map((x) => <Chip key={x.subtheme_id}>{x.name} · {x.n}</Chip>)}</div>
      {quote && <QuoteCard e={quote} compact />}
      <p className="theme__help"><b>What would help.</b> {help.length ? help.map((o) => o.title).join("; ") : "See the opportunities above."}</p>
      <p className="gcard__sub">{t.interpretation}</p>
      <button type="button" className="btn btn--primary" onClick={() => onOpen({ title: THEME_SHORT[t.theme_id], subtitle: t.name, base: { theme: t.theme_id }, initialSentiment: "Negative" })}>Read the unhappy comments →</button>
    </article>
  );
}

export default function ThemesSection({ onOpen }: { onOpen: (t: DrawerTarget) => void }) {
  const themes = useApi<Theme[]>("/themes");
  const opps = useApi<Opportunity[]>("/opportunities");
  return (
    <Section id="themes" eyebrow="2 · Recurring problems" title="What problems keep coming up?" lede="Reviews are grouped into five themes, so you can see which problems come up again and again. One review can touch several themes, so the counts overlap.">
      <Async state={themes}>
        {(ts, meta) => (
          <Async state={opps}>
            {(os) => (
              <>
                <div className="themes">{[...ts].sort((a, b) => (b.sentiment.Negative.n + b.sentiment.Mixed.n) - (a.sentiment.Negative.n + a.sentiment.Mixed.n)).map((t) => <ThemeCard key={t.theme_id} t={t} opps={os} onOpen={onOpen} />)}</div>
                <Card title="How the grouping was done" sub={meta.emergence}>
                  <p className="gcard__sub"><b>Counting method.</b> {meta.counting_method}</p>
                </Card>
              </>
            )}
          </Async>
        )}
      </Async>
    </Section>
  );
}
