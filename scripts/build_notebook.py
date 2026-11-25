"""Builds the runnable Colab notebook of the Urban Company Discovery Engine (notebook/Urban_Company_Discovery_Engine.ipynb), a Markdown export of it,
and a light JSON copy for the website's notebook viewer.

The rule code inside the notebook is COPIED from the project's own scripts (issue codes, return/non-return rules, curated labels, sentiment, PM briefs,
opportunity definitions), so the notebook and the website cannot drift apart. The Urban Company dataset (2,527 reviews) is embedded, so 'Run all' works
with nothing to upload and no API keys. Run:  .python/python.exe scripts/build_notebook.py"""
import base64
import gzip
import io
import json
import re
import shutil
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
S = ROOT / "scripts"
OUT = ROOT / "notebook"
OUT.mkdir(exist_ok=True)
NAME = "Urban_Company_Discovery_Engine"


def text(p):
    return Path(p).read_text(encoding="utf-8")


def between(src, start, end=None):
    a = src.index(start)
    b = src.index(end, a) if end else len(src)
    return src[a:b]


def md(s):
    return {"cell_type": "markdown", "metadata": {}, "source": s.strip("\n").splitlines(keepends=True)}


def code(s, **meta):
    return {"cell_type": "code", "execution_count": None, "metadata": meta, "outputs": [], "source": s.strip("\n").splitlines(keepends=True)}


# ------------------------------------------------------------------------------------------------ pieces copied from the project
common = text(S / "step2_common.py")
issue_rules = "import re\nI = re.I\n\n" + between(common, "# ------------------------------------------------------------------ issue codes (multi-label)")

codes2 = text(S / "step2_codes2.py")
codes2 = codes2[codes2.index("import re"):]                       # drop the module docstring
codes2 = codes2[: codes2.index("def classify_return(text):")].rstrip() + "\n"   # the legacy first-pass function is not used; the curated one is

curated = text(S / "step2_curated.py")
curated = curated[curated.index("import re"):].replace("def classify_return(rid, text, sentiment):", "def classify_return_curated(rid, text, sentiment):")

behaviour = text(S / "step2_behaviour.py")
behaviour = behaviour[behaviour.index("import pandas as pd"):].replace("def classify(legacy_class", "def behaviour_classify(legacy_class")

sentiment_src = text(S / "sentiment.py")
sentiment_src = sentiment_src[sentiment_src.index("import re"):]

pm_src = text(S / "pm_briefs.py")
pm_src = pm_src[pm_src.index("PM = {"):]

ba = text(S / "build_analysis.py")
opps_block = between(ba, "OPPS = [", "opps = []").replace("CUR.ER_INTENT", "ER_INTENT").rstrip() + "\n"

# ------------------------------------------------------------------------------------------------ embedded dataset
master = pd.read_csv(ROOT / "output" / "urban_company_reviews_master.csv", encoding="utf-8-sig", dtype=str, keep_default_na=False)
KEEP = ["record_id", "review_title", "review_text", "platform", "source_url", "review_date", "rating", "service_category", "sentiment_label"]
buf = io.StringIO()
master[KEEP].to_csv(buf, index=False)
b64 = base64.b64encode(gzip.compress(buf.getvalue().encode("utf-8"), 9, mtime=0)).decode("ascii")
b64_lines = "\n".join(f'    "{b64[i:i + 120]}"' for i in range(0, len(b64), 120))
N_MASTER = len(master)

cells = []
cells.append(md(f"""
# Urban Company Discovery Engine, in a notebook

**Press Runtime → Run all** (Ctrl+F9). The notebook opens with the **{N_MASTER:,} public Urban Company reviews** already inside it, so there is nothing to upload and nothing to set up.
To try the engine on **your own comments**, change `DATA_SOURCE` in Step 1 to *Upload my own CSV* and run all again.

It is the same six-step workflow you see on the website, written out so you can read and change every rule:

| Step | What the engine does | Result |
|---|---|---|
| **1 · Collect** | Loads the reviews and finds the columns | A tidy table of comments |
| **2 · Clean** | Removes empty rows and true duplicates | One row per customer comment |
| **3 · Read** | Reads sentiment, the problem raised and a return signal | Feeling, problem, Return / Non-Return |
| **4 · Group** | Groups problems and unmet needs into five themes | Recurring patterns, not one-off complaints |
| **5 · Prioritise** | Scores nine product opportunities | A ranked list with a PM brief for each |
| **6 · Prove** | Checks the evidence and builds the report | An HTML report plus two CSV files |

"""))
cells.append(md("""
## Step 1 · Collect
Choose where the comments come from. The default is the built-in Urban Company dataset; pick *Upload my own CSV* to use your own file.
"""))
cells.append(code(r'''
import re, math, time, html, os, io, sys, json, gzip, base64, subprocess
from collections import Counter
import pandas as pd

# ---- Run settings ----
DATA_SOURCE = "Use preloaded Urban Company dataset"  #@param ["Use preloaded Urban Company dataset", "Upload my own CSV"]
CSV_PATH = ""            # optional: path to a CSV already in this Colab session (overrides DATA_SOURCE)
TEXT_COLUMN = ""         # leave empty to auto-detect the review text column
OUTPUT_DIR = "discovery_output"

STAGES = []
def stage(k, title, fn, io_, t0, note=None):
    s = {"k": k, "title": title, "fn": fn, "io": io_, "ms": int((time.time() - t0) * 1000)}
    if note: s["note"] = note
    STAGES.append(s)
'''))
cells.append(md(f"""
### The built-in dataset
The Urban Company review file ({N_MASTER:,} public reviews from Google Play, Reddit and two complaint sites, each with its own source link) is stored inside this notebook, so *Run all* works with no upload. Nothing to edit in the next cell.
"""))
cells.append(code(f'''
#@title Preloaded Urban Company dataset (do not edit) {{ display-mode: "form" }}
PRELOADED_NAME = "urban_company_reviews_master.csv"
PRELOADED_CSV_B64 = (
{b64_lines}
)
'''))
cells.append(md("### Load the file"))
cells.append(code(r'''
t0 = time.time()
try:
    from google.colab import files as colab_files
    IN_COLAB = True
except ImportError:
    IN_COLAB = False

if CSV_PATH:
    path = CSV_PATH
    print(f"Using CSV_PATH: {path}")
elif DATA_SOURCE.lower().startswith("upload"):
    if not IN_COLAB: raise RuntimeError("Upload is only available in Colab. Set CSV_PATH to your CSV file instead.")
    print("Choose your reviews CSV file...")
    uploaded = colab_files.upload()
    if not uploaded: raise RuntimeError("No CSV file received. Upload a file, or set DATA_SOURCE to the preloaded dataset.")
    path = next(iter(uploaded))
else:
    path = PRELOADED_NAME
    with open(path, "wb") as f: f.write(gzip.decompress(base64.b64decode(PRELOADED_CSV_B64)))
    print("Using the preloaded Urban Company dataset. To analyse your own CSV, set DATA_SOURCE to 'Upload my own CSV' and run all again.")

raw = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig", engine="python", index_col=False).reset_index(drop=True)
headers = [h.strip() for h in raw.columns]
raw.columns = headers
if not headers or not len(raw): raise ValueError("The CSV has a header but no data rows.")
FILE_NAME = os.path.basename(path)
USING_PRELOADED = (path == PRELOADED_NAME) and not CSV_PATH
stage("ingest", "Collect: load the file", "read_csv()", f"{len(raw)} rows × {len(headers)} cols", t0)
print(f"Loaded {FILE_NAME}: {len(raw)} rows, columns: {headers}")
'''))
cells.append(md("""
### Find the columns
Finds the review text column and the optional columns (title, source, rating, date, link, service category, an existing sentiment label). Only a text column is required.
"""))
cells.append(code(r'''
t0 = time.time()
FIELD_RULES = {
    "id": [r"^(record[_ ]?id|review[_ ]?id|id|#|row)$", r"record|review_?id|\bid\b"],
    "title": [r"^(review[_ ]?title|title|headline|subject)$"],
    "text": [r"^(review[_ ]?text|text|review|comment|content|body|feedback|verbatim)$", r"review|comment|content|body|feedback|verbatim|text"],
    "platform": [r"^(platform|source|source[_ ]?platform|channel|store)$", r"source|platform|channel|store"],
    "rating": [r"^(rating|stars|score)$", r"rating|stars"],
    "date": [r"^(review[_ ]?date|date)$", r"date|time"],
    "url": [r"^source[_ ]?url$", r"url|link"],
    "category": [r"^(service[_ ]?category|category)$", r"category|service"],
    "sentiment": [r"^(sentiment[_ ]?label|sentiment)$"],
}
ORDER = ["text", "platform", "id", "title", "rating", "date", "url", "category", "sentiment"]

def auto_map(headers, data):
    m, used = {}, set()
    for f in ORDER:
        hit = None
        for rule in FIELD_RULES[f]:
            for h in headers:
                if h in used or not re.search(rule, h, re.I): continue
                if f == "text" and re.search(r"url|title|insight|variant", h, re.I): continue
                hit = h; break
            if hit: break
        if hit: m[f] = hit; used.add(hit)
    if "text" not in m:  # fallback: the column with the longest average text
        best, bl = None, 0
        for h in headers:
            l = data[h].head(200).str.len().mean()
            if l > bl and h not in used: bl, best = l, h
        if best: m["text"] = best
    return m

MAP = auto_map(headers, raw)
if TEXT_COLUMN:
    if TEXT_COLUMN not in headers: raise ValueError(f'Column "{TEXT_COLUMN}" is not in the CSV. Columns found: {headers}')
    MAP["text"] = TEXT_COLUMN
if "text" not in MAP: raise ValueError(f"Could not find a review text column. Set TEXT_COLUMN. Columns found: {headers}")
stage("map", "Collect: find the columns", "auto_map()", f"{len(MAP)} fields mapped", t0)
print("Column mapping:", MAP)
'''))
cells.append(md("""
## Step 2 · Clean
Empty rows are dropped. A comment counts as a duplicate only when the text, the place and the day are all the same, because short reviews such as "good app" are often different people.
"""))
cells.append(code(r'''
t0 = time.time()
def col(f, default=""):
    return raw[MAP[f]].astype(str).str.strip() if f in MAP else pd.Series([default] * len(raw), index=raw.index)

df = pd.DataFrame({
    "record_id": col("id"), "review_title": col("title"), "review_text": col("text"),
    "platform": col("platform", "Unknown source"), "source_url": col("url"), "review_date": col("date"),
    "rating": col("rating"), "service_category": col("category"), "sentiment_label": col("sentiment"),
})
df.loc[df.record_id == "", "record_id"] = [f"ROW-{i + 1:05d}" for i in df.index[df.record_id == ""]]
df.loc[df.platform == "", "platform"] = "Unknown source"
df["rating_f"] = pd.to_numeric(df.rating, errors="coerce")
df["text"] = (df.review_title + " " + df.review_text).str.replace(r"\s+", " ", regex=True).str.strip()
df = df[df.text.str.len() >= 1].reset_index(drop=True)
before = len(df)
# a duplicate is the same text from the same place on the same day (short reviews such as "good app" are often genuinely different people)
key = (df.text.str.lower().str.replace(r"[^a-z0-9ऀ-ॿ ]+", " ", regex=True).str.replace(r"\s+", " ", regex=True).str.strip()
       + "|" + df.platform + "|" + df.source_url + "|" + df.review_date)
df = df[~key.duplicated()].reset_index(drop=True)
dups = before - len(df)
N = len(df)
stage("clean", "Clean", "drop empty and duplicate rows", f"{len(raw)} → {N} rows", t0, f"{dups} exact duplicates removed")
print(f"{N} reviews after cleaning ({dups} duplicates removed)")
'''))
cells.append(md("""
## Step 3 · Read
Every comment is read three ways: how the customer feels, what problem they raise, and whether their words point to coming back.

### Sentiment
The built-in dataset already carries sentiment labels that were read by an analyst. For your own CSV, a transparent text lexicon (VADER plus home-services terms) labels every review as Positive, Negative, Neutral, Mixed or Uncertain. The star rating is used only as a tie-breaker when the words carry no feeling.
"""))
cells.append(code("""
#@title Sentiment word list  { display-mode: "form" }
try:
    import vaderSentiment
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "vaderSentiment"])
""" + sentiment_src))
cells.append(code(r'''
t0 = time.time()
VALID = {"Positive", "Negative", "Neutral", "Mixed", "Uncertain"}
have = df.sentiment_label.isin(VALID)
if have.all():
    sent_method = "labels supplied in the file (analyst-read for the preloaded dataset)"
else:
    todo = df.index[~have]
    res = [label(df.at[i, "review_title"], df.at[i, "review_text"], df.at[i, "rating_f"] if not pd.isna(df.at[i, "rating_f"]) else None) for i in todo]
    df.loc[todo, "sentiment_label"] = [x[0] for x in res]
    sent_method = f"text lexicon for {len(todo)} reviews" + (f", file labels for {int(have.sum())}" if have.any() else "")
sc = df.sentiment_label.value_counts()
stage("sentiment", "Read: sentiment", "label()", " · ".join(f"{k} {v}" for k, v in sc.items()), t0, sent_method)
print(sent_method); print(sc.to_dict())
'''))
cells.append(md("""
### The problem the customer raises
Phrase rules flag **26 codes**: 22 problems customers raise and 4 kinds of praise (a review can have several). Fourteen **unmet-need** types are flagged separately. The rules are written out below; edit them to fit your own product.
"""))
cells.append(code("#@title Problem and theme rules  { display-mode: \"form\" }\n" + issue_rules))
cells.append(code("#@title Unmet-need and return-signal rules  { display-mode: \"form\" }\n" + codes2))
cells.append(code(r'''
t0 = time.time()
df = tag_issues(df)
for k, rx in NEED_RE.items():
    df["nd_" + k] = df.text.map(lambda t, rx=rx: bool(rx.search(t)))
flagged = int(df[[c for c in df.columns if c.startswith("i_")]].any(axis=1).sum())
stage("problems", "Read: problems and needs", "tag_issues()", f"{flagged} of {len(df)} reviews raise at least one coded problem or praise", t0,
      f"{len(ISSUES)} problem and praise codes · {len(NEEDS)} need types")
print(f"{flagged} of {len(df)} reviews match at least one problem or praise code")
'''))
cells.append(md("""
### Return / Non-Return
Every review is placed as **Return** (likely to book again), **Non-Return** (unlikely to) or **Insufficient Evidence**, together with *how* that was decided:
**Stated** (said in the first person), **Signalled** (advises others against the app, mentions switching, distrust, or recommends with trust) or **Inferred** (sentiment and star rating). These are **predictions from public text, not observed repeat bookings**.
For the preloaded dataset the analyst-read labels are used where they exist; for your own CSV the phrase rules and the sentiment decide.
"""))
cells.append(code("#@title Hand-checked labels for the built-in dataset  { display-mode: \"form\" }\n" + curated))
cells.append(code("#@title Return / Non-Return decision rules  { display-mode: \"form\" }\n" + behaviour))
cells.append(code(r'''
t0 = time.time()
first = [classify_return_curated(r.record_id, r.text, r.sentiment_label) for r in df.itertuples()]
final = [behaviour_classify(a, s, r.sentiment_label, r.rating_f) for (a, s), r in zip(first, df.itertuples())]
df["return_class"] = [x[0] for x in final]
df["return_basis"] = [x[1] for x in final]
df["return_confidence"] = [x[2] for x in final]
df["return_reason"] = [x[3] for x in final]
rcn = df.return_class.value_counts()
classified = int(rcn.get("Return", 0) + rcn.get("Non-Return", 0))
stage("return", "Read: return signal", "behaviour_classify()", f"{rcn.get('Return', 0)} Return · {rcn.get('Non-Return', 0)} Non-Return · {rcn.get('Insufficient Evidence', 0)} insufficient", t0,
      f"{100 * classified / N:.1f}% of reviews classified")
print(rcn.to_dict(), f"({100 * classified / N:.1f}% classified)")
print(pd.crosstab(df.return_class, df.return_basis))
'''))
cells.append(md("""
## Step 4 · Group
The problem codes are grouped into **five themes**, so recurring patterns stand out from one-off complaints. A review can belong to more than one theme, so the shares overlap.
"""))
cells.append(code(r'''
t0 = time.time()
th_n = {t: int(df["th_" + t].sum()) for t in THEMES}
need_n = {k: int(df["nd_" + k].sum()) for k in NEEDS}
theme_table = pd.DataFrame([dict(theme=t, name=THEMES[t][0], reviews=th_n[t], share=f"{100 * th_n[t] / N:.1f}%",
                                 negative=f"{100 * (df.loc[df['th_' + t], 'sentiment_label'] == 'Negative').mean():.0f}%") for t in THEMES]).sort_values("reviews", ascending=False)
stage("themes", "Group into themes", "THEMES", f"{len(THEMES)} themes", t0, "; ".join(f"{t} {n}" for t, n in th_n.items()))
print("Most frequent unmet needs:", ", ".join(f"{k.split(' (')[0]} ({v})" for k, v in sorted(need_n.items(), key=lambda kv: -kv[1])[:4]))
theme_table
'''))
cells.append(md("""
## Step 5 · Prioritise
Nine product opportunities are defined from the problems and needs above. Score (0 to 1) = **25%** how many reviews mention it, **20%** how unhappy they are, **20%** how strong the evidence is (volume and number of sources), **20%** the link to leaving signals, **15%** an analyst impact judgement (a hypothesis). Each opportunity carries a product-manager brief; its counts come from the data, its proposals and root causes are hypotheses.
"""))
cells.append(code("#@title Product-manager briefs for the nine opportunities { display-mode: \"form\" }\n" + pm_src))
cells.append(code(r'''
t0 = time.time()
b = df                                              # the opportunity definitions below are written against this table
SRC = [p for p in b.platform.value_counts().index]
pct = lambda n, d, nd=1: round(100.0 * n / d, nd) if d else 0.0
def mask_any(cols): return b[cols].any(axis=1)
def nd(*names): return pd.concat([b["nd_" + n] for n in names], axis=1).any(axis=1)
def leave_mask(s): return (s.return_class == "Non-Return") & s.return_basis.isin(["Stated", "Signalled"])
SCALE = min(1.0, N / 2527)                          # volume thresholds are set for 2,527 reviews; smaller files scale down (with a floor)
EVID_FULL_N = max(8, 80 * SCALE)

''' + opps_block + r'''
opps = []
for oid, name, m, problem, seg, benefit, impact, link, improvement, metric, codes, theme_id, need_names in OPPS:
    s = b[m]; n = len(s)
    if n == 0: continue
    rated = s.rating_f.dropna()
    sev = (s.sentiment_label == "Negative").sum() / n
    sources = sum(1 for p in SRC if (s.platform == p).sum() >= 5)
    sw = leave_mask(s).sum() / n
    base_sw = leave_mask(b).mean()
    freq = min(1.0, pct(n, N) / 15.0); evid = min(1.0, 0.6 * sources / 4 + 0.4 * min(1.0, n / EVID_FULL_N)); rep = min(1.0, 4 * sw)
    score = 0.25 * freq + 0.20 * sev + 0.20 * evid + 0.20 * rep + 0.15 * impact / 5.0
    pool = s[(s.text.str.len().between(40, 230))]
    pool = pool.assign(_src=pool.source_url.str.startswith("http")).sort_values(["_src", "record_id"], ascending=[False, True])
    quotes = []
    for p in pool.platform.unique():
        quotes += list(pool[pool.platform == p].head(1).itertuples())
    quotes = quotes[:3]
    opps.append({"id": oid, "title": name, "problem": problem, "reviews": n, "pct": pct(n, N), "negative_pct": pct((s.sentiment_label == "Negative").sum(), n),
                 "low_rating_pct": pct((rated <= 2).sum(), len(rated)) if len(rated) else None, "non_return_pct": pct((s.return_class == "Non-Return").sum(), n),
                 "return_pct": pct((s.return_class == "Return").sum(), n), "leaving_signal_pct": pct(sw * n, n), "baseline_leaving_signal_pct": round(100 * base_sw, 1),
                 "by_source": {p: int((s.platform == p).sum()) for p in SRC}, "sources_present": sources, "theme": theme_id, "impact": impact,
                 "parts": {"frequency": round(freq, 3), "severity": round(sev, 3), "evidence": round(evid, 3), "repeat_relevance": round(rep, 3), "impact": impact},
                 "score": round(score, 3), "ids": list(s.record_id),
                 "quotes": [{"id": q.record_id, "source": q.platform, "url": q.source_url, "text": q.text[:230]} for q in quotes]})
opps.sort(key=lambda x: -x["score"])
for i, o in enumerate(opps, 1):
    o["rank"] = i
    o["priority"] = "High" if i <= 3 else ("Medium" if i <= 6 else "Low")
    pm = PM[o["id"]]
    conf = "High" if o["parts"]["evidence"] >= 0.9 and o["reviews"] >= max(10, 100 * SCALE) else ("Medium" if o["parts"]["evidence"] >= 0.6 and o["reviews"] >= max(5, 40 * SCALE) else "Low")
    o["confidence"] = conf
    o["recommendation"] = "Validate first" if conf == "Low" else ("Start now" if i <= 3 else ("Quick win" if pm["effort"] == "S" else "Plan next"))
    o["pm"] = pm
stage("rank", "Prioritise", "score()", f"{len(opps)} opportunities ranked", t0, "Top: " + (opps[0]["title"] if opps else "none"))
pd.DataFrame([dict(rank=o["rank"], opportunity=o["title"], score=o["score"], reviews=o["reviews"], share=f"{o['pct']}%", negative=f"{o['negative_pct']}%",
                   leaving_signals=f"{o['leaving_signal_pct']}%", priority=o["priority"], call=o["recommendation"]) for o in opps])
'''))
cells.append(md("""
## Step 6 · Prove
### Evidence checks
Plain checks on the file itself: how much can be traced to a source, how much is stated rather than inferred, and whether the sample is large enough to lean on.
"""))
cells.append(code(r'''
t0 = time.time()
n_rated = int(df.rating_f.notna().sum()); n_url = int(df.source_url.str.startswith("http").sum())
by_basis = df[df.return_class != "Insufficient Evidence"].return_basis.value_counts()
checks = [
    ("Reviews with a source link", f"{n_url} of {N}", pct(n_url, N), "Each finding can be opened at its source" if n_url / N > 0.9 else "Add a source link per row so findings can be checked"),
    ("Reviews with a star rating", f"{n_rated} of {N}", pct(n_rated, N), "Ratings help the Inferred return reading" if n_rated else "No ratings: return reading relies on wording"),
    ("Sources represented", str(df.platform.nunique()), None, ", ".join(df.platform.value_counts().head(5).index)),
    ("Return / Non-Return stated by the customer", f"{int(by_basis.get('Stated', 0))} of {N}", pct(by_basis.get("Stated", 0), N), "Only these are first-person statements; the rest are signalled or inferred"),
    ("Reviews with a clear return reading", f"{classified} of {N}", pct(classified, N), "Insufficient Evidence is kept apart, never forced into a class"),
    ("Sentiment labels", sent_method, None, ""),
]
if N < 200: checks.append(("Sample size", f"{N} reviews", None, "Small file: treat rankings as directions to test, not conclusions"))
stage("audit", "Prove: evidence checks", "checks()", f"{len(checks)} checks", t0)
pd.DataFrame(checks, columns=["check", "result", "share_%", "note"])
'''))
cells.append(md("""
### The report
Builds the self-contained HTML report and the two CSV files, shows the report inline, and downloads all three in Colab.
"""))
cells.append(code(r'''
t0 = time.time()
esc = lambda s: html.escape("" if s is None else str(s), quote=True)
P = lambda x: f"{x:.1f}%"
SENTS = ["Positive", "Negative", "Neutral", "Mixed", "Uncertain"]
top3 = [o for o in opps if o["recommendation"] == "Start now"][:3]
brief = []
if top3: brief.append(("Start now", "; ".join(f"{o['title']} (score {o['score']:.2f}, {o['reviews']} reviews)" for o in top3) + "."))
if opps: brief.append(("Biggest evidence base", f"{max(opps, key=lambda o: o['reviews'])['title']}: {max(opps, key=lambda o: o['reviews'])['reviews']} reviews ({P(max(opps, key=lambda o: o['reviews'])['pct'])} of the file)."))
brief.append(("Return reading", f"{P(pct(rcn.get('Return', 0), N))} of reviews read as Return and {P(pct(rcn.get('Non-Return', 0), N))} as Non-Return; {P(pct(rcn.get('Insufficient Evidence', 0), N))} are Insufficient Evidence. These are predictions from public text, not observed repeat bookings."))
if N < 200: brief.append(("Caution", f"Only {N} reviews: treat the ranking as a direction to test."))

CSS = """:root{--bg:#0a0c1d;--ink:#f3f4ff;--ink2:#c3c6e0;--ink3:#8e93b5;--line:rgba(160,150,255,.18);--glass:rgba(20,22,52,.7);--glass2:rgba(255,255,255,.05);--violet:#9b7bff;--blue:#4da8ff;--amber:#f6a152;--pos:#43d9a0;--neg:#ff6f8d;--neu:#8d92ad}
*{box-sizing:border-box}html{background:var(--bg)}body{margin:0;color:var(--ink);font:14.5px/1.6 "Plus Jakarta Sans",system-ui,-apple-system,"Segoe UI",sans-serif;padding:0 18px 70px;background:radial-gradient(60vw 40vw at -10% -10%,rgba(125,92,255,.32),transparent 60%),radial-gradient(50vw 30vw at 110% 110%,rgba(246,161,82,.16),transparent 60%),var(--bg)}
.w{max-width:1040px;margin:0 auto}h1,h2,h3{margin:0;line-height:1.2}h1{font-size:34px;letter-spacing:-.02em;padding-top:8px;overflow-wrap:anywhere}h1 span,h2 span{background:linear-gradient(90deg,#9b7bff,#f6a152);-webkit-background-clip:text;background-clip:text;color:transparent}h2{font-size:22px;margin:42px 0 6px;letter-spacing:-.01em}h3{font-size:15.5px}.m{color:var(--ink2)}.f{color:var(--ink3)}.eb{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--blue);font-weight:700}
.flowbar{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-top:22px}.fs{position:relative;background:var(--glass);border:1px solid var(--line);border-radius:16px;padding:12px 14px}.fs i{font-style:normal;display:inline-grid;place-items:center;width:24px;height:24px;border-radius:50%;background:linear-gradient(135deg,#7d5cff,#5a8bff);font-size:12px;font-weight:700;margin-right:6px}.fs b{font-size:13.5px}.fs small{display:block;color:var(--ink2);margin-top:4px;font-size:12.5px}
.k{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-top:18px}.kp{background:var(--glass);border:1px solid var(--line);border-radius:16px;padding:14px 16px}.kp b{display:block;font-size:26px;margin-top:2px;letter-spacing:-.02em}.kp small{color:var(--ink3);font-size:12px}
.c{background:var(--glass);border:1px solid var(--line);border-radius:18px;padding:18px;margin-top:14px;min-width:0}.b{display:grid;grid-template-columns:auto 1fr;gap:12px;margin-top:10px}.tg{font-size:11px;font-weight:700;padding:3px 10px;border-radius:99px;background:rgba(155,123,255,.18);color:#cdbfff;white-space:nowrap;align-self:start;margin-top:2px}
.stack{display:flex;gap:2px;height:12px;border-radius:99px;overflow:hidden;background:var(--glass2)}.stack span{display:block;min-width:2px}.p{background:var(--pos)}.u{background:var(--neu)}.g{background:var(--neg)}
.tw{overflow-x:auto;border:1px solid var(--line);border-radius:16px;background:var(--glass);margin-top:14px}table{border-collapse:collapse;width:100%;font-size:13.5px}th,td{padding:10px 12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}th{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink3)}tr:last-child td{border-bottom:0}td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
.pl{display:inline-block;font-size:11px;font-weight:700;padding:2px 10px;border-radius:99px;background:var(--glass2);color:var(--ink2);margin-right:5px}.pl.neg{background:rgba(255,111,141,.16);color:var(--neg)}.pl.pos{background:rgba(67,217,160,.16);color:var(--pos)}.pl.warn{background:rgba(246,161,82,.16);color:var(--amber)}.pl.acc{background:rgba(77,168,255,.16);color:var(--blue)}
details{background:var(--glass);border:1px solid var(--line);border-radius:18px;margin-top:10px}summary{cursor:pointer;padding:14px 16px;display:grid;grid-template-columns:30px 1fr auto;gap:12px;align-items:center;list-style:none}summary::-webkit-details-marker{display:none}.sc{font-size:28px;font-weight:800;text-align:right;letter-spacing:-.02em}.sc small{display:block;font-size:10px;letter-spacing:.12em;color:var(--ink3);font-weight:500}
.bd{padding:4px 16px 16px;border-top:1px solid var(--line)}.bd p{margin:9px 0}.q{border-left:3px solid var(--violet);padding:4px 0 4px 12px;margin:10px 0;color:var(--ink)}.q small{display:block;color:var(--ink3);font-size:11.5px}.q a{color:var(--blue)}ul{margin:7px 0 0;padding-left:18px}li{margin:5px 0}b,strong{font-weight:700}"""

def stack(p, u, g): return f'<div class="stack"><span class="p" style="flex:{p}"></span><span class="u" style="flex:{u}"></span><span class="g" style="flex:{g}"></span></div>'
H = [f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet"><title>Urban Company Discovery Engine, notebook report</title><style>{CSS}</style></head><body><div class="w">']
H.append(f'<div class="eb" style="padding-top:30px">Urban Company Discovery Engine · notebook report</div><h1><span>{esc(FILE_NAME)}</span></h1>')
H.append(f'<p class="m">Read from {N:,} comments in {sum(s["ms"] for s in STAGES) / 1000:.1f} seconds, using written rules only.</p>')
ribbon = [("Collect", f"{len(raw):,} rows loaded"), ("Clean", f"{N:,} comments kept"), ("Read", f"{P(pct(classified, N))} given a return reading"),
          ("Group", f"{len(THEMES)} themes"), ("Prioritise", f"{len(opps)} opportunities"), ("Prove", f"{len(checks)} evidence checks")]
H.append('<div class="flowbar">' + "".join(f'<div class="fs"><i>{i + 1}</i><b>{a}</b><small>{esc(b_)}</small></div>' for i, (a, b_) in enumerate(ribbon)) + "</div>")
pos_n, neg_n = int((df.sentiment_label == "Positive").sum()), int((df.sentiment_label == "Negative").sum())
kp = [("Reviews analysed", f"{N:,}", f"{df.platform.nunique()} sources"), ("Positive / Negative", f"{pct(pos_n, N)}% / {pct(neg_n, N)}%", "share of reviews"),
      ("Return reading", P(pct(classified, N)), f"{rcn.get('Return', 0):,} Return · {rcn.get('Non-Return', 0):,} Non-Return"),
      ("Themes", len(THEMES), f"{len(ISSUES)} problem and praise codes"), ("Opportunities", len(opps), "ranked by score")]
H.append('<div class="k">' + "".join(f'<div class="kp"><span class="eb">{esc(a)}</span><b>{esc(b_)}</b><small>{esc(c)}</small></div>' for a, b_, c in kp) + "</div>")
H.append('<div class="c"><h3>Generated brief</h3>' + "".join(f'<div class="b"><span class="tg">{esc(a)}</span><span>{esc(c)}</span></div>' for a, c in brief) + "</div>")

H.append('<h2>Step 3 · <span>Return / Non-Return</span></h2><p class="m">How each review was read. Stated = said in the first person; Signalled = advice to others, switching, distrust or trust; Inferred = from sentiment and rating.</p><div class="tw"><table><thead><tr><th>Class</th><th class="n">Reviews</th><th class="n">Share</th><th class="n">Stated</th><th class="n">Signalled</th><th class="n">Inferred</th></tr></thead><tbody>')
for c_ in ["Return", "Non-Return", "Insufficient Evidence"]:
    sub = df[df.return_class == c_]
    bb = sub.return_basis.value_counts()
    H.append(f'<tr><td><b>{c_}</b></td><td class="n">{len(sub):,}</td><td class="n">{P(pct(len(sub), N))}</td>' + "".join(f'<td class="n">{int(bb.get(x, 0)) if c_ != "Insufficient Evidence" else "–"}</td>' for x in ("Stated", "Signalled", "Inferred")) + "</tr>")
H.append("</tbody></table></div>")

H.append('<h2>Step 4 · <span>Themes</span></h2><p class="m">Five themes group the problem types. A review can fall in several, so shares overlap.</p><div class="tw"><table><thead><tr><th>Theme</th><th class="n">Reviews</th><th class="n">Share</th><th>Sentiment of these reviews</th></tr></thead><tbody>')
for t_, (nm, _codes) in sorted(THEMES.items(), key=lambda kv: -int(df["th_" + kv[0]].sum())):
    s_ = df[df["th_" + t_]]
    cnt = s_.sentiment_label.value_counts()
    H.append(f'<tr><td><b>{t_}</b> {esc(nm)}</td><td class="n">{len(s_):,}</td><td class="n">{P(pct(len(s_), N))}</td><td style="min-width:160px">{stack(cnt.get("Positive", 0), cnt.get("Neutral", 0) + cnt.get("Mixed", 0) + cnt.get("Uncertain", 0), cnt.get("Negative", 0))}</td></tr>')
H.append("</tbody></table></div>")

H.append('<h2>Step 5 · <span>Opportunities</span></h2><p class="m">Score = 25% how many reviews, 20% how unhappy, 20% evidence strength, 20% link to leaving signals, 15% analyst impact judgement. Counts come from the reviews; proposals, root causes and effort are product hypotheses.</p>')
for i, o in enumerate(opps):
    pm, tcls = o["pm"], ("pos" if o["recommendation"] == "Start now" else "acc" if o["recommendation"] in ("Quick win", "Plan next") else "warn")
    H.append(f'<details{" open" if i == 0 else ""}><summary><span class="f">{o["rank"]:02d}</span><div><b>{esc(o["title"])}</b> <span class="pl {tcls}">{esc(o["recommendation"])}</span><span class="pl">{o["priority"]} priority</span><span class="pl">{o["confidence"]} confidence</span><br><span class="m">{o["reviews"]:,} reviews ({P(o["pct"])}) · {P(o["negative_pct"])} negative · {P(o["leaving_signal_pct"])} leaving signals (file baseline {P(o["baseline_leaving_signal_pct"])})</span></div><div class="sc">{o["score"]:.2f}<small>SCORE</small></div></summary><div class="bd">')
    H.append(f'<p><b>Problem:</b> {esc(pm["problem"])}</p><p><b>Who is affected:</b> {esc(pm["who"])}</p>')
    H.append("<p><b>What to build</b></p><ul>" + "".join(f'<li><b>{esc(x["title"])}.</b> {esc(x["what"])}</li>' for x in pm["proposal"]) + "</ul>")
    H.append(f'<p><b>Why it should lift repeat booking (hypothesis):</b> {esc(pm["repeat_mechanism"])}</p><p><b>Success looks like:</b> {esc(pm["success"])}</p><p><b>Watch out:</b> {esc(pm["watch_out"])}</p><p class="f">Effort: {esc(pm["effort"])}. {esc(pm["effort_note"])}</p>')
    pr = o["parts"]
    H.append(f'<p class="f">Score parts: frequency {pr["frequency"]:.2f} · severity {pr["severity"]:.2f} · evidence {pr["evidence"]:.2f} · leaving signals {pr["repeat_relevance"]:.2f} · impact judgement {pr["impact"]}/5. By source: ' + ", ".join(f"{esc(k)} {v}" for k, v in o["by_source"].items() if v) + ".</p>")
    for q in o["quotes"]:
        link = f' · <a href="{esc(q["url"])}" target="_blank" rel="noopener">open source</a>' if str(q["url"]).startswith("http") else ""
        H.append(f'<div class="q">“{esc(q["text"])}”<small>{esc(q["source"])} · {esc(q["id"])}{link}</small></div>')
    H.append("</div></details>")

H.append('<h2>Step 6 · <span>Evidence checks</span></h2><div class="tw"><table><thead><tr><th>Check</th><th>Result</th><th>Note</th></tr></thead><tbody>' + "".join(f'<tr><td>{esc(a)}</td><td>{esc(b_)}</td><td class="m">{esc(d)}</td></tr>' for a, b_, _c, d in checks) + "</tbody></table></div>")
H.append('<h2>How this run went</h2><div class="tw"><table><thead><tr><th>#</th><th>Step</th><th>Function</th><th>Result</th><th class="n">ms</th></tr></thead><tbody>')
for i, s in enumerate(STAGES):
    H.append(f'<tr><td>{i + 1}</td><td><b>{esc(s["title"])}</b></td><td>{esc(s["fn"])}</td><td>{esc(s["io"])}' + (f'<br><span class="f">{esc(s["note"])}</span>' if s.get("note") else "") + f'</td><td class="n">{s["ms"]}</td></tr>')
H.append('</tbody></table></div><p class="f" style="margin-top:30px;max-width:80ch">Results come from deterministic rules inside this notebook, not a language model, so they are traceable and repeatable. Return and Non-Return are predictions from public text, not observed repeat-booking rates.</p></div></body></html>')
report_html = "".join(H)

# ---- CSV outputs
enriched = df[["record_id", "platform", "review_date", "rating", "sentiment_label", "return_class", "return_basis", "return_confidence", "return_reason", "source_url", "service_category", "review_title", "review_text"]].copy()
enriched["themes"] = [", ".join(t for t in THEMES if r[f"th_{t}"]) for _, r in df.iterrows()]
enriched["problem_types"] = [", ".join(k for k in ISSUES if r[f"i_{k}"]) for _, r in df.iterrows()]
opp_df = pd.DataFrame([dict(rank=o["rank"], opportunity_id=o["id"], opportunity=o["title"], score=o["score"], reviews=o["reviews"], share_pct=o["pct"], negative_pct=o["negative_pct"],
                            leaving_signal_pct=o["leaving_signal_pct"], priority=o["priority"], recommendation=o["recommendation"], confidence=o["confidence"], effort=o["pm"]["effort"],
                            problem=o["pm"]["problem"], success=o["pm"]["success"], review_ids=" ".join(o["ids"])) for o in opps])
os.makedirs(OUTPUT_DIR, exist_ok=True)
stem = re.sub(r"[^\w.-]+", "_", re.sub(r"\.[^.]+$", "", FILE_NAME))
paths = {"report": f"{OUTPUT_DIR}/{stem}_discovery_report.html", "opportunities": f"{OUTPUT_DIR}/{stem}_opportunities.csv", "enriched_reviews": f"{OUTPUT_DIR}/{stem}_enriched_reviews.csv"}
open(paths["report"], "w", encoding="utf-8").write(report_html)
opp_df.to_csv(paths["opportunities"], index=False, encoding="utf-8-sig")
enriched.to_csv(paths["enriched_reviews"], index=False, encoding="utf-8-sig")
stage("report", "Prove: report", "build_report()", "3 files written", t0)

print(f"Analysed {N:,} reviews. {P(pct(classified, N))} classified Return / Non-Return.")
if opps: print(f"Top opportunity: {opps[0]['title']} (score {opps[0]['score']:.2f})")
print("Files:", *paths.values(), sep="\n  ")
try:
    from IPython.display import HTML, display
    display(HTML(report_html))
except Exception: pass
if IN_COLAB:
    for p in paths.values(): colab_files.download(p)
'''))

# ------------------------------------------------------------------------------------------------ write
nb = {"nbformat": 4, "nbformat_minor": 5,
      "metadata": {"colab": {"name": f"{NAME}.ipynb", "provenance": []}, "kernelspec": {"name": "python3", "display_name": "Python 3"}, "language_info": {"name": "python"}},
      "cells": cells}
path = OUT / f"{NAME}.ipynb"
path.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")


def src(c):
    return "".join(c["source"])


def is_payload(c):
    return c["cell_type"] == "code" and "PRELOADED_CSV_B64 = (" in src(c)


# the notebook must never mention the excluded scope
for c in cells:
    if not is_payload(c):
        assert not re.search(r"insta[\s_-]*help", src(c), re.I), "excluded scope leaked into the notebook"
        assert "CLOUDFLARE" not in src(c).upper() and "API_TOKEN" not in src(c).upper(), "no credentials belong in the notebook"

# Markdown export and a light copy for the website viewer (the embedded dataset is replaced by a note)
def placeholder(c):
    return f'PRELOADED_NAME = "urban_company_reviews_master.csv"\nPRELOADED_CSV_B64 = "<compressed copy of the {N_MASTER:,}-review dataset, {len(b64) // 1024:,} KB, embedded in the .ipynb file>"\n'


md_parts = [f"# Urban Company Discovery Engine: notebook\n\n> Markdown export of the notebook `{NAME}.ipynb`. Code and markdown cells are in their original order. The embedded dataset payload ({len(b64) // 1024:,} KB) is left out here and is kept in the `.ipynb`.\n\n**Notebook cells:** {len(cells)}\n\n---\n"]
view = []
k = 0
heading = "Code"
for c in cells:
    if c["cell_type"] == "markdown":
        md_parts.append(src(c) + "\n")
        view.append({"type": "markdown", "source": src(c)})
        h = re.search(r"^#{2,3}\s+(.*)$", src(c), re.M)
        if h:
            heading = re.sub(r"^\d+\.\s*", "", h.group(1)).strip()
    else:
        k += 1
        body = placeholder(c) if is_payload(c) else src(c)
        md_parts.append(f"### Notebook code cell {k}\n\n```python\n{body}\n```\n")
        ttl = re.match(r"#@title\s+(.*?)(?:\s*\{.*)?$", body.strip().splitlines()[0])
        view.append({"type": "code", "source": body, "title": ttl.group(1) if ttl else heading, "note": "embedded dataset" if is_payload(c) else ""})
(OUT / f"{NAME}.md").write_text("\n".join(md_parts), encoding="utf-8")
(OUT / f"{NAME}_view.json").write_text(json.dumps({"title": "Urban Company Discovery Engine, in a notebook", "file": f"{NAME}.ipynb", "reviews": N_MASTER, "cells": view}, ensure_ascii=False), encoding="utf-8")

pub = ROOT / "frontend" / "public" / "notebook"
pub.mkdir(parents=True, exist_ok=True)
for ext in (".ipynb", ".md", "_view.json"):
    shutil.copy2(OUT / f"{NAME}{ext}", pub / f"{NAME}{ext}")
print("written", path, path.stat().st_size // 1024, "KB;", len(cells), "cells; embedded dataset", len(b64) // 1024, "KB")
