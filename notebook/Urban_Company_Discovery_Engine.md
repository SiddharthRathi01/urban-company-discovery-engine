# Urban Company Discovery Engine: notebook

> Markdown export of the notebook `Urban_Company_Discovery_Engine.ipynb`. Code and markdown cells are in their original order. The embedded dataset payload (486 KB) is left out here and is kept in the `.ipynb`.

**Notebook cells:** 31

---

# Urban Company Discovery Engine, in a notebook

**Press Runtime → Run all** (Ctrl+F9). The notebook opens with the **2,527 public Urban Company reviews** already inside it, so there is nothing to upload and nothing to set up.
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

## Step 1 · Collect
Choose where the comments come from. The default is the built-in Urban Company dataset; pick *Upload my own CSV* to use your own file.

### Notebook code cell 1

```python
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
```

### The built-in dataset
The Urban Company review file (2,527 public reviews from Google Play, Reddit and two complaint sites, each with its own source link) is stored inside this notebook, so *Run all* works with no upload. Nothing to edit in the next cell.

### Notebook code cell 2

```python
PRELOADED_NAME = "urban_company_reviews_master.csv"
PRELOADED_CSV_B64 = "<compressed copy of the 2,527-review dataset, 486 KB, embedded in the .ipynb file>"

```

### Load the file

### Notebook code cell 3

```python
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
```

### Find the columns
Finds the review text column and the optional columns (title, source, rating, date, link, service category, an existing sentiment label). Only a text column is required.

### Notebook code cell 4

```python
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
```

## Step 2 · Clean
Empty rows are dropped. A comment counts as a duplicate only when the text, the place and the day are all the same, because short reviews such as "good app" are often different people.

### Notebook code cell 5

```python
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
```

## Step 3 · Read
Every comment is read three ways: how the customer feels, what problem they raise, and whether their words point to coming back.

### Sentiment
The built-in dataset already carries sentiment labels that were read by an analyst. For your own CSV, a transparent text lexicon (VADER plus home-services terms) labels every review as Positive, Negative, Neutral, Mixed or Uncertain. The star rating is used only as a tie-breaker when the words carry no feeling.

### Notebook code cell 6

```python
#@title Sentiment word list  { display-mode: "form" }
try:
    import vaderSentiment
except ImportError:
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "vaderSentiment"])
import re
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_an = SentimentIntensityAnalyzer()
_an.lexicon.update({
    # negative service-failure vocabulary VADER lacks or under-weights
    "noshow": -2.5, "scam": -3.0, "scammed": -3.0, "fraud": -3.0, "fraudulent": -3.0, "cheat": -2.8, "cheated": -2.8, "cheating": -2.8,
    "overcharge": -2.2, "overcharged": -2.2, "overcharging": -2.2, "overpriced": -2.0, "expensive": -1.2, "costly": -1.2, "exorbitant": -2.4,
    "pathetic": -3.0, "worst": -3.2, "rude": -2.4, "arrogant": -2.2, "unprofessional": -2.6, "unreliable": -2.4, "unresponsive": -2.2,
    "damaged": -2.2, "damage": -1.8, "broke": -1.8, "broken": -1.8, "ruined": -2.6, "delay": -1.4, "delayed": -1.6, "late": -1.2,
    "cancelled": -1.6, "canceled": -1.6, "cancels": -1.4, "cancelling": -1.4, "cancellation": -1.0, "reschedule": -0.8, "rescheduled": -1.0,
    "refund": -0.6, "waste": -2.0, "wasted": -2.0, "useless": -2.6, "horrible": -3.0, "terrible": -3.0, "disappointed": -2.4,
    "disappointing": -2.4, "unhappy": -2.0, "dissatisfied": -2.2, "harassment": -2.8, "harassed": -2.6, "misbehaved": -2.4, "misbehavior": -2.4,
    "unhelpful": -2.2, "incompetent": -2.6, "negligent": -2.4, "leaking": -1.4, "faulty": -2.0, "defective": -2.2, "unresolved": -2.0,
    "poor": -2.2, "bad": -2.4, "never": -0.8, "didn't": -0.4, "didnt": -0.4, "not": -0.3,
    # positive service vocabulary
    "punctual": 2.2, "polite": 2.0, "courteous": 2.2, "professional": 1.6, "thorough": 1.8, "neat": 1.6, "clean": 1.0, "cleaned": 1.0,
    "satisfied": 2.2, "satisfactory": 1.8, "recommend": 2.0, "recommended": 2.0, "excellent": 3.0, "amazing": 3.0, "awesome": 3.0,
    "helpful": 2.2, "prompt": 1.8, "promptly": 1.8, "efficient": 2.0, "reliable": 2.2, "convenient": 2.0, "hassle-free": 2.2, "smooth": 1.8,
    "seamless": 2.2, "affordable": 1.8, "wonderful": 3.0, "fantastic": 3.0, "brilliant": 2.8, "superb": 3.0, "lovely": 2.4, "delighted": 2.8,
    "hardworking": 2.0, "skilled": 2.0, "trained": 1.2, "trustworthy": 2.2, "genuine": 1.6, "friendly": 2.0, "responsive": 2.0, "quick": 1.4, "quickly": 1.4,
})
NEG_NO_SHOW = re.compile(r"(?:did(?:n't| not)|never|not|yet to|hasn't|haven't|hasn’t|didn’t)\s+(?:turn(?:ed)?\s*up|show(?:ed)?\s*up|come|came|arrive[d]?|reach(?:ed)?|visit(?:ed)?|call(?:ed)?|respond(?:ed)?|reply|replied|attend(?:ed)?)|no[- ]show|didn[’']t (?:turn|show)|never came|not (?:come|came|arrived)", re.I)
NEG_PHRASES = re.compile(r"(?:can[’']?t|cannot|unable to|not able to|couldn[’']?t|no way to|impossible to|difficult to)\s+(?:talk|speak|contact|reach|connect|book|get|cancel|find|change|use|login|log)|no (?:number|option|helpline|customer care|human|slot|way)|not (?:showing|working|opening|loading|available|serviceable)|doesn[’']?t work|isn[’']?t working|not (?:satisf|happy|good|worth|professional|well|clean|working|resolved|refunded|received|available|helpful|up to)|money (?:was )?(?:deducted|debited|taken)|(?:no|not getting) (?:refund|response|reply|help|support|slot|slots)|still (?:waiting|pending|not)|waste of (?:time|money)|too (?:high|costly|expensive|much)|not recommend|never again|don[’']t (?:book|use|go|waste|recommend)|do not (?:book|use|go|recommend)|stay away|avoid", re.I)
POS_PHRASES = re.compile(r"(?:highly |would |will |definitely )?recommend(?:ed)?|very good|really good|great (?:service|job|work|experience|app)|well done|on time|on-time|good (?:service|work|job|experience|app|quality)|satisfied with|happy with|thank(?:s| you)|best (?:service|app|experience)|love (?:it|the|this)|value for money|worth (?:it|the)", re.I)
CONTRAST = re.compile(r"\b(?:but|however|although|though|except|yet|unfortunately|only issue|only problem|one (?:issue|problem|complaint)|apart from|otherwise|still)\b", re.I)
QUESTION = re.compile(r"\?|\b(?:how (?:do|can|to)|is there|do you|does (?:it|anyone|urban)|can (?:i|you|we|someone)|any(?:one)? (?:know|recommend|suggest)|which is better|should i|looking for|need(?:ed)? (?:a|an|to)|want(?:ed)? to know|please (?:call|contact|help))", re.I)
HINGLISH = re.compile(r"\b(?:hai|hain|nahi|nahin|nhi|bahut|bohot|kya|kyu|kyun|karo|karna|kiya|mera|meri|aap|apka|aapka|achha|accha|bekar|bakwas|paisa|paise|wala|wale|toh|kaam|abhi|aur|lekin|mujhe|hum|ho|gaya|gayi|raha|rahi|tha|thi|ka|ki|ke)\b", re.I)

SENT_SPLIT = re.compile(r"(?<=[\.\!\?\n])\s+|\s*;\s*|\s+(?=but\b|however\b|although\b|though\b|unfortunately\b)", re.I)


def _score(s):
    c = _an.polarity_scores(s)["compound"]
    if NEG_NO_SHOW.search(s): c = min(c, 0) - 0.55
    if NEG_PHRASES.search(s): c -= 0.6
    if POS_PHRASES.search(s): c += 0.30
    return max(-1.0, min(1.0, c))


def _nonenglish(t):
    letters = re.findall(r"[^\W\d_]", t)
    if not letters: return True
    nonlatin = sum(1 for ch in letters if ord(ch) > 0x024F)
    if nonlatin / len(letters) > 0.3: return True
    words = re.findall(r"[A-Za-z']+", t.lower())
    return len(words) >= 4 and sum(1 for w in words if HINGLISH.fullmatch(w)) / len(words) > 0.22


def label(title, text, rating):
    """Return (label, method, score). rating may be None/NaN."""
    full = ((title or "") + ". " + (text or "")).strip()
    r = None if rating is None or rating != rating else float(rating)
    if not re.search(r"[A-Za-zऀ-ॿ]", full):
        return "Uncertain", "text has no readable words (emoji/symbols only)", 0.0
    if _nonenglish(full):
        return "Uncertain", "text mostly non-English/Hinglish - English lexicon unreliable; needs human/LLM read", 0.0
    parts = [p.strip() for p in SENT_SPLIT.split(full) if p and len(p.strip()) > 2]
    scores = [_score(p) for p in parts] or [0.0]
    overall = _score(full)
    avg = sum(scores) / len(scores)
    pos = [s for s in scores if s >= 0.35]; neg = [s for s in scores if s <= -0.35]
    strong_pos = max(scores) if scores else 0; strong_neg = min(scores) if scores else 0
    polarity = 0.5 * overall + 0.5 * avg
    if pos and neg and strong_pos >= 0.5 and strong_neg <= -0.5 and abs(polarity) < 0.45:
        lab, m = "Mixed", "text: positive and negative statements both present"
    elif polarity >= 0.25 and not (neg and strong_neg <= -0.55):
        lab, m = "Positive", "text lexicon"
    elif polarity <= -0.25 and not (pos and strong_pos >= 0.55):
        lab, m = "Negative", "text lexicon"
    elif neg and pos and abs(polarity) < 0.25:
        lab, m = "Mixed", "text: weaker positive and negative statements both present"
    else:
        # text carries no clear polarity
        if r is not None and not QUESTION.search(full) and len(re.findall(r"\w+", full)) <= 14:
            if r >= 4: lab, m = "Positive", "rating tie-break (text neutral)"
            elif r <= 2: lab, m = "Negative", "rating tie-break (text neutral)"
            else: lab, m = "Neutral", "text neutral; 3-star rating"
        elif r is not None and r <= 1 and not QUESTION.search(full):
            lab, m = "Negative", "rating tie-break (text neutral)"
        else:
            lab, m = "Neutral", "text: no clear polarity (enquiry/factual)"
    # contradiction with rating -> do not force a label
    if r is not None:
        if lab == "Positive" and r <= 1.5 and "text lexicon" == m and polarity < 0.6:
            lab, m = "Uncertain", "text reads positive but rating is 1 star (possible sarcasm / mis-rating)"
        elif lab == "Negative" and r >= 4.5 and "text lexicon" == m and polarity > -0.6:
            lab, m = "Uncertain", "text reads negative but rating is 5 stars (possible mis-rating)"
    return lab, m, round(polarity, 3)
```

### Notebook code cell 7

```python
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
```

### The problem the customer raises
Phrase rules flag **26 codes**: 22 problems customers raise and 4 kinds of praise (a review can have several). Fourteen **unmet-need** types are flagged separately. The rules are written out below; edit them to fit your own product.

### Notebook code cell 8

```python
#@title Problem and theme rules  { display-mode: "form" }
import re
I = re.I

# ------------------------------------------------------------------ issue codes (multi-label)
ISSUES = {
    # ---- fulfilment reliability & availability
    "cancelled": r"cancel\w*\b.{0,30}(?:moment|minute|the end|last)|(?:guys|they|he|she|professionals?|technicians?|partners?|beauticians?|uc|company) cancel|cancel(?:l)?(?:ed|s|ing|ation)?\b.{0,40}(?:last[- ]minute|booking|service|appointment|without|by (?:the )?(?:professional|company|uc|urban))|last[- ]minute cancel|booking (?:got |was |is )?cancel|auto[- ]?cancel|cancel(?:led)? (?:my|the|our) (?:booking|service|appointment|order)",
    "rescheduled": r"re-?schedul",
    "no_show": r"(?:did(?:n[’']?t| not)|never|not|yet to|hasn[’']?t|haven[’']?t)\s+(?:turn(?:ed)?\s*up|show(?:ed)?\s*up|come|came|arrive[d]?|reach(?:ed)?|visit(?:ed)?|attend(?:ed)?)|no[- ]show|never came|nobody (?:came|turned)|no one (?:came|turned|showed)|not (?:come|came|arrived)|left without|ghost",
    "late": r"\blate\b|delay(?:ed|s)?\b|not on time|not punctual|hours? late|kept (?:us |me )?waiting|waiting for|too long to|not (?:in|on) time|not timely|(?:came|arrived|reached)\b.{0,15}(?:late|after)",
    "slot_unavailable": r"no slots?|slots? (?:are |is |were )?(?:not|never|unavailable|full)|(?:not|never|unable to|can[’']?t|couldn[’']?t|cannot) (?:get|find|book|see|able to book).{0,25}(?:slot|booking|appointment|professional|service)|no (?:professional|partner|technician|beautician)s? (?:available|assigned)|fully booked|not available (?:at|for|in)|unavailable|all out|booking (?:is )?not (?:possible|confirmed)|take too long for the slot|not able to book",
    # ---- pricing, fees, policy
    "price_high": r"(?:rates?|pricing|prices?|tariff|fares?|fees?)\b.{0,30}(?:high|higher|concern|review|competitive|reduc\w+|practical|abnormal|unreasonable|steep|affordable|too|more than|much|increas\w+|hik\w+|doubl\w+|tripl\w+)|(?:high|higher|reasonable|affordable|competitive|abnormal|exorbitant)\b.{0,12}(?:rates?|pricing|prices?|tariff|charges?|fees?)|expensive|costly|overpriced|over[- ]priced|too (?:high|much|costly|expensive)|exorbitant|(?:increas|hik|rais)\w*\b.{0,15}(?:price|rate|charge)|pricey|daylight robbery|concern about (?:the )?(?:rates?|price|pricing)|review (?:the )?pric\w+|\b(?:cost|charges?)\b.{0,25}(?:very |too |so )?(?:high|much|difficult to afford)|\b\dx\b.{0,20}local|times (?:as )?(?:much )?(?:compare\w* )?(?:to |than |as )?(?:the )?local|(?:difficult|hard) to afford",
    "fees_charges": r"(?:pause|extend|cancel)\b.{0,15}(?:your |the |my )?(?:plan|subscription|membership|pack)|plan (?:cancel|pause|expir)\w*|tips? (?:automatically|added|forced)|(?:discount|coupon|offer)s?\b.{0,30}(?:new (?:user|customer)|existing|loyal|regular)|platform fees?|convenience fee|visit(?:ing|ation)? (?:charge|fee)|surge|cancellation (?:fee|charge)|minimum (?:order|booking|amount|cart)|min(?:imum)? (?:order|booking)|hidden (?:charge|fee|cost)|additional (?:charge|fee)|extra (?:charge|fee)|\bgst\b|\btax(?:es)?\b|tipping|\btip\b|plus member|subscription",
    "overcharge_upsell": r"overcharg|inflated|extra (?:money|amount|cash|payment)|asked (?:for )?(?:extra|more|additional) (?:money|amount|cash)|demand(?:ed|s|ing)? (?:extra|more|additional|3 times|double)|spare part|(?:parts?) (?:cost|price|charge)|quoted\b.{0,40}(?:but|then|after)|different (?:rate|price|amount)|price (?:shown|displayed|changed|different)|rates? (?:shown|displayed|mismatch)|upsell|unnecessar\w+ (?:part|replac|work)|charged (?:me )?(?:more|extra|double|twice)|double (?:the )?(?:price|amount|charge)|local .{0,25}(?:cheaper|charge|fraction|half)|cheaper|misleading (?:price|pricing|rate|charge)|(?:wrong|extra|more) (?:amount|charges?)",
    # ---- support, refunds, resolution
    "support_unreachable": r"customer (?:care|support|service)\b.{0,50}(?:no|not|poor|worst|useless|pathetic|bad|non[- ]?existent|zero|unable|difficult|can[’']?t|cannot|unhelpful|hopeless|absent|missing|never|weak)|(?:no|not|poor|worst|useless|pathetic|bad|zero|unhelpful|hopeless|missing|difficult|weak).{0,30}customer (?:care|support|service)|no (?:human|helpline|contact (?:number|option)|number to|way to (?:talk|reach|contact|speak))|(?:can[’']?t|cannot|unable to|not able to|couldn[’']?t|difficult to|impossible to|no way to)\s+(?:talk|speak|reach|contact|connect|call)\b|chat ?bot|\bbot\b|\bai (?:bot|chat|assistant|support|help|agent|customer)|automated (?:message|response|reply)|no (?:customer )?(?:care|support) (?:number|team)|toll[- ]free|doesn[’']?t let you call",
    "refund_payment": r"refund|money (?:was |got |is |has been )?(?:deducted|debited|taken|stuck|not (?:returned|received))|not (?:been )?refunded|amount (?:was |got )?(?:deducted|debited)|payment (?:failed|deducted|not (?:reflected|updated|showing|received))|charged (?:twice|double)|double payment|credit(?:ed)? back|wallet",
    "unresolved": r"unresolved|not (?:been )?(?:resolved|solved|addressed|resolve|attended)|no (?:response|reply|resolution|action|follow[- ]?up|call ?back|one (?:called|responded|contacted))|(?:still|yet) (?:not|pending|waiting)|no one (?:called|responded|contacted|has contacted|got back)|escalat|complaint\b.{0,30}(?:closed|ignored|not)|ignored|nobody (?:called|responded|contacted)|haven[’']?t (?:heard|received a)|never (?:got|received) (?:a )?(?:call|response|reply)|closed (?:my )?(?:complaint|ticket|case)|after[- ]sales? service",
    "warranty_rework": r"warrant(?:y|ies)|guarantee|re-?visit|re-?service|follow[- ]?up (?:service|visit)|issue (?:came|came back|reoccur\w*|re-?appear\w*|repeat\w*|persist\w*)|(?:problem|issue|leak\w*|cooling|dirt\w*|stain\w*|cockroach\w*|pests?) (?:again|persist\w*|still|remain\w*|returned|came back)|again (?:after|within)|not working (?:after|again)|stopped working (?:after|within)|within (?:a )?(?:week|few days|\d+ days|days)",
    "native_after_sales": r"(?:native|purifier|\bro\b|\bm[123]\b|smart lock|lock ultra)\b.{0,220}(?:not working|stopped|defect\w*|faulty|leak\w*|install\w*|delay\w*|tds\b|membrane|warrant\w*|technician|replac\w*|complain\w*|issue|problem|motherboard|mother board|no (?:update|response|support|service)|support|service)|(?:install\w*|defect\w*|faulty|motherboard|mother board|stopped (?:working|dispens\w+)).{0,160}(?:native|purifier|\bro\b|\bm[123]\b)",
    # ---- service quality, conduct, trust
    "poor_quality": r"lazy|slow in work|working slow\w*|time (?:period )?(?:was )?reduc\w+|reduced the time|less time|not enough time|poor (?:quality|service|work|job)|bad (?:work|service|quality|cleaning)|not (?:clean|cleaned|cleaning|proper|properly|done|completed|up to)|unprofessional|unskilled|untrained|incompetent|not (?:well )?trained|no knowledge|half[- ]?done|incomplete|left (?:the )?(?:work|job|midway|in between)|worst (?:cleaning|work)|stains?\b.{0,20}(?:remain|still|left|visible)|did(?:n[’']?t| not) clean|rushed|careless|negligen|sloppy|not (?:worth|value)|didn[’']?t (?:know|knew)|lack of (?:knowledge|training|skill)|(?:wasn[’']?t|was not|isn[’']?t|is not) (?:good|proper)|not satisf\w+|messed|mess up|(?:service|work|job|installation|massage|cleaning|repair)\b.{0,15}\b(?:is|was|are|were)? ?(?:very |so |really |too |extremely )?(?:poor|bad|worst|pathetic|terrible|horrible|disappointing|useless|superficial)|still (?:many |some )?(?:tough )?stains|stains?\b.{0,30}still",
    "damage_theft": r"damag(?:e|ed|es|ing)|broke\b|broken|ruin(?:ed)?|scratch|burn(?:t|ed)\b|stolen|theft|stole\b|steal|missing (?:from|after)|burst|short[- ]?circuit|spark|dismantle",
    "conduct_safety": r"\brude\b|arrogan\w+|misbehav\w+|abus\w+|harass\w+|threat\w+|argu(?:e|ed|ing|ment)|attitude|disrespect\w*|creepy|unsafe|safety|inappropriate|forced (?:me )?(?:to )?(?:give|rate)|(?:ask|ask(?:ed|ing)|force|forced|pressur\w+)\b.{0,25}(?:5|five)[- ]?(?:\*|star)|personal number|(?:asked|ask) (?:me )?for (?:a )?(?:5|five)",
    "trust_fraud": r"scam\w*|fraud\w*|cheat\w*|dishonest\w*|liar|\blie[sd]?\b|false (?:information|promise|assur\w+|claim\w*|commit\w*)|mislead\w*|\bfake\b|loot\w*|robb\w*|dupe[d]?|betray|can[’']?t trust|not trust\w*|don[’']?t trust|untrust\w*|no trust|lost (?:my |all )?(?:trust|faith)|not a trust",
    # ---- coverage, missing services, app
    "coverage_gap": r"not (?:available|provided|serviced?|offered|operational|working) (?:in|at|for) (?:my|our|this|the) (?:area|city|location|town|locality|region|society|pin)|(?:my|our) (?:area|city|town|location|locality|pincode)\b.{0,40}(?:not|no|isn[’']?t|unavailable)|(?:not|no|doesn[’']?t|isn[’']?t|aren[’']?t)\b.{0,30}(?:available|serviceable|service|cover\w*|operat\w*|present).{0,15}(?:here|in my|in our|at my|there)|not serviceable|expand|more (?:cities|areas)|tier[- ]?(?:2|3|ii)|bring (?:this |these |the )?(?:service|services)|start (?:this |these |the |your )?(?:service|services)|doesn[’']?t (?:work|operate|serve|cover) here|services? (?:is|are) not (?:yet )?available|not there at few locations|not (?:in|at) (?:my|our) (?:area|city)|(?:is|are) not available in (?:my|our|the) (?:area|city)",
    "missing_service_request": r"(?:please|plz|pls|kindly|should|must|need to|needs to|can you|could you|would be (?:great|nice|good)|wish|hope you|request (?:you )?to|suggest\w*)\b.{0,50}\b(?:add|provide|include|introduce|start|launch|offer|have|bring|keep|allow|enable|give)\b|no (?:option|service|provision|facility|way) (?:for|to|of)|there is no (?:option|service|provision)|not (?:listed|available) (?:in|on|under) (?:the )?(?:app|menu|list)|missing|doesn[’']?t (?:have|offer|provide|include) (?:a |any |an )?(?:option|service)|(?:don[’']?t|do not) (?:have|offer|provide) (?:a |any |an )?(?:option|service)|classic (?:service|option|segment)|single bathroom|1 bathroom|pay after|cash (?:option|on delivery|payment)|\bcod\b",
    "app_friction": r"(?:top portion|status bar|overlap\w*|screen|display).{0,30}(?:app|phone)|app (?:experience|interface|design)|(?:no|limited) (?:contact us|communication)|\bapp\b.{0,40}(?:not|crash\w*|hang\w*|slow|bug\w*|glitch\w*|freez\w*|stuck|lag\w*|work\w*|open\w*|load\w*|error)|crash\w*|glitch\w*|\bbugs?\b|freez\w*|something went wrong|black screen|otp (?:not|doesn|issue|problem)|location (?:issue|problem|error|fetch\w*|not)|keeps? (?:asking|crash)|\blogin\b|log in|user[- ]?friendly|interface|\bui\b|\bux\b|can[’']?t (?:book|cancel|edit|reschedule|add|select|see|view|find) (?:on|in|from|the|any|my|a)|unable to (?:book|cancel|edit|reschedule|add|select|see|view|find|check ?out)",
    "native_product": r"\bnative\b|water purifier|\bro\b|purifier|smart lock|lock ultra|\bm1\b|\bm2\b|\bm3\b|\btds\b|membrane",
    # ---- unspecified dissatisfaction (reported separately; not a theme)
    "generic_negative": r"^\W*(?:bad|worst|wrst|poor|pathetic|useless|horrible|terrible|not good|very bad|third class|worst (?:service|app|company|ever)|bad (?:service|app|experience)|very poor|waste|rubbish|disgusting)\W*(?:service|app|company|experience|ever)?\W*$|not (?:very )?happy|disappointed|dissatisfied|bad experience|worst (?:experience|service|app|company)|poor (?:experience|service)",
    # ---- positives
    "pos_quality_pro": r"(?<![A-Za-z])(?:excellent|amazing|awesome|outstanding|superb|wonderful|fantastic|great (?:service|job|work|experience|app|team)|very good|really good|good (?:work|job|service|quality|experience|professional|staff|app)|best (?:service|app|platform|experience)|professional(?:ly)?|polite|courteous|well[- ]?(?:trained|behaved|mannered)|thorough(?:ly)?|neat(?:ly)?|skilled|knowledgeable|expert|pleasure|appreciat\w+|impress\w+|top[- ]?notch)(?![A-Za-z])|(?<!not )(?<!un)(?<!dis)satisfied|happy (?:with|about)|(?<!not )worth (?:it|the)",
    "pos_punctual": r"on[- ]time|punctual|prompt(?:ly)?|arrived (?:early|on time|right on)|timely|came (?:on time|before time|early|immediately)|quick(?:ly)?|fast service|same day",
    "pos_convenience": r"convenien\w+|hassle[- ]?free|easy to (?:use|book)|easy booking|one[- ]stop|time[- ]?saver|saves? (?:me )?time|go[- ]to\b|user[- ]?friendly|seamless|smooth(?:ly)?|transparent|reliable|trust(?:ed|worthy)|peace of mind|life (?:easy|easier)",
    "pos_support_resolution": r"(?:support|customer care|customer service|team|company)\b.{0,40}(?:resolved|helpful|prompt|responsive|quick|good|great|excellent|supportive|compensat\w+)|(?:resolved|compensat\w+|refunded|replaced (?:it )?free|free of cost|apologi[sz]ed)|issue (?:was |got )?(?:resolved|fixed|sorted)",
}
# ---- refinements after reading random hits for each code (precision spot-check)
ISSUES.update({
    "late": r"\blate\b|delay(?:ed|s)?\b|not on time|not punctual|hours? late|kept (?:us |me )?waiting|too long to|not (?:in|on) time|not timely|(?:came|arrived|reached)\b.{0,15}(?:late|after)",
    "price_high": r"(?:rates?|pricing|prices?|tariff|fares?|fees?)\b.{0,30}(?:high|higher|concern|review|practical|abnormal|unreasonable|steep|too|more than|much|increas\w+|hik\w+|doubl\w+|tripl\w+|more affordable|not affordable)|(?:high|higher|abnormal|exorbitant)\b.{0,12}(?:rates?|pricing|prices?|tariff|charges?|fees?)|expensive|costly|overpriced|over[- ]priced|too (?:high|much|costly|expensive)|exorbitant|(?:increas|hik|rais)\w*\b.{0,15}(?:price|rate|charge)|pricey|daylight robbery|concern about (?:the )?(?:rates?|price|pricing)|review (?:the )?pric\w+|\b(?:cost|charges?)\b.{0,25}(?:very |too |so )?(?:high|much|difficult to afford)|\b\dx\b.{0,20}local|times (?:as )?(?:much )?(?:compare\w* )?(?:to |than |as )?(?:the )?local|(?:difficult|hard) to afford|(?:price|rate)s? (?:is|are) (?:very |too |bit )?(?:high|more)",
    "warranty_rework": r"warrant\w*\b.{0,70}(?:not|denied|refus\w+|void\w*|reject\w+|evad\w+|honou?r\w*|didn[’']?t|issue|problem|expire\w*|claim)|(?:claim|claimed|claiming)\w*\b.{0,25}warrant|no warranty|(?:not|isn[’']?t|aren[’']?t) (?:under|covered)|re-?visit|re-?service|follow[- ]?up (?:service|visit)|issue (?:came|came back|reoccur\w*|re-?appear\w*|repeat\w*|persist\w*)|(?:problem|issue|leak\w*|cooling|dirt\w*|stain\w*|cockroach\w*|pests?) (?:again|persist\w*|still|remain\w*|returned|came back)|again (?:after|within)|not working (?:after|again)|stopped working (?:after|within)|within (?:a )?(?:week|few days|\d+ days) (?:of|after) (?:the )?(?:service|repair|cleaning|visit|installation|work)",
    "missing_service_request": r"(?:please|plz|pls|kindly|should|must|can you|could you|would be (?:great|nice|good)|wish|hope you|request (?:you )?to|suggest\w*)\b.{0,40}\b(?:add|provide|include|introduce|start|launch|offer|bring|allow|enable)\b|no (?:option|provision|facility) (?:for|to|of)|there is no (?:option|service|provision)|not (?:listed|available) (?:in|on|under) (?:the )?(?:app|menu|list)|doesn[’']?t (?:have|offer|provide|include) (?:a |any |an )?(?:option|service)|(?:don[’']?t|do not) (?:have|offer|provide) (?:a |any |an )?(?:option|service)|classic (?:service|option|segment)|single bathroom|1 bathroom|pay after|cash (?:option|on delivery|payment)|\bcod\b|(?:wish|want|need|looking for) (?:a |an )?(?:service|option) (?:for|to)",
    "coverage_gap": r"not (?:available|provided|serviced?|offered|operational) (?:in|at|for) (?:my|our|this|the) (?:area|city|location|town|locality|region|society|pin)|(?:isn[’']?t|is not|not|aren[’']?t|are not|unavailable) (?:yet )?(?:available|serviceable|operational|offered) (?:here|there|in my|in our|at my|at our|in the area)|not serviceable|\bexpand\w*|more (?:cities|areas)|tier[- ]?(?:2|3|ii)|bring (?:this |these |the )?(?:service|services)|start (?:this |these |the |your )?(?:service|services)|doesn[’']?t (?:work|operate|serve|cover|cater) (?:here|in)|services? (?:is|are) not (?:yet )?available|not there at few locations|(?:no|not) (?:service|services|professional|professionals) (?:in|at) (?:my|our) (?:area|city|location)|not available here",
    "app_friction": r"\bapp\b(?: is| was| keeps| has| still| does not| doesn[’']?t)?(?: very| so| too| really)? ?(?:not (?:working|opening|loading|responding|friendly|user)|crash\w*|hang\w*|slow|buggy|glitch\w*|freez\w*|stuck|lag\w*|poor|bad|confusing|outdated|broken)|crash\w*|glitch\w*|(?<!bed )(?<!bed-)\bbugs?\b|\bfreez(?:e|es|ing|ed)\b|something went wrong|black screen|otp (?:not|doesn|issue|problem)|location (?:issue|problem|error|fetch\w*)|status bar|overlap\w*|(?:not|isn[’']?t|un)\W*(?:very )?user[- ]?friendly|(?:can[’']?t|cannot|unable to|not able to) (?:book|cancel|edit|reschedule|check ?out)\b|app (?:experience|interface|design)|(?:no|limited) (?:contact us|communication)",
})
# ---- second precision pass (weak codes found when scoring 8 random hits per code)
ISSUES.update({
    "slot_unavailable": r"\bno slots?\b|slots? (?:are |is |were )?(?:not|never|unavailable|full|hardly)|(?:not|never|unable to|can[’']?t|couldn[’']?t|cannot) (?:get|find|book|see|able to book)\b.{0,25}(?:slot|appointment|professional)|no (?:professional|partner|technician|beautician)s? (?:available|assigned)|professionals? (?:are |is )?(?:unavailable|busy)|fully booked|all (?:our )?professionals are busy|not able to book|unable to book|(?:no|zero) (?:availability|vacancy)|take too long for the slot",
    "damage_theft": r"damag(?:e|ed|es|ing)\b.{0,40}(?:my|our|the|ac|machine|tv|fridge|geyser|chimney|floor|wall|tile|furniture|sofa|property|appliance|unit|part|panel|compressor|motherboard)|(?:my|our|the) (?:ac|machine|tv|fridge|geyser|chimney|floor|wall|tile|furniture|sofa|property|appliance|unit|panel|compressor|motherboard)\b.{0,30}damag|ruin(?:ed)? (?:my|our|the)|(?:technician|professional|they|he|she)\b.{0,25}(?:broke|broken)\b|stolen|theft|\bstole\b|\bsteal\b|short[- ]?circuit",
    "conduct_safety": r"\brude\b|arrogan\w+|misbehav\w+|abus(?:e|ed|ive|ing)\b|harass\w+|threat(?:en|s|ened|ening)?\b|attitude|disrespect\w*|creepy|unsafe|safety (?:concern|issue|risk|harness)|inappropriate|forced (?:me )?(?:to )?(?:give|rate)|(?:ask|asks|asked|asking|force|forced|forcing|pressur\w+)\b.{0,25}(?:5|five)[- ]?(?:\*|star)|personal number|(?:asked|ask) (?:me )?for (?:a )?(?:5|five)|yell\w+|shout\w+|unprofessional (?:behaviou?r|conduct|attitude)",
})
ISSUE_RE = {k: re.compile(v, I | re.S) for k, v in ISSUES.items()}

# ------------------------------------------------------------------ five emergent themes = groupings of the issue codes
THEMES = {
    "T1": ("Unreliable fulfilment: cancellations, no-shows, delays and missing slots", ["cancelled", "rescheduled", "no_show", "late", "slot_unavailable"]),
    "T2": ("Price, fees and policy rigidity", ["price_high", "fees_charges", "overcharge_upsell"]),
    "T3": ("Support access, refunds and problem resolution (incl. warranty and Native after-sales)", ["support_unreachable", "refund_payment", "unresolved", "warranty_rework", "native_after_sales"]),
    "T4": ("Service quality, professional conduct and trust (good and bad)", ["poor_quality", "damage_theft", "conduct_safety", "trust_fraud", "pos_quality_pro", "pos_punctual", "pos_support_resolution"]),
    "T5": ("Coverage gaps, missing services and app friction", ["coverage_gap", "missing_service_request", "app_friction"]),
}


def tag_issues(df):
    for k, rx in ISSUE_RE.items():
        df["i_" + k] = df.text.map(lambda t, rx=rx: bool(rx.search(t)))
    for th, (name, codes) in THEMES.items():
        df["th_" + th] = df[["i_" + c for c in codes]].any(axis=1)
    return df
```

### Notebook code cell 9

```python
#@title Unmet-need and return-signal rules  { display-mode: "form" }
import re

I = re.I | re.S

# ------------------------------------------------------------------ return behaviour
RET_REPORTED = re.compile(
    r"(?:using|used|use|availed|taken|booked|been (?:a )?(?:customer|user))\b.{0,45}(?:since\b|for (?:the )?(?:past |last |almost |nearly |over |more than )?(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten|few|several|many)\s*(?:years?|yrs?|months?)|(?:many|several|multiple|numerous|countless|few|couple of|\d+) times|regularly|frequently|again and again|every (?:month|week|time|day)|(?:more than|over) \d+ times)"
    r"|(?:booked|called|used|availed|taken|hired)\b.{0,25}(?:\d+|two|three|four|five|six|seven|eight|multiple|several|many|numerous) (?:times|services|bookings|occasions)"
    r"|(?:regular|loyal|repeat|long[- ]?time|old|returning|frequent) (?:customer|user|client)|(?:been|am|was) (?:a )?(?:regular|loyal)\b|since (?:its |their )?(?:inception|startup|beginning|the (?:start|beginning)|20\d\d|urban ?clap)|(?:second|third|fourth|2nd|3rd) (?:time|booking|service|visit)|(?:booked|used|called|hired) (?:them|her|him|uc|urban company|urbanclap) again|re-?booked|my go[- ]to|go[- ]to (?:app|platform|place|service)|always (?:book|use|call|prefer|go)|i (?:keep|continue) (?:using|booking)|(?:used|used to use|had used|have used|tried) (?:uc|urban company|urbanclap)\b.{0,25}(?:before|earlier|previously|in the past|last year|in 20\d\d)|(?:in|back in) 20\d\d,? i had used|previous (?:booking|service|experience)s?|earlier (?:booking|service|experience)s?|every (?:other )?(?:month|week)|monthly (?:booking|service|clean)|(?:last|past) (?:\d+|few|several) (?:years|months)", I)
RET_INTENT = re.compile(
    r"(?:will|would|shall|'ll|going to|gonna|plan to|definitely|surely|certainly)\b.{0,25}\b(?:book|use|call|hire|prefer|choose|ask for|take|avail)\b.{0,30}(?:again|more|in (?:the )?future|next time|whenever|for (?:other|more|all|my)|her\b|him\b|them\b|uc\b|urban)"
    r"|(?:book|use|call|hire|choose|prefer|ask for|request) (?:her|him|them) (?:again|only|always|next|every|for)|(?:will|would) (?:definitely |certainly |surely )?(?:be )?(?:back|return)\b|next time (?:also )?(?:i|we) (?:will|would)|keep (?:using|booking)|continue (?:to )?(?:use|using|book|with)|(?:would|will) (?:like|love) to (?:book|use|call|hire|get).{0,20}again|(?:prefer|want|request)\w*\b.{0,20}(?:same|this) (?:professional|person|technician|beautician|lady|guy|partner)|(?:will|would) (?:definitely )?(?:call|ask|prefer|request) (?:her|him) again|will book again|use (?:it|them|this) again|plan to keep", I)
NON_RETURN = re.compile(
    r"(?:never|not|won[’']?t|will not|wouldn[’']?t|shall not|don[’']?t|do not|no longer|no more|can[’']?t|cannot)\b.{0,25}\b(?:book|use|using|call|hire|take|avail|go (?:back|for)|order|trust|purchase|buy|rely|depend|deal|continue)\b.{0,35}(?:again|any ?more|ever|\buc\b|urban|their|them|services|from (?:them|uc|urban)|this (?:app|company|platform)|in (?:the )?future)"
    r"|never again|(?:last|final) time\b.{0,30}(?:using|booking|use|book|taking|with|i)|uninstall(?:ed|ing)?|delet(?:ed|ing) (?:the |my )?(?:app|account)|stopped (?:using|booking|taking|availing)|(?:switch(?:ed|ing)?|shift(?:ed|ing)?|moved?|moving)\b.{0,25}\b(?:to|towards)\b.{0,30}(?:snabbit|pronto|yes ?madam|nobroker|housejoy|justdial|local|another|other|different|someone else|independent)"
    r"|lost (?:a|my|me as a) customer|take (?:my|our) business elsewhere|stop (?:using|booking)|(?:i|we) (?:have|had) (?:now )?(?:stopped|quit|given up)|(?:i|we) (?:am|are|will|would) (?:be )?(?:cancelling|cancelled|canceling) (?:my|our) (?:subscription|membership|plan)|(?:not|never) (?:going|go) (?:to |back to )?(?:use|book|use them|book them|call)", I)
SIGNAL_TRUST = re.compile(r"recommend|trust|reliable|go[- ]?to|loyal|worth|satisf|happy with|impress|appreciat|keep (?:it )?up|thank|best|will think twice|think twice|rethink|alternative|switch|look(?:ing)? for (?:other|another|someone|a better)|avoid|stay away|beware|don[’']?t (?:use|book|go|waste)|do not (?:use|book|go|waste)|better than|compared? (?:to|with)|instead of|local|scam|fraud|cheat|disappoint|never|worst|pathetic|horrible|terrible", I)

# ------------------------------------------------------------------ alternatives
ALTERNATIVES = {
    "Snabbit": r"snabb?it|snapbit",
    "Pronto": r"\bpronto\b",
    "Yes Madam": r"yes ?madam",
    "NoBroker": r"no ?broker",
    "Housejoy": r"house ?joy",
    "Justdial / Sulekha / other directories": r"just ?dial|\bjd\b|sulekha|indiamart|magicbricks|99acres|hometriangle|lifeasy|livspace|homelane|asian paints|deccan clap|billu|onsitego|hi ?care|\bkaya\b|zimmber|toni (?:and|&) guy",
    "Brand / authorised service centre": r"authori[sz]ed (?:service|technician|centre|center)|official(?:ly)? (?:service|technician|centre|center)|service cent(?:re|er)|company (?:technician|service)|(?:samsung|lg|voltas|carrier|daikin|whirlpool|bosch|haier|godrej|kent|aquaguard|livpure|ao smith|atomberg|sharp|hitachi|blue ?star)\b.{0,25}(?:service|technician|support|warranty|centre|center)|brand service",
    "Local / independent professionals": r"\blocal\b.{0,30}(?:technician|mechanic|electrician|plumber|carpenter|painter|repair|market|vendor|shop|service|guy|person|expert|labou?r|barber|salon|parlou?r|masseu\w+|cleaner|ac |maid|contractor|professional|provider)|(?:technician|mechanic|electrician|plumber|carpenter|painter|repair|guy|person|expert)s? (?:from|in) (?:the )?(?:local|nearby|neighbou?rhood|market)|nearby (?:shop|market|salon|parlou?r|technician|mechanic)|independent (?:professional|technician|provider|worker|plumber|electrician|mechanic|painter|cleaner|beautician)|free-?lanc\w+|my (?:regular|usual|own|old|permanent|known) (?:technician|mechanic|plumber|electrician|carpenter|painter|guy|maid|cleaner|beautician|barber|contact)|(?:known|trusted|reliable|personal) (?:technician|mechanic|plumber|electrician|carpenter|painter|guy|contact|person)|direct(?:ly)? (?:from|with) (?:the )?(?:service provider|professional|technician|painter|carpenter)|contact(?:ed)? (?:him|her) directly|personal number|(?:your|their|his|her) own (?:number|contact)|(?:neighbou?rhood|local) (?:shop|vendor|parlou?r|salon|painter|mechanic)|(?:go|went|gone|going) (?:to|for) (?:a )?(?:local|shop|market|parlou?r|salon)",
    "Neighbours / friends / family / colleagues": r"neighbou?r|(?:my |our )?(?:friend|friends|family|colleague|relative|sister|brother|mom|mother|dad|father|husband|wife|cousin|in-?laws?)\b.{0,40}(?:told|suggest|recommend|referr?|use[sd]?|booked|called|got|gave)|(?:recommend|suggest|referr?)\w* (?:by|from) (?:a |my |our )?(?:friend|family|neighbou?r|colleague|relative)|word[- ]of[- ]mouth|referral|ask(?:ed|ing)? (?:around|friends|neighbou?rs)|known (?:people|contacts)",
    "WhatsApp / society / community groups": r"whats ?app|society (?:group|chat|committee|vendor|list)|resident'?s? (?:group|association|welfare)|\brwa\b|facebook (?:group|community)|telegram|community (?:group|recommend)|apartment (?:group|chat)|(?:ask|asked|post|posted) (?:on |in )?(?:reddit|this (?:sub|community)|here)",
}
ALT_RE = {k: re.compile(v, I) for k, v in ALTERNATIVES.items()}
ALT_WHY = {
    "cheaper / better price": re.compile(r"cheap\w*|afford\w*|less (?:price|cost|charge|expensive)|fraction|half (?:the )?(?:price|cost)|lower (?:price|rate|cost)|reasonable|economical|save[sd]? (?:money|\d+)|value for money|budget|(?:price|rate|cost|charge)s? (?:is|are|was|were)? ?(?:low|lower|less|much less)|less than (?:uc|urban)|\d+ ?(?:x|times) (?:less|cheaper)", I),
    "trust / reliability": re.compile(r"trust\w*|reliab\w+|honest|genuine|known|regular|permanent|familiar|dependable|consistent|always (?:comes|come|available|turns)|show[s]? up", I),
    "available / quick": re.compile(r"available|immediate\w*|same day|quick\w*|instantly|right away|no (?:wait|slot)|when (?:needed|required)|on short notice|urgent", I),
    "quality / skill": re.compile(r"better (?:work|quality|service|job)|skill\w*|expert\w*|experienced|quality|thorough|knowledg\w+|specialis\w+", I),
    "personal relationship / accountability": re.compile(r"call (?:him|her) directly|personal number|direct(?:ly)?|own number|phone number|follow[- ]?up|accountab\w+|responsib\w+|stand(?:s)? behind", I),
}

# ------------------------------------------------------------------ triggers (Q2)
TRIGGERS = {
    "Appliance / equipment breakdown or fault": r"not cooling|stopped (?:cooling|working)|not working|(?:ac|fridge|refrigerator|washing machine|geyser|tv|chimney|purifier|laptop|fan|inverter|stove|microwave)\b.{0,30}(?:stopped|not working|issue|problem|broken|dead|died|damage|fault|noise|leak)|short circuit|power (?:cut|tripp)|\bbroke\b|\bbroken\b|dead\b|conked|malfunction",
    "Water / plumbing / leakage emergency": r"leak(?:age|ing|s)?|clog\w*|block(?:age|ed)|seepage|damp(?:ness)?|water (?:logging|tank|supply|pressure)|burst|flush|drain\w*|overflow",
    "Seasonal / weather (summer, monsoon)": r"summer|hot weather|heat\b|monsoon|rain(?:s|y)?\b|humid|winter|season",
    "Festival / occasion / event (Diwali, wedding, party)": r"diwali|deepawali|holi|rakhi|raksha|ganesh|navratri|dussehra|eid|christmas|festiv\w+|wedding|marriage|bridal|engagement|party|birthday|anniversary|baby shower|function|occasion|puja|housewarming|griha ?pravesh|karwa",
    "Moving house / new home / renovation / tenancy": r"mov(?:e|ed|ing)[- ](?:in|into|out)|move-?in|shift(?:ed|ing) (?:to|into|house|flat|home|from)|new (?:flat|home|house|apartment|place)|vacat\w+|new tenants?|\btenants?\b|landlord|\brent(?:ed|ing|al)?\b|renovat\w+|possession|just moved|recently (?:moved|shifted)|before (?:the )?(?:tenants?|moving)|handover",
    "Guests / family visit / elderly or ill family member": r"guests?|relatives? (?:visit|coming)|parents? (?:visit|coming|are coming|staying)|in-?laws?|bed ?ridden|senior citizen|elderly|(?:father|mother|dad|mom)\b.{0,40}(?:visit\w*|ill|unwell|surgery|kidney|health)|pregnan\w+|new ?born|baby",
    "Pests / bad smell / hygiene problem": r"cockroach\w*|bed ?bugs?|termite\w*|\bants\b|pest control|rodent|mosquito\w*|\bsmell\w*|stink\w*|infest\w*|disinfect\w+|sanitis\w+",
    "Time pressure / working schedule (no time to DIY)": r"working (?:professional|couple|women|woman|mother|people|parents)|busy|no time|don[’']?t have time|time[- ]?saver|saves? (?:my )?time|office (?:hours|work|goers?)|work from home|wfh|long hours|dual[- ]income|both (?:of us|work)|job(?:s)?\b.{0,20}(?:time|busy)",
    "Maid / help unavailable (leave) -> substitute": r"maid (?:on|is on|went on|is away|is absent)|(?:regular|usual) (?:maid|help)\b.{0,30}(?:leave|away|absent|vacation|holiday|not coming)|(?:maid|help|cook)s?\b.{0,20}(?:leave|absent|didn[’']?t come|not coming)",
    "Grooming / beauty need tied to an event or personal situation": r"(?:bridal|wedding|party|function|festival|event|occasion|engagement|vacation|trip|tanned|interview)\b.{0,60}(?:facial|waxing|threading|mani|pedi|haircut|hair colou?r|massage|spa\b|salon|makeup|henna|mehndi|laser|de-?tan|bleach|beautician)|(?:facial|waxing|threading|mani|pedi|haircut|hair colou?r|massage|spa\b|salon|makeup|henna|mehndi|laser|de-?tan|bleach|beautician)\b.{0,60}(?:bridal|wedding|party|function|festival|event|occasion|engagement|vacation|trip|tanned|interview)|(?:got|getting|need|want)\w* (?:a |my )?(?:facial|waxing|massage|haircut|manicure|pedicure)",
    "Urgent / same-day need": r"urgent\w*|emergency|asap|immediately|right now|today itself|same[- ]day|at the earliest|as soon as possible|short notice|last[- ]minute (?:need|requirement|booking)",
    "Planned / advance booking / recurring": r"in advance|advance booking|pre-?book\w*|plan(?:ned|ning)? (?:to|for)|schedul\w+ (?:ahead|in advance)|(?:\d+|few|couple of|two|three) days (?:before|prior|in advance|ahead)|recurring|monthly|weekly|annual|yearly|\bamc\b|subscription|plan\b.{0,20}(?:month|week)|regular(?:ly)? (?:clean|service|servicing)|every (?:month|week|year|\d+ months)|periodic\w*",
    "Product purchase decision (Native purifier / lock)": r"planning to (?:buy|purchase|get)|thinking (?:of|about) (?:buying|getting)|(?:buy|buying|purchase|purchasing|shortlist\w*|considering)\b.{0,40}(?:purifier|\bro\b|native|smart lock|lock)|which (?:water )?purifier",
}
TRIG_RE = {k: re.compile(v, I) for k, v in TRIGGERS.items()}

# ------------------------------------------------------------------ household type (Q7) and discovery channel (Q7)
HOUSEHOLD = {
    "Lives alone / single / bachelor": r"live[sd]? alone|living alone|stay(?:ing)? alone|staying by myself|single (?:woman|man|girl|guy|person|female|male)|bachelor|\bsolo\b|(?:i am|i'm) (?:a )?(?:single|alone)|someone living alone",
    "Elderly parents / senior / bedridden at home": r"senior citizens?|elderly|old age|bed ?ridden|(?:my |our )?(?:parents?|father|mother|dad|mom|grand(?:mother|father|parents?))\b.{0,40}(?:alone|stay|live|old|senior|ill|unwell|home)|aged (?:parents?|mother|father)",
    "Family with children / newborn": r"\bkids?\b|children|child\b|toddler|infant|new ?born|baby|my (?:son|daughter)|school",
    "Pet owners": r"\bdogs?\b|\bcats?\b|\bpets?\b|puppy|kitten|doggo",
    "Working professionals / dual-income / women who work": r"working (?:professional|couple|women|woman|mother|people|parents)|dual[- ]income|both (?:of us|work)|tech professional|office[- ]?goers?|corporate|working girl|\bit professional\b|work(?:ing)? from home|wfh|salaried",
    "Renters / tenants / landlords / PG": r"\brent(?:ed|ing|al)?\b|tenant|landlord|\bpg\b|hostel|flat owner|giving out my flat",
    "Newcomers to a city / moved recently": r"new to (?:the |this )?(?:city|town|area)|just moved|recently (?:moved|shifted|relocated)|moving (?:to|into) (?:a )?(?:new|the)|shifted from|relocat\w+|moved from",
    "NRI / living abroad (booking for family in India)": r"\bnri\b|live[sd]? (?:abroad|overseas|in the (?:uk|us|usa))|(?:from|in) (?:the )?(?:uk|singapore|dubai|usa|u\.s\.|australia|canada)\b|out of (?:the )?country|parents? (?:in|live in) (?:india|delhi|pune)|booking (?:for|on behalf of) (?:my )?(?:parents|mother|father|mom|dad|family)|(?:for|of) my (?:mother|father|mom|dad|parents|in-?laws)\b.{0,30}(?:booked|booking|book)",
    "Small flat (1 BHK / studio)": r"\b1 ?bhk\b|\bstudio\b|\b1bhk\b|one bhk|single room|1 bathroom|single bathroom|one bathroom",
    "Large flat / villa / office (3+ BHK, duplex, office)": r"\b[3-9] ?bhk\b|duplex|villa|bungalow|penthouse|\boffice\b|\bshop\b|guest house|institute|society of|group of \d+ families|\b\d{4} ?sq ?ft",
    "Gated society / apartment building rules": r"gated (?:society|community)|society (?:rule|not allow|allow|security|guard|permission|policy)|apartment (?:building|complex|society)|(?:security|guard)\b.{0,30}(?:allow|stop|permission|entry|smok)|high[- ]?rise|(?:8|10|\d+)(?:th|st|nd|rd)? floor",
    "Women customers / female-professional preference": r"(?:female|woman|women|lady|ladies)\b.{0,25}(?:professional|technician|beautician|therapist|masseu\w+|worker|partner|staff|only|preferred|safe)|(?:i am|i'm|as) a (?:woman|female|girl|lady)|\bf\d{2}\b|\d{2} ?f\b|for women|women[’']?s? safety|safe(?:ty)? (?:for|as) a (?:woman|female)",
}
HH_RE = {k: re.compile(v, I) for k, v in HOUSEHOLD.items()}
DISCOVERY = {
    "Friends / family / colleague referral": r"(?:friend|family|colleague|relative|neighbou?r|sister|brother|mom|mother|dad|father|husband|wife|cousin)s?\b.{0,40}(?:told|suggest\w*|recommend\w*|referr\w*|use[sd]?|introduced|said)|(?:recommend\w*|suggest\w*|referr\w*|told|introduced)\b.{0,15}(?:by|from|me by|me to) (?:a |my |our )?(?:friend|family|neighbou?r|colleague|relative|sister|brother|cousin)|word[- ]of[- ]mouth|came to know (?:from|through|about)|heard (?:about|of|from)|referral (?:code|link|bonus)",
    "Advertising / social media / YouTube": r"(?:saw|seen|watch\w*|came across|noticed|heard)\b.{0,25}(?:ads?\b|advert\w*|video|reel|youtube\w*|banner|hoarding|billboard|instagram|influencer\w*|youtuber\w*)|(?:ads?\b|advert\w*|youtuber\w*|youtube\w*|influencer\w*|instagram|reels?)\b.{0,50}(?:made me|lured|attract\w+|convinc\w+|promot\w+|showed|said|claim\w*|promis\w+)|(?:handout|signboard|pamphlet|hoarding|billboard)s?|(?:youtubers?|influencers?)\b.{0,30}prais\w+|great marketing",
    "Search / reviews / app store / Reddit": r"google(?:d| search| reviews?)|searched|search(?:ing)? (?:for|on)|(?:read|saw|seen|checked|looked at) (?:the |some |many |a lot of )?(?:reviews?|ratings?)|reviews? (?:on|in|from) (?:reddit|google|play|app)|(?:play|app) store|rating (?:of|on) (?:the )?app|(?:saw|read|found|came across|seen)\b.{0,25}reddit|reddit (?:reviews?|posts?)|quora|top result|first result",
    "Marketplace / retail partner (Amazon, Flipkart) for Native products": r"(?:bought|ordered|purchased|got|buy|order)\b.{0,40}(?:from|on|via|through) (?:amazon|flipkart)|(?:amazon|flipkart)\b.{0,40}(?:native|purifier|\bro\b)|native\b.{0,60}(?:amazon|flipkart)",
    "Offer / first-booking discount / membership promotion": r"first[- ]?(?:booking|time) (?:offer|discount)|new user (?:offer|discount)|introductory|launch offer|welcome offer|coupon|discount (?:code|offer)|cashback|referral (?:code|bonus)|(?:attractive|great|good) offers?|lured|plus membership|\bsale\b|promotional",
    "Society / apartment partnership / on-ground promoters": r"(?:stall|booth|kiosk)s?\b.{0,60}(?:society|apartment|building|complex|mall|uc|urban)|(?:uc|urban company|urbanclap)\b.{0,40}(?:stall|booth|kiosk)|rep(?:resentative)?s? (?:came|visited)\b.{0,30}(?:society|apartment|building|complex|home)|(?:society|apartment|building|complex)\b.{0,30}(?:stall|booth|kiosk|promot\w+)",
}
DISC_RE = {k: re.compile(v, I) for k, v in DISCOVERY.items()}

# ------------------------------------------------------------------ unmet needs (Q8): explicit asks and recurring gaps
NEEDS = {
    "Reachable human support (call/phone/helpline instead of bot)": r"(?:no|not|without|lack of|need|want|provide|add|require|missing|absence of)\b.{0,30}(?:human|helpline|phone|call(?:ing)? (?:option|facility|number|support)|contact (?:number|us|option)|customer care number|toll[- ]?free|real person|live (?:chat|support|agent)|talk to|speak to|executive)|(?:ai|bot|chatbot)\b.{0,40}(?:useless|no help|doesn[’']?t|cannot|can[’']?t|frustrat\w+|loop|repeat\w*|template|generic|dumb|stupid|waste)|(?:can[’']?t|cannot|unable to|not able to|difficult to|impossible to)\s+(?:talk|speak|reach|contact|connect|call)",
    "Upfront total price / no surprise charges": r"hidden (?:charge|fee|cost)|all (?:the )?charges (?:before|upfront|up front)|(?:total|final) (?:price|cost|amount|bill)\b.{0,40}(?:show|display|mention|before|upfront|include|differ|more|double)|(?:price|rate|amount)s? (?:shown|displayed|mentioned|quoted)\b.{0,50}(?:differ|different|but|more|extra|later|then|after)|extra (?:charge|money|amount)\b.{0,30}(?:after|later|at the time)|(?:amount|rate|price)\b.{0,25}(?:including|inclusive of|incl\.?) (?:tax|gst)|(?:bill|invoice)\b.{0,25}(?:break[- ]?up|mismatch|match|differ)|price (?:change|changed|keeps changing|going up and down)|transparen\w+",
    "Reliable arrival: no last-minute cancellation, ETA, alternate professional": r"(?:no|without|prior|advance|any) (?:information|intimation|notice|intimate|update|alert)|(?:alternate|alternative|replacement|another) (?:professional|partner|person|technician|slot)|(?:track|tracking|eta|live location)\b|(?:inform|intimat\w+|notif\w+|updat\w+)\b.{0,25}(?:late|delay|cancel|reschedul)|(?:cancel|reschedul)\w*\b.{0,25}(?:without|no) (?:information|intimation|notice|consent|asking|informing)|compensat\w+\b.{0,25}(?:late|delay|cancel|wait)",
    "Fair cancellation / reschedule policy": r"cancellation (?:fee|charge|policy)|(?:charged|charge|penalty|fine)\b.{0,30}(?:cancel|reschedul)|(?:cancel|reschedul)\w*\b.{0,30}(?:charged|charge|fee|penalty|fine)|penalty|pay (?:a )?fine",
    "Choice of professional / continuity / gender / language": r"(?:choose|select|pick|choice of|same|particular|specific|preferred)\b.{0,15}(?:professional|partner|person|technician|beautician|therapist|girl|lady|guy)|(?:female|woman|women|lady)\b.{0,15}(?:technician|professional|only|installer|worker)|(?:hindi|local language|kannada|tamil|telugu|marathi|bengali|english)\b.{0,40}(?:speak|know|understand|professional|helper|partner|language)|(?:professional|helper|partner)s?\b.{0,40}(?:language|speak|understand)|male (?:when|but)|kept giving me a male",
    "Flexible / granular packages (single bathroom, add-ons, partial jobs, longer duration)": r"single bathroom|1 bathroom|one bathroom|(?:only|just)\b.{0,15}(?:floor|window|fan|kitchen|balcon|sofa|chimney) (?:clean|wash)|smaller (?:chunks|job|package)|(?:add[- ]?on|extend|extension|increase)\b.{0,20}(?:time|duration|service|hour)|(?:time|duration)\b.{0,20}(?:extend|extension|increase|more)|odd jobs|small jobs?|miscellaneous|custom(?:i[sz]ed)? (?:request|requirement|package)|minimum (?:order|booking|amount|cart)|min(?:imum)? (?:order|booking)|hourly|per hour basis|not (?:listed|included) in (?:the )?(?:app|menu|package)|(?:service|option)s? (?:not|isn[’']?t) (?:available|listed)",
    "Payment flexibility (pay after service / cash / COD)": r"pay (?:after|post|on completion)|payment after (?:service|work|job)|cash (?:option|payment|on delivery|mode)|\bcod\b|no cash|advance payment|prepaid\b.{0,30}(?:not|why|forc|mandat)|upfront payment|pay (?:later|at the end)",
    "Warranty / rework / after-sales that is honoured": r"warrant(?:y|ies)\b.{0,70}(?:not|denied|refus\w+|void\w*|reject\w+|evad\w+|honou?r\w*|didn[’']?t|issue|problem|claim)|(?:claim|claimed|claiming)\w*\b.{0,25}warrant|after[- ]?sales?|revisit|re-?service|rework|follow[- ]?up (?:visit|service)|(?:redo|redone|do (?:it )?again) (?:the )?(?:work|job|service)|(?:no|not)\b.{0,15}(?:post[- ]service|after service) (?:support|follow)",
    "Fast, fair refunds and payment-failure recovery": r"refund|money (?:deducted|debited|stuck|not (?:returned|received))|payment (?:failed|deducted|stuck|issue)|charged (?:twice|double)|double payment|not (?:been )?refunded|amount (?:deducted|debited)",
    "Professional training / tools / consumables / 2-person jobs": r"(?:train(?:ing|ed)?|untrained|skill\w*)\b.{0,30}(?:professional|staff|partner|helper|technician|worker|needed|required|improve|provide|give)|(?:professional|staff|partner|helper|technician|worker)s?\b.{0,30}(?:untrained|not (?:well )?trained|lack\w* (?:training|skill)|need\w* training)|(?:tools?|equipment|consumables?|chemicals?|machine|ladder|vacuum|gloves?|mask|degreaser|scrubber|napkin|cloth)\b.{0,40}(?:not|didn[’']?t|doesn[’']?t|without|provide|bring|carry|brought|lack|missing|insufficient|inadequate)|(?:two|2|more than one|minimum two)\b.{0,20}(?:person|people|cleaners?|workers?|professionals?|helpers?)",
    "New service categories requested": r"(?:please|plz|pls|kindly|should|can you|could you|wish|want|need|hope)\b.{0,50}(?:cook(?:ing)?|chef|food|tiffin|car wash|car cleaning|gardener|gardening|garden|heat pump|home organi[sz]\w+|declutter\w*|mehndi|henna|blender|mixer|window ac|cctv|wall panel\w*|interior|bridal|makeup|hair spa|protein treatment|tank cleaning|dry ?clean\w*|laundry|ironing|pressing|packers|movers|vet\b|pet (?:groom|care)|physio\w*|nurse|elder care|tutor|yoga|fitness|trainer|coach|photograph\w*)|why can[’']?t (?:urban company|uc)\b.{0,30}(?:start|add|offer|provide)|(?:don[’']?t|doesn[’']?t|does not|do not) (?:have|offer|provide|do)\b.{0,25}(?:cook|food|dish|car wash|garden|window ac|heat pump|dry ?clean)|not (?:listed|available)\b.{0,15}(?:window ac|cook|geyser|capacitor|heat pump)",
    "Coverage in tier-2/3 cities and more localities": r"tier[- ]?(?:2|3|ii)|(?:not|isn[’']?t|aren[’']?t|no)\b.{0,25}(?:available|serviceable|present|operational|service|services|covered|cover)\b.{0,25}(?:in|at|near) (?:my|our|this|the) (?:area|city|town|location|locality|sector|colony)|(?:please|plz|pls|kindly)\b.{0,30}(?:expand|extend|start|bring|launch)\b.{0,40}(?:city|town|area|locality|location|zone|pincode|sector)|\bexpand\w*\b.{0,30}(?:service|city|area|zone)|(?:service|services)\b.{0,25}(?:not|isn[’']?t) (?:yet )?(?:available|provided|present)\b.{0,25}(?:here|there|in)|(?:udaipur|bilaspur|calicut|malappuram|warangal|mohali|kharar|bhopal|nashik|coimbatore|jaipur|lucknow|raipur|ludhiana|mandsaur|dombivli|palava|thudiyalur|pitampura|kalyani)\b",
    "App usability, location handling and information clarity": r"(?:app|application)\b.{0,50}(?:confus\w+|not (?:clear|friendly|user)|difficult|complicated|slow|crash\w*|glitch\w*|bugs?\b|stuck|hang\w*|lag\w*|location)|(?:location|address)\b.{0,40}(?:wrong|error|issue|problem|stuck|fetch\w*|not (?:detect|correct|work)|keeps)|(?:not|isn[’']?t|unclear|confus\w+)\b.{0,25}(?:clear|mention\w*|detail\w*|inclusion|exclusion|what is (?:included|covered))|package (?:details|inclusions?|exclusions?)|(?:no|not)\b.{0,15}(?:detail|description|information)",
    "Rating pressure / tip prompts from professionals": r"(?:ask|asks|asked|asking|force|forces|forced|forcing|pressur\w+|beg\w*|demand\w*)\b.{0,30}(?:5|five)[- ]?(?:\*|star|stars)|(?:5|five)[- ]?(?:\*|star|stars?)\b.{0,30}(?:ask|asks|asked|asking|force|forced|forcing|pressur\w+|beg\w*)|(?:ask|asks|asked|asking|force|forced|forcing|pressur\w+|beg\w*)\b.{0,15}(?:rating|ratings|review|tip|tips)|tip(?:s|ping)?\b.{0,30}(?:added|forced|automatic\w*|mandatory|prompt|why)|rating immediately",
}
NEED_RE = {k: re.compile(v, I) for k, v in NEEDS.items()}
```

### Notebook code cell 10

```python
t0 = time.time()
df = tag_issues(df)
for k, rx in NEED_RE.items():
    df["nd_" + k] = df.text.map(lambda t, rx=rx: bool(rx.search(t)))
flagged = int(df[[c for c in df.columns if c.startswith("i_")]].any(axis=1).sum())
stage("problems", "Read: problems and needs", "tag_issues()", f"{flagged} of {len(df)} reviews raise at least one coded problem or praise", t0,
      f"{len(ISSUES)} problem and praise codes · {len(NEEDS)} need types")
print(f"{flagged} of {len(df)} reviews match at least one problem or praise code")
```

### Return / Non-Return
Every review is placed as **Return** (likely to book again), **Non-Return** (unlikely to) or **Insufficient Evidence**, together with *how* that was decided:
**Stated** (said in the first person), **Signalled** (advises others against the app, mentions switching, distrust, or recommends with trust) or **Inferred** (sentiment and star rating). These are **predictions from public text, not observed repeat bookings**.
For the preloaded dataset the analyst-read labels are used where they exist; for your own CSV the phrase rules and the sentiment decide.

### Notebook code cell 11

```python
#@title Hand-checked labels for the built-in dataset  { display-mode: "form" }
import re

ER_REPORTED = """CC-0039 CC-0113 GP-0329 GP-0468 GP-0588 GP-0746 GP-0826 GP-0844 GP-0867 GP-0942 GP-1004 GP-1043 GP-1044 GP-1233 GP-1269 GP-1273 GP-1309
GP-1404 GP-1412 GP-1427 GP-1452 GP-1511 GP-1625 GP-1092 GP-0766 PC-0006 PC-0027 PC-0040 PC-0107 PC-0108 PC-0148 PC-0151 RD-0017 RD-0165 RD-0181 RD-0229
GP-0616 GP-0775 GP-1223 GP-1276 RD-0053 PC-0150 RD-0112 RD-0251 PC-0125""".split()
ER_INTENT = "GP-0081 GP-0085 GP-0550 GP-0564 GP-0609 GP-0640 GP-0830 GP-0939 GP-1327".split()
ENR = "CC-0064 GP-0370 GP-0435 GP-0452 GP-0621 GP-1245 GP-1319 PC-0019 PC-0046 PC-0053 PC-0071 PC-0116 PC-0122 PC-0123 PC-0124 PC-0161 PC-0113 PC-0126 RD-0125".split()
# reviewers who say they had been repeat customers before leaving / or who are loyal but unhappy
ENR_PRIOR_REPEAT = set("CC-0064 GP-0435 PC-0122 PC-0123 PC-0124 PC-0113 RD-0125 PC-0046".split())

WARN = re.compile(r"(?:don[’']?t|do not|never|stay away|avoid|beware|not to|would not recommend|do not recommend|don[’']?t recommend|not recommend|think twice|be aware|careful)\b.{0,30}(?:use|book|buy|go|trust|waste|rely|call|take|purchase|recommend|before|ever)|avoid (?:at all|like)|stay away|think twice|beware|please be aware|never use|never ever", re.I)
SWITCH = re.compile(r"alternative|look(?:ing)? for (?:other|another|someone|a better)|look elsewhere|seek services elsewhere|will stop booking|forced to seek|(?:go|going|went) (?:for|with|to) (?:a )?(?:local|other|another)|local (?:provider|technician|mechanic|market|guy|vendor|expert)|other apps?|snabbit|pronto|yes ?madam|nobroker|housejoy|better than (?:uc|urban)|instead of (?:uc|urban|booking)|(?:not|never) (?:going|go) to (?:use|book)|rather (?:use|go|call|hire)|shift(?:ing)? back", re.I)
TRUST_POS = re.compile(r"recommend|trust(?:ed|worthy)?|reliable|go[- ]?to|loyal|worth|satisf|happy with|impress|appreciat|keep (?:it )?up|thank|best|excellent|great|amazing|good", re.I)
DISTRUST = re.compile(r"don[’']?t trust|not trust|no trust|distrust|scam|fraud|cheat|dishonest|liar|loot|fake|robb|mislead|theft|stole|stolen|abus|harass", re.I)


def classify_return_curated(rid, text, sentiment):
    if rid in ENR:
        return "Explicit Non-Return", ("previously a repeat customer" if rid in ENR_PRIOR_REPEAT else "states will not return / has switched / uninstalled")
    if rid in ER_REPORTED:
        return "Explicit Return", "reports repeat or ongoing use"
    if rid in ER_INTENT:
        return "Explicit Return", "states intent to book again / prefers same professional"
    wc = len(re.findall(r"\w+", text))
    if WARN.search(text): return "Behavioural Signal", "warns others / advises against using"
    if SWITCH.search(text): return "Behavioural Signal", "switching intent or comparison with alternatives"
    if wc >= 8 and DISTRUST.search(text): return "Behavioural Signal", "distrust / safety or honesty concern"
    if wc >= 8 and sentiment == "Positive" and TRUST_POS.search(text): return "Behavioural Signal", "satisfaction / trust / recommendation (no repeat stated)"
    if wc >= 8 and sentiment in ("Negative", "Mixed"): return "Behavioural Signal", "dissatisfaction (no non-return or switching stated)"
    return "Insufficient Evidence", "no repeat or non-return information"


# ---- round 2 (new Play Store positive reviews, each read by hand): first-person repeat use / intent to book again -------------------
ER_REPORTED.extend(f"GP-{n}" for n in "1729 1742 1745 1784 1794 1862 1907 1975 1980 1988 2021 2033 2038 2052 2060 2065 2079 2114 2128 2139 1932 1828 2037 1844".split())
ER_INTENT.extend(f"GP-{n}" for n in "1746 1753 1837 1874 1827 2012 1774 1668 1853 1895 1910 1921 2049 2072 2140".split())
```

### Notebook code cell 12

```python
#@title Return / Non-Return decision rules  { display-mode: "form" }
import pandas as pd


def behaviour_classify(legacy_class, legacy_sub, sentiment, rating):
    """Returns (return_class, basis, confidence, reason)."""
    if legacy_class == "Explicit Return":
        return "Return", "Stated", "High", legacy_sub
    if legacy_class == "Explicit Non-Return":
        return "Non-Return", "Stated", "High", legacy_sub
    if legacy_class == "Behavioural Signal":
        if legacy_sub.startswith("warns others"):
            return "Non-Return", "Signalled", "Medium", "advises others not to use the app"
        if legacy_sub.startswith("switching"):
            return "Non-Return", "Signalled", "Medium", "mentions switching to or comparing with alternatives"
        if legacy_sub.startswith("distrust"):
            return "Non-Return", "Signalled", "Medium", "expresses distrust or a safety/honesty concern"
        if legacy_sub.startswith("satisfaction"):
            return "Return", "Signalled", "Medium", "expresses satisfaction, trust or recommends"
    r = None if rating is None or pd.isna(rating) else float(rating)
    if sentiment == "Positive":
        if r is not None and r <= 2:
            return "Insufficient Evidence", "Inferred", "Low", "positive wording but a low star rating"
        return "Return", "Inferred", ("Medium" if r is not None and r >= 4 else "Low"), "positive experience"
    if sentiment == "Negative":
        if r is not None and r >= 4:
            return "Insufficient Evidence", "Inferred", "Low", "negative wording but a high star rating"
        return "Non-Return", "Inferred", ("Medium" if r is not None and r <= 2 else "Low"), "negative experience"
    if r is not None and r >= 4:
        return "Return", "Inferred", "Low", f"{sentiment.lower()} wording with a high star rating"
    if r is not None and r <= 2:
        return "Non-Return", "Inferred", "Low", f"{sentiment.lower()} wording with a low star rating"
    return "Insufficient Evidence", "None", "Low", "no clear positive or negative signal"
```

### Notebook code cell 13

```python
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
```

## Step 4 · Group
The problem codes are grouped into **five themes**, so recurring patterns stand out from one-off complaints. A review can belong to more than one theme, so the shares overlap.

### Notebook code cell 14

```python
t0 = time.time()
th_n = {t: int(df["th_" + t].sum()) for t in THEMES}
need_n = {k: int(df["nd_" + k].sum()) for k in NEEDS}
theme_table = pd.DataFrame([dict(theme=t, name=THEMES[t][0], reviews=th_n[t], share=f"{100 * th_n[t] / N:.1f}%",
                                 negative=f"{100 * (df.loc[df['th_' + t], 'sentiment_label'] == 'Negative').mean():.0f}%") for t in THEMES]).sort_values("reviews", ascending=False)
stage("themes", "Group into themes", "THEMES", f"{len(THEMES)} themes", t0, "; ".join(f"{t} {n}" for t, n in th_n.items()))
print("Most frequent unmet needs:", ", ".join(f"{k.split(' (')[0]} ({v})" for k, v in sorted(need_n.items(), key=lambda kv: -kv[1])[:4]))
theme_table
```

## Step 5 · Prioritise
Nine product opportunities are defined from the problems and needs above. Score (0 to 1) = **25%** how many reviews mention it, **20%** how unhappy they are, **20%** how strong the evidence is (volume and number of sources), **20%** the link to leaving signals, **15%** an analyst impact judgement (a hypothesis). Each opportunity carries a product-manager brief; its counts come from the data, its proposals and root causes are hypotheses.

### Notebook code cell 15

```python
#@title Product-manager briefs for the nine opportunities { display-mode: "form" }
PM = {
    "O1": {
        "problem": "A confirmed booking is cancelled, rescheduled, late or never attended, and the customer has already arranged their day around the slot. Recovery is manual: they rebook from scratch, sometimes after paying a fee.",
        "who": "Customers booking time-bound services (AC, cleaning, salon at home), especially first-time customers who have no history with the platform.",
        "why_it_happens": ["A booking is accepted before a professional has actually committed to the slot.", "Professionals can cancel late at little cost, and there is no live arrival status.", "When a provider cancels there is no automatic replacement; the customer has to start again."],
        "proposal": [
            {"title": "Confirm before you charge", "what": "Show the named professional and arrival window at confirmation; treat a booking as confirmed only when a professional has accepted."},
            {"title": "Two-way confirmation and live ETA", "what": "Professional confirms the morning of the job; the customer sees live status and gets a proactive alert on any delay (a customer asked for exactly this)."},
            {"title": "Automatic recovery", "what": "If a professional cancels or is late beyond a threshold, auto-offer the next available professional or a priority reschedule, plus a goodwill credit that applies to the next booking."},
            {"title": "No customer penalty for provider failure", "what": "Waive every fee when the cancellation is not the customer's; add reliability to professional scoring and assignment."}],
        "repeat_mechanism": "A failed first booking is the earliest and cheapest point to lose a customer. A fast, visible recovery turns a failure into a reason to trust the platform, which should raise the chance of a second booking (hypothesis: compare 90-day repeat for first bookings that were late or cancelled and recovered vs not recovered).",
        "success": "More bookings fulfilled on the first scheduled slot, faster replacement after a provider cancellation, and a smaller repeat-rate gap between customers whose first booking failed and those whose first booking went well.",
        "watch_out": "Professional supply and earnings: stricter cancellation rules can push professionals away; credits add cost.",
        "effort": "M", "effort_note": "Product plus operations; the confirm-first and ETA changes are the core build.",
    },
    "O2": {
        "problem": "When something goes wrong, customers cannot reach a person. The bot repeats itself, there is no phone number, tickets are closed without a reply, and nobody owns the problem, so customers chase for days.",
        "who": "Any customer after a failed or disputed booking; most acute for high-value services and Native purifier owners.",
        "why_it_happens": ["Support is designed bot-first to deflect volume, with no easy exit to a human.", "Tickets are closed by timers rather than by the customer confirming resolution.", "First-line agents lack authority to refund or arrange a redo, so cases bounce between teams."],
        "proposal": [
            {"title": "A person on request", "what": "After one bot exchange, or at once for a paid booking issue, offer a callback within a stated time. Show the phone or chat option in the booking screen."},
            {"title": "One case, one owner", "what": "A single case ID with a named owner, visible status and deadline in the app; a case closes only when the customer confirms or a clear resolution is recorded."},
            {"title": "Empowered first contact", "what": "Let first-line agents approve refunds, redos and goodwill credits up to a cap so most problems end in one contact."},
            {"title": "Reach out first", "what": "After a cancelled, late or very low-rated job, contact the customer proactively before they complain, and check back after resolution."}],
        "repeat_mechanism": "The experience of getting a problem fixed seems to decide whether customers stay, more than the original failure itself. Fast, human resolution should keep customers who would otherwise leave after a single failure (hypothesis: compare repeat rate of customers who complained and were resolved at first contact vs those who were not).",
        "success": "Customers reach a human quickly, most complaints end in one contact, few cases are reopened, and customers who complained rebook at a rate close to those who did not.",
        "watch_out": "Support cost per ticket rises; authority limits need fraud controls.",
        "effort": "L", "effort_note": "Operating-model change as much as product: staffing, tooling and agent authority.",
    },
    "O3": {
        "problem": "Money is deducted without a booking, refunds arrive late or partially, and customers who paid in advance feel they cannot get it back.",
        "who": "Customers who pay online, especially when a booking is cancelled by the company or a payment fails.",
        "why_it_happens": ["Payments and bookings are not reconciled in real time, so a paid-but-not-booked state can persist.", "Refunds follow bank timelines and manual approval rather than automatic rules.", "Customers cannot see where their refund is."],
        "proposal": [
            {"title": "Automatic refund to source", "what": "Refund automatically, with a visible tracker and expected date, whenever the company or professional cancels or a payment succeeds without a booking."},
            {"title": "Instant credit option", "what": "Offer an immediate in-app credit as an alternative to a 5-7 day bank refund, so the customer can rebook straight away."},
            {"title": "Reconcile within minutes", "what": "If money is taken and no booking exists, create the booking or reverse the charge automatically and tell the customer."},
            {"title": "Pay after service for small jobs", "what": "Test pay-after-service for low-value jobs, which several customers asked for."}],
        "repeat_mechanism": "A refund that takes weeks turns a one-off failure into a grievance about paying in the app at all. Instant, visible refunds should remove a common reason for not coming back (hypothesis).",
        "success": "Refunds reach the customer in hours instead of weeks, almost no case is stuck in 'paid but not booked', and customers who received a refund rebook at a normal rate.",
        "watch_out": "Instant credit can be abused; finance reconciliation effort rises.",
        "effort": "M", "effort_note": "Mostly payments and finance plumbing, clearly scoped.",
    },
    "O4": {
        "problem": "The price changes between the quote, the app and the bill. Fees stack up on small jobs, and on-site professionals quote parts or extra work at rates customers find far above local providers.",
        "who": "Repair and small-ticket customers (AC, appliance, plumbing, electrical) and cost-conscious households comparing with local providers.",
        "why_it_happens": ["Platform, visit, surge and tax charges are added late in the flow.", "Parts and extra work are priced on site at the professional's discretion, with no visible rate card.", "Customers cannot verify whether the extra work is needed."],
        "proposal": [
            {"title": "One all-in price, locked", "what": "Show the full price including fees and taxes before payment and honour it; if it changes, explain why in one line."},
            {"title": "In-app approval for extras", "what": "Any additional part or work is quoted in the app with a price cap, and the customer approves it before work starts."},
            {"title": "Public rate card for common parts", "what": "Publish typical prices so customers can see an upsell is not out of line with local rates."},
            {"title": "Small-job pricing", "what": "Review fee structure for small jobs, where fees weigh most and customers compare with local providers."}],
        "repeat_mechanism": "Price surprises damage trust, and customers who feel overcharged compare with local providers. A predictable bill makes the next booking a known quantity (hypothesis: repeat rate of customers whose final bill matched the quote vs those whose bill rose).",
        "success": "The final bill matches the booked price for almost every job, extras are approved in the app, and price complaints fall, particularly for small-ticket repeat categories.",
        "watch_out": "Revenue per booking may fall and professionals may lose upsell income; measure margin alongside repeat.",
        "effort": "M", "effort_note": "Pricing and checkout changes plus a professional-side approval flow.",
    },
    "O5": {
        "problem": "Work fails soon after the visit, and customers meet a refusal: warranty has 'expired', or rework needs repeated requests. Native purifier owners also report installation and after-sales delays.",
        "who": "Repair customers (AC, appliance, plumbing) and owners of Native products.",
        "why_it_happens": ["Warranty terms are short and unclear, so customers are surprised by the limits.", "Rework competes in the same dispatch queue as new bookings.", "Native installation and service depend on a chain of parties with no single status."],
        "proposal": [
            {"title": "One-tap 'problem after service'", "what": "Inside the warranty window, one tap reschedules the same or another professional within a stated time."},
            {"title": "Warranty visible per job", "what": "Show what is covered and the end date on the booking, and consider longer cover on high-value repairs."},
            {"title": "Native after-sales tracker", "what": "Installation and service status with a promised date, a dedicated support line and proactive delay updates."},
            {"title": "Hand-off when out of scope", "what": "If a fault is outside the service, say so plainly and point to the brand or a recommended option instead of leaving the customer stranded."}],
        "repeat_mechanism": "A repair that fails soon after is a strong reason to switch providers, and Native owners are long-term customers by design. Fixing it without a fight should protect the next booking (hypothesis).",
        "success": "Rework requests are completed quickly, warranty disputes fall, Native installations meet the promised date, and customers who needed rework still rebook.",
        "watch_out": "Warranty cost rises; abuse of rework needs light checks.",
        "effort": "M", "effort_note": "Rework flow and warranty display are contained; Native logistics is the harder part.",
    },
    "O6": {
        "problem": "Quality is inconsistent: incomplete or poor work, damage or theft, rude or unsafe conduct, pressure to give five stars, and doubts about honesty. People living alone feel the risk most in salon and massage at home.",
        "who": "All categories; salon, massage and home-alone customers for safety; AC and appliance customers for damage.",
        "why_it_happens": ["Assignment is not matched to skill and category experience.", "There is no customer-visible proof of completed work.", "Damage claims are slow, and in-person rating requests create pressure."],
        "proposal": [
            {"title": "Skill-matched assignment", "what": "Match professionals to jobs by verified skill and past results, with refreshers where quality slips."},
            {"title": "Proof of work", "what": "A short checklist and before/after photos the customer approves before the job closes."},
            {"title": "Damage cover that works", "what": "Visible cover with a fast claim path and a stated settlement time."},
            {"title": "Safety by design", "what": "Verified identity, shareable job status, a female-professional option, and ratings and tips requested in the app, not in person."}],
        "repeat_mechanism": "Customers who say they will return mostly praise the individual professional. Making that quality consistent, and making it easy to rebook the good one, should convert more first bookings into repeat bookings (hypothesis).",
        "success": "A higher share of jobs rated well without a complaint, faster damage settlement, fewer safety complaints, and more rebooking of the same professional.",
        "watch_out": "Training and checks add cost and time per job; strict scoring can reduce supply.",
        "effort": "L", "effort_note": "Largest operational scope; start with proof-of-work and damage claims.",
    },
    "O7": {
        "problem": "Customers who need a small or specific job hit minimum-order rules, find no single-bathroom or per-task option, cannot extend time, or ask for services that do not exist.",
        "who": "Small households, single-room needs and customers with one-off tasks; people asking for new categories.",
        "why_it_happens": ["Packages are sized for larger jobs, and a minimum order protects margin on small ones.", "There is no lightweight way to add time or customise a job.", "Demand for missing services is not captured."],
        "proposal": [
            {"title": "Per-task and single-unit options", "what": "Single-bathroom cleaning and similar small units with clear scope."},
            {"title": "Add-on and time extension", "what": "Let the customer extend the visit or add a task in the app, at a stated price."},
            {"title": "Capture missing demand", "what": "A custom request form that records requested services, and test the most requested categories."}],
        "repeat_mechanism": "Small jobs are where customers turn to local providers. Serving them should keep customers booking between larger jobs (hypothesis).",
        "success": "Fewer abandoned carts at the minimum-order step, more small-job bookings, and a repeat rate for small-job customers closer to the average.",
        "watch_out": "Small jobs have lower margin per visit; test price points before wide launch.",
        "effort": "S", "effort_note": "Packaging and catalogue work; no new infrastructure.",
    },
    "O8": {
        "problem": "In some areas and smaller cities customers open the app and find no service, or a category that is unavailable, with no sign of when it will arrive.",
        "who": "Customers in unserved pincodes and tier-2/3 cities.",
        "why_it_happens": ["Supply has not been built in low-density areas.", "Customers who cannot book leave no record of their demand."],
        "proposal": [
            {"title": "Pincode waitlist", "what": "Let customers join a waitlist by pincode and see nearby available categories."},
            {"title": "Use demand to decide expansion", "what": "Rank areas by waitlist demand to prioritise partner onboarding."}],
        "repeat_mechanism": "Customers who cannot book cannot return. A waitlist keeps the relationship alive until service arrives (hypothesis; the evidence here is thin).",
        "success": "Waitlist sign-ups by pincode, and bookings from waitlisted customers soon after launch.",
        "watch_out": "A waitlist raises expectations; communicate timelines honestly.",
        "effort": "S", "effort_note": "Small build; the expansion itself is a business decision.",
    },
    "O9": {
        "problem": "Customers who had a good job want the same professional again, but cannot easily rebook them, may pay extra to do so, and may be reassigned the professional they complained about.",
        "who": "Customers of recurring services (cleaning, salon, massage, plumbing) who found someone they trust.",
        "why_it_happens": ["Assignment is optimised for supply, not preference.", "Rebooking a specific person is not a first-class action.", "Complaints do not reliably block a professional for that customer."],
        "proposal": [
            {"title": "Book again with the same professional", "what": "A prominent action on the completion screen and in booking history, at no extra charge."},
            {"title": "Honour dislikes", "what": "After a complaint, never reassign that professional to that customer."},
            {"title": "Suggest favourites", "what": "Recommend the customer's well-rated professionals for the next category they need."}],
        "repeat_mechanism": "Several customers say outright they will call the same professional again. Making that one tap should convert a good job directly into a repeat booking (hypothesis; the most direct link to the metric).",
        "success": "More bookings rebooked with the same professional, and a higher 90-day repeat rate after a five-star job when the rebook prompt is shown.",
        "watch_out": "Popular professionals become overloaded; protect availability and fairness.",
        "effort": "S", "effort_note": "Contained product change using existing data.",
    },
}
```

### Notebook code cell 16

```python
t0 = time.time()
b = df                                              # the opportunity definitions below are written against this table
SRC = [p for p in b.platform.value_counts().index]
pct = lambda n, d, nd=1: round(100.0 * n / d, nd) if d else 0.0
def mask_any(cols): return b[cols].any(axis=1)
def nd(*names): return pd.concat([b["nd_" + n] for n in names], axis=1).any(axis=1)
def leave_mask(s): return (s.return_class == "Non-Return") & s.return_basis.isin(["Stated", "Signalled"])
SCALE = min(1.0, N / 2527)                          # volume thresholds are set for 2,527 reviews; smaller files scale down (with a floor)
EVID_FULL_N = max(8, 80 * SCALE)

OPPS = [
    ("O1", "Arrival guarantee and proactive recovery", mask_any(["th_T1"]) | nd("Reliable arrival: no last-minute cancellation, ETA, alternate professional", "Fair cancellation / reschedule policy"),
     "A confirmed booking is cancelled, rescheduled, late or never attended, and customers are charged or left without a replacement.", None,
     "Customers can plan around the slot; fewer wasted days and fewer fees for failures that are not theirs.", 4,
     "Fewer first-booking failures should reduce lapsed customers: a failed or late first booking is the earliest point at which a customer decides whether to trust the platform again (hypothesis).",
     "Two-way confirmation and live ETA; automatic same-day replacement when a professional cancels; waive cancellation fees whenever the company or professional cancels; compensation credit that is applied to the next booking.",
     "% of bookings fulfilled on the first scheduled slot; % of cancellations replaced within 2 hours; 90-day repeat booking rate for customers whose first booking was late or cancelled vs on time.",
     ["cancelled", "no_show", "late"], "T1", ["Reliable arrival: no last-minute cancellation, ETA, alternate professional", "Fair cancellation / reschedule policy"]),
    ("O2", "Human-reachable support with first-contact resolution", mask_any(["i_support_unreachable", "i_unresolved"]) | nd("Reachable human support (call/phone/helpline instead of bot)"),
     "Customers cannot reach a person, bots repeat templates, tickets are closed unresolved, and nobody owns the problem.", None,
     "A problem becomes a short, owned conversation instead of a stalemate.", 5,
     "Recourse failure is the most common companion of explicit non-return statements, so fixing it may rescue customers who would otherwise leave after a single failure (hypothesis).",
     "Callback or human chat on request after one bot exchange; a single case ID with owner and deadline; escalation path visible in the app; proactive status updates; post-resolution check-in.",
     "Time to first human response; % of complaints resolved at first contact; % of complaints reopened; 90-day repeat booking rate for customers who raised a complaint.",
     ["support_unreachable", "unresolved"], "T3", ["Reachable human support (call/phone/helpline instead of bot)"]),
    ("O3", "Instant refunds and payment-failure recovery", mask_any(["i_refund_payment"]) | nd("Fast, fair refunds and payment-failure recovery", "Payment flexibility (pay after service / cash / COD)"),
     "Money is deducted without a booking, refunds are slow or partial, and customers who paid in advance feel they cannot get it back.", None,
     "Customers regain money and trust quickly; less resentment of advance payment.", 3,
     "Refund waits turn a one-off failure into a grievance; fast automatic refunds could remove a common reason for not coming back (hypothesis).",
     "Auto-refund to source when the company or professional cancels or a payment fails; visible refund tracker with date; pay-after-service for low-value jobs.",
     "Median hours to refund; % of provider-cancelled bookings auto-refunded; repeat booking rate after a refund event.",
     ["refund_payment"], "T3", ["Fast, fair refunds and payment-failure recovery"]),
    ("O4", "All-in price lock and on-site upsell guardrails", mask_any(["th_T2"]) | nd("Upfront total price / no surprise charges"),
     "Prices change between quote, app and bill; stacked fees on small jobs; parts or extra work quoted on site at much higher rates than local providers.", None,
     "Predictable total cost and confidence that the on-site quote is fair.", 4,
     "Customers who feel overcharged compare with local providers and say they will switch; transparent pricing may keep small and repeat jobs on the platform (hypothesis).",
     "Show the all-in price (taxes, platform and visit fees) before payment; in-app approval and price cap for parts or extra work; visible rate card for common parts; clear explanation when prices change.",
     "% of bills equal to the booked price; % of on-site quote changes approved in-app; price-related complaint rate; repeat rate for small-ticket jobs.",
     ["price_high", "fees_charges", "overcharge_upsell"], "T2", ["Upfront total price / no surprise charges"]),
    ("O5", "One-tap rework and Native after-sales", mask_any(["i_warranty_rework", "i_native_after_sales"]) | nd("Warranty / rework / after-sales that is honoured"),
     "Warranty is refused or expires in days, rework needs repeated requests, and Native purifier installation or service is delayed or unsupported.", "Water Purifier / RO and AC Service & Repair",
     "Work that fails after the visit is fixed without a fight.", 4,
     "A product or repair that fails soon after service is a strong switch trigger, and Native owners are long-term customers by design (hypothesis).",
     "One-tap rework within the warranty window (same professional or a replacement); warranty visible and tracked in the app; Native installation SLA and a dedicated support line; longer warranty on high-value repairs.",
     "% of rework requests completed within 48 hours; warranty claim approval rate; Native installation completed within SLA; 90-day repeat rate after a rework event.",
     ["warranty_rework", "native_after_sales"], "T3", ["Warranty / rework / after-sales that is honoured"]),
    ("O6", "Quality, conduct and safety assurance", mask_any(["i_poor_quality", "i_damage_theft", "i_conduct_safety", "i_trust_fraud"]) | nd("Professional training / tools / consumables / 2-person jobs", "Rating pressure / tip prompts from professionals"),
     "Inconsistent skill, incomplete work, damaged property, rude or unsafe conduct, rating pressure and doubts about honesty.", "Salon and massage (safety), AC and appliance repair (damage)",
     "Consistent work and a sense of safety, especially for people alone at home.", 4,
     "Customers who say or signal they will return mostly praise the individual professional; making that quality consistent and easy to rebook could raise repeat booking (hypothesis).",
     "Skill-matched assignment and training for each category; checklist and before/after photos; damage cover with fast claims; safety features (verified identity, share-trip style tracking, female professional option); remove in-person rating prompts.",
     "% of jobs rated 4+ with no complaint; damage/theft claim rate and time to settle; safety complaints per 10,000 bookings; repeat rate with the same professional.",
     ["poor_quality", "damage_theft", "conduct_safety", "trust_fraud"], "T4", ["Professional training / tools / consumables / 2-person jobs", "Rating pressure / tip prompts from professionals"]),
    ("O7", "Flexible small-job and add-on packages", nd("Flexible / granular packages (single bathroom, add-ons, partial jobs, longer duration)", "New service categories requested"),
     "Minimum-order rules, no single-bathroom or per-task option, no way to extend time, and requests for services that do not exist.", "Home cleaning, small repairs",
     "Pay for exactly the job needed and get small jobs done without a minimum order.", 3,
     "Small jobs are where customers turn to local providers; serving them may keep customers on the platform between large bookings (hypothesis).",
     "Single-bathroom and per-task cleaning; hourly or add-on time extension; custom-request option for small jobs; test requested categories (cooking, home organising, heat pump).",
     "Share of bookings under the old minimum; conversion of cart abandoned at minimum order; repeat rate within 90 days for small-job customers.",
     ["missing_service_request"], "T5", ["Flexible / granular packages (single bathroom, add-ons, partial jobs, longer duration)", "New service categories requested"]),
    ("O8", "Coverage waitlist and tier-2/3 expansion", nd("Coverage in tier-2/3 cities and more localities") | mask_any(["i_coverage_gap"]),
     "Customers in unserved areas and cities cannot book at all; some download the app and find nothing.", "Tier-2/3 cities",
     "Access to the service, or a clear date when it will arrive.", 2,
     "Customers who cannot book cannot return; a waitlist keeps the relationship alive until coverage arrives (hypothesis; this evidence is thin).",
     "In-app waitlist by pincode with demand counts; partner onboarding where demand clusters; show nearest available categories.",
     "Waitlist sign-ups by pincode; % of waitlisted users who book within 90 days of launch.",
     ["coverage_gap"], "T5", ["Coverage in tier-2/3 cities and more localities"]),
    ("O9", "Preferred-professional continuity", nd("Choice of professional / continuity / gender / language") | b.record_id.isin(ER_INTENT),
     "Customers want to rebook the professional who did a good job (and avoid one who did not), but face surcharges, no choice, or reassignment of the same person after a complaint.", None,
     "Reliable quality from someone they trust, without paying extra to rebook.", 3,
     "Several explicit return statements are about a specific professional ('will definitely call her again'); free, easy rebooking could convert one good job into repeat bookings (hypothesis).",
     "'Book again with the same professional' on the completion screen; no surcharge for re-booking; block a professional after a complaint; recommend favourites for the next category.",
     "% of bookings re-booked with the same professional; 90-day repeat rate after a 5-star job with and without the rebook prompt.",
     [], "T4", ["Choice of professional / continuity / gender / language"]),
]

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
```

## Step 6 · Prove
### Evidence checks
Plain checks on the file itself: how much can be traced to a source, how much is stated rather than inferred, and whether the sample is large enough to lean on.

### Notebook code cell 17

```python
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
```

### The report
Builds the self-contained HTML report and the two CSV files, shows the report inline, and downloads all three in Colab.

### Notebook code cell 18

```python
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
```
