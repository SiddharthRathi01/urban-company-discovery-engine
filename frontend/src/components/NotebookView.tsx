import { useEffect, useState } from "react";
import project from "../project.json";
import MiniMarkdown from "./MiniMarkdown";

interface Cell { type: "markdown" | "code"; source: string; title?: string; note?: string }
interface Notebook { title: string; file: string; reviews: number; cells: Cell[] }

const BASE = "/notebook/Urban_Company_Discovery_Engine";
const COLAB = `https://colab.research.google.com/github/${project.github_repo}/blob/main/${project.notebook_path}`;

function codeTitle(src: string) {
  const first = src.trim().split("\n")[0];
  const t = /^#@title\s+(.*?)(?:\s*\{.*)?$/.exec(first);
  if (t) return t[1];
  return first.startsWith("#") ? first.replace(/^#+\s*/, "") : first.slice(0, 70);
}

/** The Colab notebook of the engine: how to run it, and a read-only view of every cell. */
export default function NotebookView() {
  const [nb, setNb] = useState<Notebook | null>(null);
  const [err, setErr] = useState(false);
  useEffect(() => {
    fetch(`${BASE}_view.json`).then((r) => (r.ok ? r.json() : Promise.reject())).then(setNb).catch(() => setErr(true));
  }, []);
  const nCode = nb?.cells.filter((c) => c.type === "code").length ?? 0;
  return (
    <div className="nb">
      <div className="nb__hero">
        <div>
          <span className="nb__tag">Runnable notebook</span>
          <h3>Run the engine yourself in Google Colab</h3>
          <p>The same engine as a notebook. It runs on the {nb ? nb.reviews.toLocaleString("en-IN") : "2,527"} reviews stored inside it, so nothing needs to be uploaded, and it needs no API keys. You can also run it on your own CSV.</p>
        </div>
        <div className="nb__actions">
          <a className="btn btn--primary" href={COLAB} target="_blank" rel="noopener noreferrer">▶ Open in Google Colab</a>
          <a className="btn" href={`${BASE}.ipynb`} download>⬇ Download</a>
          <a className="btn" href={`${BASE}.md`} target="_blank" rel="noopener noreferrer">Read as text ↗</a>
        </div>
      </div>

      <h3 className="nb__h">Inside the notebook{nb ? <small>{nb.cells.length} cells · {nCode} code</small> : null}</h3>
      {err && <p className="gcard__sub">The notebook preview could not be loaded. You can still download the file above.</p>}
      {!nb && !err && <p className="gcard__sub">Loading the notebook…</p>}
      {nb && (
        <div className="nb__cells">
          {nb.cells.map((c, i) =>
            c.type === "markdown" ? (
              <div className="nbmd" key={i}><MiniMarkdown source={c.source} /></div>
            ) : (
              <details className="nbcode" key={i}>
                <summary><span className="nbcode__tag">Code</span><span className="nbcode__t">{c.title || codeTitle(c.source)}</span>{c.note && <em>{c.note}</em>}</summary>
                <pre><code>{c.source}</code></pre>
              </details>
            ),
          )}
        </div>
      )}
    </div>
  );
}
