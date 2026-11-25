import type { ReactNode } from "react";

/** A small Markdown renderer for the notebook viewer: headings, quotes, tables, lists, bold, italic and inline code. No HTML is ever injected. */
function inline(s: string): ReactNode[] {
  return s.split(/(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)/g).filter(Boolean).map((p, i) => {
    if (p.startsWith("**")) return <strong key={i}>{p.slice(2, -2)}</strong>;
    if (p.startsWith("`")) return <code key={i}>{p.slice(1, -1)}</code>;
    if (p.startsWith("*") && p.endsWith("*") && p.length > 2) return <em key={i}>{p.slice(1, -1)}</em>;
    return <span key={i}>{p}</span>;
  });
}

function cells(row: string) { return row.trim().replace(/^\||\|$/g, "").split("|").map((c) => c.trim()); }

export default function MiniMarkdown({ source }: { source: string }) {
  const out: ReactNode[] = [];
  const lines = source.replace(/\r/g, "").split("\n");
  let para: string[] = [];
  let k = 0;
  const flush = () => { if (para.length) { out.push(<p key={k++}>{inline(para.join(" "))}</p>); para = []; } };
  for (let i = 0; i < lines.length; i++) {
    const ln = lines[i];
    if (!ln.trim()) { flush(); continue; }
    if (ln.trim().startsWith("|")) {
      flush();
      const rows: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith("|")) rows.push(lines[i++]);
      i--;
      const head = cells(rows[0]);
      const body = rows.slice(2).map(cells);
      out.push(
        <div className="mdtbl" key={k++}><table><thead><tr>{head.map((h, j) => <th key={j}>{inline(h)}</th>)}</tr></thead>
          <tbody>{body.map((r, j) => <tr key={j}>{r.map((c, x) => <td key={x}>{inline(c)}</td>)}</tr>)}</tbody></table></div>,
      );
      continue;
    }
    if (ln.startsWith(">")) {
      flush();
      const q: string[] = [];
      while (i < lines.length && lines[i].startsWith(">")) q.push(lines[i++].replace(/^>\s?/, ""));
      i--;
      out.push(<blockquote key={k++}><MiniMarkdown source={q.join("\n")} /></blockquote>);
      continue;
    }
    const h = /^(#{1,3})\s+(.*)$/.exec(ln);
    if (h) {
      flush();
      const L = h[1].length;
      out.push(L === 1 ? <h2 key={k++}>{inline(h[2])}</h2> : L === 2 ? <h3 key={k++}>{inline(h[2])}</h3> : <h4 key={k++}>{inline(h[2])}</h4>);
      continue;
    }
    if (/^[-*]\s+/.test(ln)) {
      flush();
      const items: string[] = [];
      while (i < lines.length && /^[-*]\s+/.test(lines[i])) items.push(lines[i++].replace(/^[-*]\s+/, ""));
      i--;
      out.push(<ul key={k++}>{items.map((t, j) => <li key={j}>{inline(t)}</li>)}</ul>);
      continue;
    }
    para.push(ln.trim());
  }
  flush();
  return <>{out}</>;
}
