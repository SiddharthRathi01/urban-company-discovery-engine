import GoldenSet from "../components/GoldenSet";
import { PageHero } from "../components/ui";

export default function GoldenPage() {
  return (
    <>
      <PageHero eyebrow="Golden data set" title={<>The engine compared with <span className="gradient-text">hand-made labels</span></>}
        lede="A golden set is a sample of real comments that a person labelled by hand. The engine reads the same comments and its answers are compared with the human labels. Upload another hand-labelled CSV to test the engine yourself." />
      <GoldenSet />
    </>
  );
}
