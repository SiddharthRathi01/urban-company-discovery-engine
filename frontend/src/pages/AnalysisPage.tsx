import { useState } from "react";
import CommentsDrawer, { type DrawerTarget } from "../components/CommentsDrawer";
import { PageHero } from "../components/ui";
import AlternativesSection from "./analysis/Alternatives";
import BehaviourSection from "./analysis/Behaviour";
import NeedsSection from "./analysis/Needs";
import OpportunitiesSection from "./analysis/Opportunities";
import SegmentsSection from "./analysis/Segments";
import ThemesSection from "./analysis/Themes";

const JUMP = [["opportunities", "What to fix first"], ["themes", "Recurring problems"], ["behaviour", "Return and non-return"], ["alternatives", "Alternatives"], ["segments", "Who differs"], ["needs", "Unmet needs"]];

export default function AnalysisPage() {
  const [drawer, setDrawer] = useState<DrawerTarget | null>(null);
  return (
    <>
      <PageHero eyebrow="Analysis" title={<>From customer reviews to <span className="gradient-text">ranked opportunities</span></>}
        lede="Which problems matter most, how they differ for customers who return and customers who do not, where customers go instead, and what they keep asking for. Every claim opens the real reviews behind it.">
        <nav className="jump" aria-label="On this page">{JUMP.map(([id, label]) => <a key={id} href={`#${id}`} onClick={(e) => { e.preventDefault(); document.getElementById(id)?.scrollIntoView({ behavior: "smooth" }); }}>{label}</a>)}</nav>
      </PageHero>
      <OpportunitiesSection onOpen={setDrawer} />
      <ThemesSection onOpen={setDrawer} />
      <BehaviourSection />
      <AlternativesSection />
      <SegmentsSection />
      <NeedsSection onOpen={setDrawer} />
      <CommentsDrawer target={drawer} onClose={() => setDrawer(null)} />
    </>
  );
}
