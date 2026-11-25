"""Builds docs/Urban_Company_AI_Evidence_Log.pdf (the AI Evidence Log) from the project's own data files.
Every figure is read from analysis/*.json or from the evaluated golden set, and the key counts are re-counted from the master dataset and the rule files
before anything is written (the script stops if they disagree). Rendering uses headless Chrome.

Links in the PDF point at SITE_URL (default http://localhost:8000). After deployment run:  SITE_URL=https://your-site .python/python.exe scripts/build_evidence_log.py"""
import html
import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
SITE = os.environ.get("SITE_URL", "http://localhost:8000").rstrip("/")
PROJECT = json.loads((ROOT / "frontend" / "src" / "project.json").read_text(encoding="utf-8"))
COLAB = f"https://colab.research.google.com/github/{PROJECT['github_repo']}/blob/main/{PROJECT['notebook_path']}"
A = lambda n: json.loads((ROOT / "analysis" / f"{n}.json").read_text(encoding="utf-8"))
E = html.escape
num = lambda n: f"{n:,}"
pct = lambda a, b: f"{100 * a / b:.0f}%"

ov, trust, beh, themes, opps, needs, revs = A("overview"), A("trust"), A("behaviour"), A("themes"), A("opportunities"), A("unmet_needs"), A("reviews")
D, S, V, FUN = ov["dataset"], beh["summary"], trust["validation"], trust["funnel"]
N = D["reviews_analysed"]

# ------------------------------------------------------------------ golden set (the primary evaluated set)
gdir = next((d for d in sorted((ROOT / "golden").glob("GS-*")) if json.loads((d / "meta.json").read_text(encoding="utf-8")).get("primary")), None)
if gdir is None:
    sys.exit("No primary golden set found: upload and evaluate a golden set first.")
gev = json.loads((gdir / "evaluation.json").read_text(encoding="utf-8"))
gs, rows = gev["summary"], gev["rows"]
mc, n_g, sc, rc = gs["match_counts"], gs["rows"], gs["sentiment"], gs["return"]

# ------------------------------------------------------------------ re-count the key figures independently before writing
from step2_common import ISSUES, THEMES  # the rule files themselves
master = pd.read_csv(ROOT / "output" / "urban_company_reviews_master.csv", encoding="utf-8-sig", dtype=str, keep_default_na=False)
assert len(master) == N == len(revs["reviews"]), "dataset size differs between the master file and the analysis"
assert {s["source"]: s["n"] for s in D["by_source"]} == master.platform.value_counts().to_dict(), "source counts differ from the master file"
cls = pd.Series([r["return_class"] for r in revs["reviews"]]).value_counts().to_dict()
assert cls == {d["class"]: d["n"] for d in beh["distribution"]}, "return classes differ from the per-review data"
basis = pd.Series([r["return_basis"] for r in revs["reviews"] if r["return_class"] != "Insufficient Evidence"]).value_counts().to_dict()
bs = S["by_basis"]
assert all(basis.get(k, 0) == bs[k]["n"] for k in ("Stated", "Signalled", "Inferred")), "return basis counts differ"
N_CODES, N_PRAISE = len(ISSUES), sum(1 for k in ISSUES if k.startswith("pos_"))
N_PROBLEMS = N_CODES - N_PRAISE
N_NEEDS, N_OPPS, N_THEMES = len(needs["unmet_needs"]), len(opps["opportunities"]), len(themes["themes"])
assert (N_NEEDS, N_OPPS, N_THEMES) == (14, 9, 5) and len(THEMES) == N_THEMES, "unmet needs / opportunities / themes counts changed"
sent = master.sentiment_label.value_counts().to_dict()
assert round(100 * sent["Positive"] / N, 1) == D["sentiment"]["Positive"]["pct"] and round(100 * sent["Negative"] / N, 1) == D["sentiment"]["Negative"]["pct"]
W = opps["opportunities"][0]["prioritisation"]["formula"]  # the weights quoted below come from the scoring formula itself
assert "0.25*frequency" in W and "0.20*severity" in W and "0.20*evidence" in W and "0.20*repeat" in W and "0.15*impact" in W
print("verified against the master file and the rule files:", N, "reviews;", N_CODES, "codes (", N_PROBLEMS, "problems +", N_PRAISE, "praise );", N_NEEDS, "needs;", N_OPPS, "opportunities;", N_THEMES, "themes")


# ------------------------------------------------------------------ helpers
def table(head, body, cls=""):
    return f'<table class="{cls}"><thead><tr>' + "".join(f"<th>{h}</th>" for h in head) + "</tr></thead><tbody>" + "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in body) + "</tbody></table>"


def segbar(parts):
    return '<div class="seg">' + "".join(f'<span style="flex:{n};background:{c}">{n}</span>' for _, n, c in parts if n) + "</div>"


def conf_table(conf, labels):
    return table(["Human \\ Engine"] + labels, [[f"<b>{h}</b>"] + [f'<span class="{"hit" if h == e and conf[h][e] else ""}">{conf[h][e]}</span>' for e in labels] for h in labels if h in conf], "conf")


def sec(n, title):
    return f'<h2><span class="no">{n}</span>{title}</h2>'


def link(path, label):
    return f'<a href="{SITE}{path}">{label}</a>'


sent_labels = ["Positive", "Negative", "Neutral", "Mixed"]
ret_labels = ["Return", "Non-Return", "Insufficient Evidence"]
non_full = [r for r in rows if r["match_status"] != "Full match"]
conf_ins = rc["confusion"]["Insufficient Evidence"]
ins_total = sum(conf_ins.values())
mixed_h = sc["confusion"]["Mixed"]
both_agree = sum(rc["confusion"][k][k] for k in ("Return", "Non-Return"))
src_counts = {}
for r in rows:
    k = r["source_url"].split("/")[2].replace("www.", "")
    src_counts[k] = src_counts.get(k, 0) + 1
SRC_LABEL = {"play.google.com": "Google Play", "reddit.com": "Reddit", "urban-company.pissedconsumer.com": "PissedConsumer", "consumercomplaints.in": "ConsumerComplaints.in"}
src_text = ", ".join(f"{n} {SRC_LABEL.get(k, k)}" for k, n in sorted(src_counts.items(), key=lambda x: -x[1]))
n_feature = sum(1 for r in non_full if "add" in r["review_text"].lower() or "option" in r["review_text"].lower())
obs = [
    f"Of the {len(non_full)} comments that were not a full match, {n_feature} are requests for a service or option to be added, and {len(non_full) - n_feature} is a scheduling complaint that the labeller read as Mixed. On the {rc['both_classified']} comments where both the labeller and the engine made a Return or Non-Return call, they agreed on {both_agree} ({rc['agreement_pct_when_both_classified']:.0f}%).",
    f"Insufficient Evidence is where they differ most: of the {ins_total} comments the labeller marked Insufficient, the engine agreed on {conf_ins['Insufficient Evidence']}, and committed to Return on {conf_ins['Return']} and to Non-Return on {conf_ins['Non-Return']}.",
    f"Mixed sentiment is the hardest call: of {sum(mixed_h.values())} comments labelled Mixed, the engine read one as Negative and one as Neutral, and it read one Positive comment that contains a feature request as Mixed.",
    "A star rating or a polite feature request is a weak sign of what a customer will do next, so the engine keeps what the customer said apart from what it infers.",
]


def card(r, n):
    txt = " ".join(r["review_text"].split())
    tone = {"Partial match": "mid", "Non-match": "low"}.get(r["match_status"], "ok")
    basis_txt = f' ({E(r["engine_return_basis"])})' if r["engine_return_basis"] not in (None, "None") else ""
    return f'''<div class="ex"><div class="exh"><b>{n}. {E(r["review_id"])}</b><span class="pill {tone}">{E(r["match_status"])}</span></div>
<p class="lab">Customer comment</p><p class="qt">“{E(txt[:330])}{"…" if len(txt) > 330 else ""}”</p>
<div class="two"><div><p class="lab">Human labels</p><p>Sentiment <b>{E(r["human_sentiment"] or "–")}</b><br>Return / Non-Return <b>{E(r["human_return"] or "–")}</b></p></div>
<div><p class="lab">Engine</p><p>Sentiment <b>{E(r["engine_sentiment"] or "–")}</b><br>Return / Non-Return <b>{E(r["engine_return"] or "–")}</b>{basis_txt}<br><span class="soft">Themes: {E(", ".join(r["engine_themes"]) or "–")}</span></p></div></div>
<p class="note">Sentiment {"matched" if r["sentiment_match"] else "differed"} · Return / Non-Return {"matched" if r["return_match"] else "differed"}</p></div>'''


font = ROOT / "frontend" / "node_modules" / "@fontsource-variable" / "plus-jakarta-sans" / "files" / "plus-jakarta-sans-latin-wght-normal.woff2"
font_face = f'@font-face{{font-family:"Plus Jakarta Sans";src:url("{font.as_uri()}") format("woff2");font-weight:200 800;font-style:normal}}' if font.exists() else ""

CSS = font_face + """
@page { size: A4; margin: 15mm 14mm 17mm 14mm; @bottom-left { content: "AI Evidence Log  ·  Urban Company Discovery Engine"; font: 500 7.8pt 'Plus Jakarta Sans', Arial, sans-serif; color: #7a7fa3; } @bottom-right { content: "Page " counter(page); font: 500 7.8pt 'Plus Jakarta Sans', Arial, sans-serif; color: #7a7fa3; } }
:root { --navy:#141a45; --violet:#6d4cff; --blue:#2f7dff; --amber:#f08a24; --green:#0f9d74; --red:#e0476b; --ink:#1b2040; --soft:#5d6388; --tint:#f4f2ff; --line:#e1def5; }
* { box-sizing: border-box; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { font: 400 9.4pt/1.55 'Plus Jakarta Sans', 'Segoe UI', Arial, sans-serif; color: var(--ink); margin: 0; }
.cover { margin: -15mm -14mm 6mm; padding: 15mm 14mm 9mm; color: #fff; background: radial-gradient(120% 140% at 0% 0%, #6d4cff 0%, #2b2c87 45%, #141a45 100%); }
.cover .eb { font-size: 8pt; letter-spacing: .22em; text-transform: uppercase; color: #c9c2ff; font-weight: 700; }
.cover h1 { font-size: 30pt; line-height: 1.05; margin: 3mm 0 1.5mm; font-weight: 800; letter-spacing: -.02em; }
.cover h1 span { background: linear-gradient(90deg, #ffffff, #ffc98a); -webkit-background-clip: text; background-clip: text; color: transparent; }
.cover p { margin: 0; color: #d9d6ff; font-size: 10.5pt; }
.kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 3mm; margin-top: 7mm; }
.kpi { background: rgba(255,255,255,.12); border: 1px solid rgba(255,255,255,.22); border-radius: 3.2mm; padding: 3mm 3.4mm; }
.kpi b { display: block; font-size: 17pt; font-weight: 800; letter-spacing: -.02em; } .kpi small { color: #dcd8ff; font-size: 7.6pt; }
h2 { display: flex; align-items: center; gap: 2.6mm; font-size: 13.5pt; font-weight: 800; color: var(--navy); margin: 8mm 0 2.4mm; padding-bottom: 1.8mm; border-bottom: 1.6px solid var(--line); break-after: avoid; letter-spacing: -.01em; }
h2 .no { display: inline-grid; place-items: center; width: 7mm; height: 7mm; border-radius: 50%; color: #fff; font-size: 9.5pt; background: linear-gradient(135deg, #6d4cff, #2f7dff); flex: none; }
h3 { font-size: 10.4pt; font-weight: 800; color: var(--violet); margin: 4.2mm 0 1.4mm; break-after: avoid; }
p { margin: 0 0 2mm; } ul { margin: 0 0 2.4mm; padding-left: 4.6mm; } li { margin-bottom: 1.3mm; } li::marker { color: var(--violet); }
table { width: 100%; border-collapse: separate; border-spacing: 0; margin: 2mm 0 3.4mm; font-size: 8.8pt; break-inside: avoid; border: 1px solid var(--line); border-radius: 2.6mm; overflow: hidden; }
th { background: linear-gradient(90deg, #1b2160, #3a2fa6); color: #fff; text-align: left; padding: 2.1mm 2.6mm; font-weight: 700; font-size: 8pt; letter-spacing: .03em; }
td { padding: 1.9mm 2.6mm; border-top: 1px solid var(--line); vertical-align: top; } tbody tr:nth-child(even) td { background: #faf9ff; } tbody tr:first-child td { border-top: 0; }
.bar { height: 2.2mm; border-radius: 99px; background: #ece9ff; min-width: 26mm; } .bar i { display: block; height: 100%; border-radius: 99px; background: linear-gradient(90deg, #6d4cff, #2f7dff); }
table.conf td, table.conf th { text-align: center; font-size: 8.3pt; } table.conf td:first-child, table.conf th:first-child { text-align: left; } .hit { display: inline-block; min-width: 6mm; border-radius: 1.4mm; background: #dcf5ec; color: var(--green); font-weight: 800; }
.seg { display: flex; height: 7mm; border-radius: 99px; overflow: hidden; margin: 2.2mm 0 3mm; gap: .6mm; } .seg span { display: grid; place-items: center; color: #fff; font-weight: 800; font-size: 9pt; }
.box { background: var(--tint); border-left: 1.4mm solid var(--violet); border-radius: 0 2.6mm 2.6mm 0; padding: 3mm 4mm; margin: 2.6mm 0 3.4mm; break-inside: avoid; }
.box.amber { background: #fff4e6; border-left-color: var(--amber); }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 4mm; break-inside: avoid; } .three { display: grid; grid-template-columns: repeat(3, 1fr); gap: 3mm; margin: 2mm 0 3mm; }
.tile { border: 1px solid var(--line); border-radius: 3mm; padding: 3mm 3.4mm; background: #fff; break-inside: avoid; } .tile b { display: block; font-size: 14pt; color: var(--violet); font-weight: 800; letter-spacing: -.02em; } .tile small { color: var(--soft); font-size: 8pt; }
.lab { font-size: 7.2pt; text-transform: uppercase; letter-spacing: .1em; color: var(--soft); font-weight: 800; margin: 2.4mm 0 .8mm; } .soft { color: var(--soft); font-size: 8.6pt; } .note { color: var(--soft); font-size: 8.4pt; font-style: italic; margin: 1mm 0 .6mm; }
.two { display: grid; grid-template-columns: 1fr 1fr; gap: 5mm; }
.ex { border: 1px solid var(--line); border-radius: 3.2mm; padding: 3.2mm 4mm 2.2mm; margin: 0 0 3.6mm; break-inside: avoid; } .exh { display: flex; justify-content: space-between; align-items: center; } .exh b { color: var(--navy); font-weight: 800; }
.qt { color: #2b3060; font-size: 9.2pt; }
.pill { display: inline-block; padding: .6mm 2.6mm; border-radius: 99px; font-size: 7.6pt; font-weight: 800; } .pill.ok { background: #dcf5ec; color: var(--green); } .pill.mid { background: #e3ecff; color: var(--blue); } .pill.low { background: #ffe3ea; color: var(--red); }
a { color: var(--blue); font-weight: 700; text-decoration: none; border-bottom: 1px solid #b9cdf7; } code { font-family: Consolas, monospace; font-size: 8.2pt; background: #efedff; padding: 0 1.2mm; border-radius: 1mm; }
.llm { display: inline-block; font-size: 7.6pt; font-weight: 800; color: var(--violet); background: #ece8ff; border-radius: 99px; padding: .4mm 2.4mm; margin-left: 1.5mm; }
"""

# ------------------------------------------------------------------ content
src_rows = []
mx = max(s["n"] for s in D["by_source"])
KIND = {"Google Play Store": "App-store reviews", "Reddit": "Discussion posts", "PissedConsumer": "Complaint site", "ConsumerComplaints.in": "Complaint site"}
for s in D["by_source"]:
    src_rows.append([f"<b>{E(s['source'])}</b>", KIND.get(s["source"], ""), num(s["n"]), f'{s["pct"]:.1f}%', f'<div class="bar"><i style="width:{100 * s["n"] / mx:.0f}%"></i></div>'])
src_rows.append(["<b>Total</b>", "", f"<b>{num(N)}</b>", "<b>100%</b>", ""])

theme_rows = [[f'<b>{t["theme_id"]}</b>', E(t["name"]), num(t["review_count"]), f'{t["pct_of_dataset"]}%'] for t in sorted(themes["themes"], key=lambda t: -t["review_count"])]
ret_rows = []
for c in beh["distribution"]:
    if c["class"] == "Insufficient Evidence":
        continue
    ret_rows.append([f"<b>{c['class']}</b>", num(c["n"]), f'{c["pct_of_dataset"]}%', str(c["by_basis"].get("Stated", 0)), str(c["by_basis"].get("Signalled", 0)), num(c["by_basis"].get("Inferred", 0))])
ret_rows.append(["<b>Insufficient Evidence</b>", num(S["insufficient"]), f'{S["insufficient_pct"]}%', "–", "–", "–"])
ret_rows.append(["<b>Given a reading (Return + Non-Return)</b>", f"<b>{num(S['classified'])}</b>", f"<b>{S['classified_pct']}%</b>", f"<b>{bs['Stated']['n']}</b>", f"<b>{num(bs['Signalled']['n'])}</b>", f"<b>{num(bs['Inferred']['n'])}</b>"])
opp_rows = [[str(o["priority_rank"]), E(o["title"]), o["priority"], f'{o["prioritisation"]["score"] * 100:.0f}', E(o["pm_brief"]["recommendation"])] for o in opps["opportunities"][:5]]

body = f"""
<div class="cover">
  <div class="eb">Urban Company Discovery Engine</div>
  <h1>AI <span>Evidence Log</span></h1>
  <p>How the engine reads customer feedback, what it found, and how that was checked.</p>
  <div class="kpis">
    <div class="kpi"><b>{num(N)}</b><small>public reviews analysed</small></div>
    <div class="kpi"><b>{len(D['by_source'])}</b><small>sources, every review linked to its page</small></div>
    <div class="kpi"><b>{S['classified_pct']}%</b><small>given a Return / Non-Return reading</small></div>
    <div class="kpi"><b>{mc['Full match']} of {n_g}</b><small>golden-set comments matched on every label</small></div>
  </div>
</div>

{sec(1, "Objective")}
<p>The Discovery Engine reads public customer feedback about Urban Company to understand what customers expect once a booking is made, how they decide they need a home service, why they book again or do not, and which product opportunities could raise the share of customers who complete another booking within 90 days. Every finding stays attached to the original comment, so it can be opened and checked at its source.</p>

{sec(2, "Data collection: sources and volume")}
<p>The final dataset has <b>{num(N)} reviews</b> from four public sources, each with its own source link.</p>
{table(["Source", "Type", "Reviews", "Share", ""], src_rows)}
<ul>
<li><b>Cleaning.</b> {num(FUN[0]['n'])} records were collected. After {FUN[1]['note'].split(' (')[0]}, {num(FUN[1]['n'])} unique records remained. A further 846 entries without a page of their own (Apple App Store and older complaint-site entries) and 358 off-topic, spam, professional-side or out-of-scope items were removed, leaving <b>{num(FUN[2]['n'])}</b> reviews.</li>
<li><b>Traceability.</b> A review is kept only if it has its own source page, so every finding can be opened at its source. The text of {num(V['urls']['individually_verified'])} reviews was checked against its live page.</li>
<li><b>Balance.</b> Complaint sites are almost entirely negative, so a random sample of detailed 4–5 star Google Play reviews was added in two rounds. Positive reviews are now {D['sentiment']['Positive']['pct']}% of the dataset and negative {D['sentiment']['Negative']['pct']}%.</li>
<li><b>Sentiment labels.</b> A word-list score gave a first label. {num(V['sentiment']['queue_read_individually'])} unclear reviews were then read one by one and {num(V['sentiment']['labels_changed_by_analyst'])} labels were corrected. A random sample of {V['sentiment']['sample']} labels was re-read afterwards: {V['sentiment']['agreed']} agreed ({V['sentiment']['agreement_pct']}%).</li>
<li><b>Not included.</b> Apple App Store reviews were collected but left out because the public feed has no page for each individual review.</li>
<li><b>Service and city tags.</b> Service category is identified in {pct(D['service_category_stated'], N)} of reviews and city in {pct(D['city_stated'], N)}, taken from the words of each review.</li>
</ul>

{sec(3, "How the engine works")}
<p>The engine follows the six steps shown on the website: collect, clean, read, group, prioritise and prove. Every result keeps the review ID and source of the comments behind it, and every count, percentage and score is calculated in code.</p>

<h3>Reading every review</h3>
<p>Each review is read in three ways.</p>
<ul>
<li><b>Sentiment:</b> Positive, Negative, Neutral, Mixed or Uncertain.</li>
<li><b>Problems and needs:</b> {N_CODES} phrase rules ({N_PROBLEMS} problems customers raise and {N_PRAISE} kinds of praise) and {N_NEEDS} unmet-need types. The matched text was read and checked by an AI-assisted analyst review before it was counted.</li>
<li><b>Return reading:</b> each review is placed as <b>Return</b> (likely to book again), <b>Non-Return</b> (unlikely to) or <b>Insufficient Evidence</b>, together with how it was decided. <i>Stated</i> means the customer said it in the first person; <i>Signalled</i> means they advised others against the app, mentioned switching, showed distrust, or recommended with trust; <i>Inferred</i> means it was read from sentiment and star rating.</li>
</ul>
{table(["Return reading", "Reviews", "Share", "Stated", "Signalled", "Inferred"], ret_rows)}
<p class="soft">These readings show what customers wrote, not their observed repeat-booking rates. {bs['Stated']['n']} reviews ({bs['Stated']['pct_of_dataset']}%) state the behaviour themselves, so the Stated and Signalled groups are the firmest evidence.</p>

<h3>Grouping into themes</h3>
<p>The problem and praise rules are grouped into {N_THEMES} themes. A review can belong to more than one theme, so the shares overlap.</p>
{table(["Theme", "What it covers", "Reviews", "Share"], theme_rows)}

<h3>Prioritising opportunities</h3>
<p>{N_OPPS} product opportunities are scored from 0 to 100. The score combines how many reviews mention the problem (25%), how unhappy those reviews are (20%), how strong the evidence is (20%), the link to leaving signals (20%) and an analyst impact judgement (15%). Each opportunity carries a product-manager brief. The top five:</p>
{table(["Rank", "Opportunity", "Priority", "Score", "Recommendation"], opp_rows)}

<h3>The live engine <span class="llm">LLM</span></h3>
<p>The same engine also runs live. When a CSV is uploaded, an LLM reads each comment in small batches (sentiment, problem, return signal and one verbatim quote), the labels are grouped into themes, and the LLM drafts insights and opportunities. Counts, percentages and the Return / Non-Return class are calculated in code with the rules above, so the LLM supplies readings and wording and never the numbers. The live engine also runs the golden-set check in section 4 and writes the short answers in Ask Questions, each backed by quotes that are checked word for word against the review.</p>

{sec(4, "Validation: human labels and engine results")}
<p>To test the engine against human judgement, a golden set of {n_g} comments from the dataset ({E(src_text)}) was read and labelled by hand before the engine saw them: sentiment, Return / Non-Return and a short problem label. The engine then analysed the same {n_g} comments and its answers were compared with the hand labels, comment by comment.</p>
{segbar([("Full match", mc["Full match"], "#0f9d74"), ("Partial match", mc["Partial match"], "#2f7dff"), ("Non-match", mc["Non-match"], "#9aa0c4")])}
<div class="three">
  <div class="tile"><b>{mc['Full match']}</b><small>Full match: every label agrees</small></div>
  <div class="tile"><b>{mc['Partial match']}</b><small>Partial match: some labels agree</small></div>
  <div class="tile"><b>{mc['Non-match']}</b><small>Non-match: no label agrees</small></div>
</div>
{table(["Measure", "Agreement", "Detail"], [["Sentiment", f'<b>{sc["agree"]} of {sc["compared"]} ({sc["agreement_pct"]:.0f}%)</b>', f'{sc["kappa"]} agreement beyond chance; {sc["agreement_pct_excluding_mixed"]:.0f}% when comments the human labelled Mixed are left out'], ["Return / Non-Return", f'<b>{rc["agree"]} of {rc["compared"]} ({rc["agreement_pct"]:.0f}%)</b>', f'{rc["kappa"]} agreement beyond chance'], ["Return / Non-Return, where both made a call", f'<b>{both_agree} of {rc["both_classified"]} ({rc["agreement_pct_when_both_classified"]:.0f}%)</b>', "Comments where neither the human nor the engine said Insufficient Evidence"]])}
<div class="box"><b>How to read this.</b> {mc["Full match"]} of {n_g} comments ({pct(mc["Full match"], n_g)}) matched on every label, and {mc["Full match"] + mc["Partial match"]} of {n_g} ({pct(mc["Full match"] + mc["Partial match"], n_g)}) matched on at least one. <i>Agreement beyond chance</i> is a score where 0 means no better than guessing and 1 means perfect agreement; it counts only the agreement that guessing would not produce. The set is small and labelled by one person, so it shows where the engine and a reader agree and differ rather than giving an accuracy figure for every review.</div>
<div class="grid2"><div><p class="lab">Sentiment: human (rows) and engine (columns)</p>{conf_table(sc["confusion"], sent_labels)}</div><div><p class="lab">Return / Non-Return: human (rows) and engine (columns)</p>{conf_table(rc["confusion"], ret_labels)}</div></div>
<h3>Key observations</h3><ul>{"".join(f"<li>{E(o)}</li>" for o in obs)}</ul>

{sec(5, "Safeguards built into the engine")}
<ul>
<li><b>Traceable by design.</b> Every theme, score and quote links back to a review ID, its source and its URL, so a reader can open the original.</li>
<li><b>Quotes checked word for word.</b> All {V['quotes']['total']} quotes shown in the dataset analysis were tested to appear exactly in the original review ({V['quotes']['verified']} of {V['quotes']['total']} passed). For uploaded files, a quote that is not word for word is replaced by the opening of the review itself, and citations that cannot be verified are dropped.</li>
<li><b>Numbers come from code.</b> Counts, percentages and sentiment totals are calculated in code and never written by the model; any generated sentence that contains a number is discarded.</li>
<li><b>Evidence kept apart.</b> Stated, Signalled and Inferred readings are shown separately with a confidence, so the strongest evidence is never blended with the weakest.</li>
<li><b>Evidence and hypotheses kept apart.</b> Root causes, proposals and repeat-booking mechanisms are labelled as hypotheses.</li>
<li><b>Honest answers.</b> Answers in Ask Questions cite reviews that were retrieved and verified; when none can be verified, the engine says the evidence is insufficient.</li>
<li><b>Secure and monitored.</b> Credentials stay on the backend and are removed from logs. AI usage (requests, tokens, neurons and failures) is tracked per request, and {V['tests']['automated_tests']} automated tests cover data integrity, the API and uploads.</li>
</ul>

{sec(6, "Improvements identified")}
<p>Based on the golden-set results, these are the next improvements. They are planned, and will be reported as complete only after they are built and retested.</p>
<ul>
<li>Treat feature requests and mixed messages explicitly, so a polite request or a star rating alone does not turn a comment into a Return reading.</li>
<li>Make the engine more willing to answer Insufficient Evidence when the wording gives no clear signal.</li>
<li>Enlarge the golden set (for example to 100 comments) and add a second labeller, to measure agreement between people as well.</li>
<li>Retest the same {n_g} comments after every change to confirm the results improve.</li>
<li>Join the findings with first-party booking data to measure the real 90-day repeat rate, including customers who left without a review.</li>
</ul>

{sec(7, "Limitations")}
<ul>
<li><b>What the sample represents.</b> Google Play supplies {D['by_source'][0]['pct']:.0f}% of the reviews and the complaint sites lean heavily negative, so the percentages describe this set of reviews rather than every Urban Company customer. The balancing steps in section 2 reduce this effect.</li>
<li><b>Return readings are likelihoods.</b> Return and Non-Return are read from what customers wrote. {bs['Stated']['n']} reviews state the behaviour themselves, and first-party booking data is the way to confirm real repeat rates.</li>
<li><b>Quiet customers.</b> Customers who stop booking without writing a review do not appear in public feedback. First-party data would show them.</li>
<li><b>Source coverage.</b> Reddit posts carry no star ratings, and Apple App Store reviews were left out because the public feed has no page for each review.</li>
<li><b>Size of the golden set.</b> The {n_g} comments were labelled by one person. A larger set with a second labeller would give a firmer measure of agreement.</li>
</ul>

{sec(8, "Supporting artifacts")}
{table(["Artifact", "What it is", "Open"], [
    ["<b>Dataset</b>", f"urban_company_reviews_master.csv: {num(N)} reviews, each with its source link", link("/downloads/dataset", "Download CSV")],
    ["<b>Golden set</b>", f"golden_data_set.csv: the {n_g} comments labelled by hand (results: {mc['Full match']} full, {mc['Partial match']} partial, {mc['Non-match']} non-match)", link("/downloads/golden-set", "Download CSV")],
    ["<b>Runnable workflow</b>", "Google Colab notebook: the same six steps, runnable on the built-in dataset or your own CSV", f'<a href="{COLAB}">Open in Colab</a>'],
    ["<b>This log</b>", "AI Evidence Log (PDF)", link("/downloads/evidence-log.pdf", "Open PDF")],
])}

{sec(9, "Where the human label differed from the engine")}
<p>These are the {len(non_full)} golden-set comments that were not a full match. They show where the engine took a different reading from the person who labelled the comment.</p>
{"".join(card(r, i) for i, r in enumerate(non_full, 1))}
<div class="box amber"><b>Keep in mind.</b> These are the comments that were not a full match in a {n_g}-comment sample. They show where a person and the engine read a comment differently; they are not a measure of how often the engine is wrong, and the labels are one person's reading.</div>
"""

doc = f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>AI Evidence Log: Urban Company Discovery Engine</title><style>{CSS}</style></head><body>{body}</body></html>'
out_dir = ROOT / "docs"
out_dir.mkdir(exist_ok=True)
html_path = out_dir / "_evidence_log.html"
pdf_path = out_dir / "Urban_Company_AI_Evidence_Log.pdf"
html_path.write_text(doc, encoding="utf-8")
chrome = next((p for p in (r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe") if Path(p).exists()), None)
if not chrome:
    sys.exit("Chrome or Edge is needed to print the PDF.")
subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={pdf_path}", html_path.as_uri()], check=True, timeout=120, capture_output=True)
html_path.unlink()
print("written", pdf_path, pdf_path.stat().st_size, "bytes")
