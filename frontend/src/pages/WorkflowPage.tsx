import { Link, useSearchParams } from "react-router-dom";
import type { Overview, Question, Trust } from "../api/types";
import { Async, Chip, PageHero, Section } from "../components/ui";
import NotebookView from "../components/NotebookView";
import { useApi } from "../hooks/useApi";

const STRENGTH_TONE: Record<string, "pos" | "mix" | "neg"> = { strong: "pos", moderate: "mix", weak: "neg" };

interface Step { title: string; text: string; out: string; tone: string }

const WORD: Record<number, string> = { 1: "One", 2: "Two", 3: "Three", 4: "Four", 5: "Five", 6: "Six", 7: "Seven", 8: "Eight", 9: "Nine", 10: "Ten" };
const word = (n: number) => (n ? WORD[n] ?? String(n) : "…");

function steps(collected: number, kept: number, themes: number, opps: number): Step[] {
  return [
    { title: "Collect", text: "We gather what real customers have written about Urban Company in public places: app-store reviews, Reddit posts and complaint sites.", out: `${collected.toLocaleString("en-IN")} comments gathered`, tone: "violet" },
    { title: "Clean", text: "Duplicates, spam and off-topic feedback are removed. Every comment we keep must link back to its original source.", out: `${kept.toLocaleString("en-IN")} comments kept`, tone: "blue" },
    { title: "Read", text: "Each comment is read for the customer's sentiment, the problem they raise, and return signals in their own words. These are interpreted from the feedback, not confirmed repeat bookings.", out: "Sentiment · Problem · Return signal", tone: "pink" },
    { title: "Group", text: "Similar problems and unmet needs are grouped into themes, so recurring patterns stand out instead of isolated complaints.", out: `${word(themes)} themes`, tone: "amber" },
    { title: "Prioritise", text: "Opportunities are ranked by how many customers face the problem, how much it affects them, and how strong the evidence is. Each comes with an actionable PM recommendation.", out: `${word(opps)} prioritised opportunities`, tone: "green" },
    { title: "Prove", text: "Every finding links to the original customer comments and their source URLs, so anyone can open and check them. The same evidence backs the answers to the discovery questions.", out: "Source-linked evidence", tone: "violet" },
  ];
}

export default function WorkflowPage() {
  const t = useApi<Trust>("/trust");
  const ov = useApi<Overview>("/overview");
  const qs = useApi<Question[]>("/questions");
  const collected = t.data?.funnel?.[0]?.n ?? 0;
  const kept = ov.data?.dataset.reviews_analysed ?? 0;
  const themes = useApi<unknown[]>("/themes").data?.length ?? 0;
  const opps = useApi<unknown[]>("/opportunities").data?.length ?? 0;
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") === "notebook" ? "notebook" : "engine";
  const pick = (t: "engine" | "notebook") => setParams(t === "engine" ? {} : { tab: t }, { replace: true });
  return (
    <>
      <PageHero eyebrow="The workflow" title={<>From scattered comments to <span className="gradient-text">clear opportunities</span></>}
        lede="Six simple steps turn thousands of customer comments into a short list of what to fix first, with proof behind every point." />
      <div className="wtabs" role="tablist" aria-label="Workflow views">
        <button type="button" role="tab" aria-selected={tab === "engine"} className={`wtab ${tab === "engine" ? "is-on" : ""}`} onClick={() => pick("engine")}>
          <strong>Engine workflow</strong><small>How comments become decisions</small>
        </button>
        <button type="button" role="tab" aria-selected={tab === "notebook"} className={`wtab ${tab === "notebook" ? "is-on" : ""}`} onClick={() => pick("notebook")}>
          <strong>Colab notebook</strong><small>Run it yourself</small>
        </button>
      </div>

      {tab === "notebook" ? <NotebookView /> : (
      <>
      <Section id="steps" eyebrow="How it works" title="Six steps, from comment to decision">
        <ol className="flow">
          {steps(collected, kept, themes, opps).map((s, i) => (
            <li key={s.title} className={`flow__step flow__step--${s.tone}`}>
              <span className="flow__no">{i + 1}</span>
              <h3>{s.title}</h3>
              <p>{s.text}</p>
              <span className="flow__out">{s.out}</span>
            </li>
          ))}
        </ol>
        <div className="flow__end">
          <strong>What the engine produces</strong>
          <span>{kept.toLocaleString("en-IN")} customer comments become:</span>
          <ul className="flow__list">
            <li>{word(themes)} major feedback themes</li>
            <li>Customer insights and unmet needs</li>
            <li>{word(opps)} prioritised product opportunities</li>
            <li>Answers to {word(qs.data?.length ?? 0).toLowerCase()} discovery questions</li>
            <li>Evidence-backed product recommendations</li>
          </ul>
        </div>
      </Section>

      <Section id="questions" eyebrow="What you get" title="Eight questions, answered from the comments" lede="Open any question to see a short answer and the real comments behind it.">
        <Async state={qs}>
          {(items) => (
            <div className="qlist">
              {items.map((q) => (
                <Link key={q.question_id} to={`/ask?q=${q.question_id}`} className="qrow">
                  <span className="qrow__id">{q.question_id}</span>
                  <span className="qrow__text">{q.question}</span>
                  <Chip tone={STRENGTH_TONE[q.evidence_strength] ?? "plain"}>{q.evidence_strength} evidence</Chip>
                </Link>
              ))}
            </div>
          )}
        </Async>
      </Section>
      </>
      )}
    </>
  );
}
