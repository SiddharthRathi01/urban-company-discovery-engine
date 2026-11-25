import { useState } from "react";
import { Link } from "react-router-dom";
import type { MoodRow, NeedItem, Opportunity, Overview, Theme } from "../api/types";
import { DivergingBars, MoodBars, SentimentLegend } from "../components/charts";
import CommentsDrawer, { type DrawerTarget } from "../components/CommentsDrawer";
import UploadDrawer from "../components/UploadDrawer";
import { Async, Card, Chip, Kpi, PageHero, Section } from "../components/ui";
import { useApi } from "../hooks/useApi";
import { THEME_SHORT, num, pct } from "../utils/format";

const unhappy = (t: Theme) => t.sentiment.Negative.n + t.sentiment.Mixed.n;

export default function FeedbackPage() {
  const ov = useApi<Overview>("/overview");
  const themes = useApi<Theme[]>("/themes");
  const opps = useApi<Opportunity[]>("/opportunities");
  const needs = useApi<NeedItem[]>("/unmet-needs");
  const bySource = useApi<MoodRow[]>("/mood", { by: "source", sort: "n" });
  const byIssue = useApi<MoodRow[]>("/mood", { by: "issue", min_n: 10 });
  const byCategory = useApi<MoodRow[]>("/mood", { by: "category", min_n: 30, sort: "n" });
  const byCity = useApi<MoodRow[]>("/mood", { by: "city", min_n: 8, sort: "n" });
  const [drawer, setDrawer] = useState<DrawerTarget | null>(null);
  const [upload, setUpload] = useState(false);

  return (
    <>
      <PageHero eyebrow="Urban Company Discovery Engine" title={<>What Urban Company customers say, <span className="gradient-text">and what to fix first</span></>}
        lede={<>This page reads real customer reviews and shows, in plain language: how people feel, which problems keep coming up, and what to fix first. Every number can be traced back to real reviews. <Link to="/overview/evidence">See how the results were checked →</Link></>}>
        <div className="statusrow">
          <Async state={ov}>
            {(o) => (
              <div className="status"><span className="status__dot" />
                <span><b>Urban Company dataset loaded</b><small>urban_company_reviews_master.csv · {num(o.dataset.reviews_analysed)} reviews · 16 columns</small></span>
              </div>
            )}
          </Async>
          <button type="button" className="btn btn--primary" onClick={() => setUpload(true)}>⬆ Upload CSV</button>
        </div>
      </PageHero>

      <Section id="summary" eyebrow="1 · Summary" title="What the feedback says">
        <Async state={ov}>
          {(o) => {
            const d = o.dataset, s = d.sentiment;
            const lead = (["Negative", "Positive", "Neutral", "Mixed"] as const).reduce((a, b) => (s[b].n > s[a].n ? b : a), "Negative" as "Negative");
            const year = (x: string) => x.slice(0, 4);
            return (
              <>
                <p className="sec__lede">{num(d.reviews_analysed)} public reviews and posts from {d.by_source.length} sources, dated {year(d.date_range.earliest)} to {year(d.date_range.latest)}. Each one links to its original page.</p>
                <div className="kpis">
                  <Kpi tone="violet" label="Reviews analysed" value={num(d.reviews_analysed)} sub={`from ${d.by_source.length} public sources`} />
                  <Kpi label="Sources" value={d.by_source.length} sub={d.by_source.map((b) => `${b.source.split(" ")[0]} ${Math.round(b.pct)}%`).join(" · ")} />
                  <Kpi tone="amber" label="Average rating" value={`${d.rating.mean.toFixed(2)} ★`} sub={`${pct(d.rating.pct_1_2_star)} are 1–2 stars · ${num(d.rating.rated_reviews)} rated`} />
                  <Kpi label="Overall mood" value={lead} sub={`${pct(s.Negative.pct)} negative · ${pct(s.Positive.pct)} positive · ${pct(s.Mixed.pct)} mixed`} />
                  <Kpi tone="blue" label="Problem areas found" value={byIssue.data ? byIssue.data.filter((r) => !r.key.startsWith("pos_")).length : "…"} sub={`${pct((100 * o.headline_metrics.reviews_with_at_least_one_theme) / d.reviews_analysed)} of reviews grouped into 5 themes`} />
                </div>
              </>
            );
          }}
        </Async>
        <Card title="Generated brief" className="brief-card">
          <Async state={themes}>
            {(ts) => (
              <Async state={opps}>
                {(os) => (
                  <Async state={needs}>
                    {(ns) => {
                      const problems = ts.filter((t) => t.theme_id !== "T4").sort((a, b) => unhappy(b) - unhappy(a)).slice(0, 2);
                      const good = byIssue.data?.find((r) => r.key === "pos_quality_pro");
                      const top = os[0], need = ns[0];
                      return (
                        <div className="brief">
                          <div><Chip tone="neg">Biggest problems</Chip><p>{problems.map((t, i) => <span key={t.theme_id}>{i ? " and " : ""}<b>{THEME_SHORT[t.theme_id]}</b> ({num(unhappy(t))} of {num(t.review_count)} reviews are unhappy)</span>)}.</p></div>
                          <div><Chip tone="pos">What is working</Chip><p>{good ? <><b>Skilled, courteous professionals</b> are praised in {num(good.n)} reviews ({pct(good.positive_share)} of them positive).</> : "Loading…"}</p></div>
                          <div><Chip tone="blue">What people ask for</Chip><p><b>{need.name}</b>: {num(need.n_reviews)} reviews ({pct(need.pct_of_dataset)} of the dataset).</p></div>
                          <div><Chip tone="violet">Fix first</Chip><p><b>{top.title}</b> has the highest priority (score {Math.round(top.prioritisation.score * 100)} out of 100). What customers need: {top.expected_customer_benefit.charAt(0).toLowerCase() + top.expected_customer_benefit.slice(1)}</p></div>
                        </div>
                      );
                    }}
                  </Async>
                )}
              </Async>
            )}
          </Async>
        </Card>
      </Section>

      <Section id="mood" eyebrow="2 · How people feel" title="Are people happy or unhappy?" lede="Each review is marked positive, neutral, mixed or negative from the words the customer used (and their star rating, where there is one). Click a row to read the reviews.">
        <div className="grid2">
          <Card title="Mood by source" sub="Complaint sites are almost entirely negative by design; Google Play is the only source with many positive voices. Read each source on its own.">
            <Async state={bySource}>{(rows) => <><MoodBars rows={rows} onPick={(r) => setDrawer({ title: r.label, subtitle: `${num(r.n)} reviews from this source`, base: { source: r.key } })} /><SentimentLegend /></>}</Async>
          </Card>
          <Card title="Mood by problem area" sub="Coral bars (left) count unhappy reviews (Negative + Mixed), mint bars (right) count positive ones, on one scale. The total number of reviews is on the right. Areas are ordered by how unhappy they are.">
            <Async state={byIssue}>
              {(rows) => (
                <>
                  <DivergingBars rows={rows.filter((r) => !r.key.startsWith("pos_")).slice(0, 14)} />
                  <div className="legend"><span><i style={{ background: "var(--neg)" }} />Unhappy</span><span><i style={{ background: "var(--pos)" }} />Positive</span></div>
                </>
              )}
            </Async>
          </Card>
        </div>
      </Section>

      <Section id="who" eyebrow="3 · Who is saying it" title="Where do the differences show up?" lede={ov.data ? `Service category is named in ${pct((100 * ov.data.dataset.service_category_stated) / ov.data.dataset.reviews_analysed, 0)} of reviews and city in ${pct((100 * ov.data.dataset.city_stated) / ov.data.dataset.reviews_analysed, 0)}, so these groups are smaller. Sample sizes are shown on every row.` : undefined}>
        <div className="grid2">
          <Card title="Mood by service category" sub="Only reviews that name a service category.">
            <Async state={byCategory}>{(rows) => <MoodBars rows={rows} labelWidth={160} onPick={(r) => setDrawer({ title: r.label, subtitle: "Reviews that name this service", base: { category: r.key } })} />}</Async>
          </Card>
          <Card title="Mood by city" sub="Only reviews that name a city (cities with at least 8 reviews).">
            <Async state={byCity}>{(rows) => <MoodBars rows={rows} labelWidth={130} onPick={(r) => setDrawer({ title: r.label, subtitle: "Reviews that name this city", base: { city: r.key } })} />}</Async>
          </Card>
        </div>
      </Section>
      <CommentsDrawer target={drawer} onClose={() => setDrawer(null)} />
      <UploadDrawer open={upload} onClose={() => setUpload(false)} />
    </>
  );
}
