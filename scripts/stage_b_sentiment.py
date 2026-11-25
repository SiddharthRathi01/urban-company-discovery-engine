"""STAGE B: lexicon draft labels -> split into AUTO-accepted (clear, rating-consistent) and REVIEW QUEUE (everything else).
The queue and a random validation sample of the auto-accepted rows are read by the analyst; overrides go in raw/analyst_overrides.json."""
import re, sys, json, random
import pandas as pd
sys.path.insert(0, "scripts")
from sentiment import label, CONTRAST, _score, SENT_SPLIT

df = pd.read_pickle("raw/candidates.pkl").reset_index(drop=True)
prefix = {"Google Play Store": "GP", "ConsumerComplaints.in": "CC", "PissedConsumer": "PC", "Reddit": "RD", "Apple App Store": "AS"}
df = df.sort_values(["platform", "review_date"], ascending=[True, False]).reset_index(drop=True)
# Record IDs are STABLE: a review keeps the ID it already has; reviews added later get the next free number for their platform.
import os
_old = pd.read_pickle("raw/candidates_scored.pkl") if os.path.exists("raw/candidates_scored.pkl") else None
_ids = {} if _old is None else {(r.platform, str(r.original_review_id)): r.record_id for r in _old.itertuples()}
_next = {p: max([int(v.split("-")[1]) for (pl, _), v in _ids.items() if pl == p] or [0]) for p in prefix}
rid = []
for r in df.itertuples():
    k = (r.platform, str(r.original_review_id))
    if k not in _ids:
        _next[r.platform] += 1
        _ids[k] = f"{prefix[r.platform]}-{_next[r.platform]:04d}"
    rid.append(_ids[k])
df["record_id"] = rid
res = df.apply(lambda r: label(r.review_title, r.review_text, r.rating), axis=1)
df["draft_label"] = res.map(lambda x: x[0]); df["draft_method"] = res.map(lambda x: x[1]); df["draft_score"] = res.map(lambda x: x[2])

CUE = re.compile(r'(?<![A-Za-z])(?:but|however|though|although|should|need|needs|please|pls|plz|improve|improvement|better|could|would|only|except|price|prices|cost|costly|expensive|charge|charges|charged|high|higher|fee|fees|not|no|cant|can.t|cannot|unable|difficult|issue|issues|problem|bug|bugs|slow|delay|delayed|late|cancel|cancelled|cancellation|rescheduled|suggest|suggestion|request|wish|hope|add|provide)(?![A-Za-z])', re.I)

def auto_ok(r):
    if r.draft_method != "text lexicon": return False
    rt = r.rating
    if r.draft_label == "Positive":
        if not (r.draft_score >= 0.2 and (not pd.isna(rt)) and rt >= 4): return False
        wc = len(re.findall(r"\w+", r.review_title + " " + r.review_text))
        return wc <= 5 or not CUE.search(r.review_title + " " + r.review_text)
    if r.draft_label == "Negative": return r.draft_score <= -0.2 and r.platform != "Reddit" and (pd.isna(rt) or rt <= 2)
    return False
df["auto_ok"] = df.apply(auto_ok, axis=1)
# contrast guard: a contrastive clause with opposite-sign sentences is never auto-accepted
def has_flip(r):
    full = (r.review_title + ". " + r.review_text)
    if not CONTRAST.search(full): return False
    sc = [_score(p) for p in SENT_SPLIT.split(full) if p and len(p.strip()) > 2]
    return any(s >= 0.35 for s in sc) and any(s <= -0.35 for s in sc)
df.loc[df.auto_ok & df.apply(has_flip, axis=1), "auto_ok"] = False
df["tx"] = (df.review_title.where(df.review_title != "", "") + (" // " if True else "") + df.review_text).str.replace(r"\s+", " ", regex=True).str.strip(" /")
df.to_pickle("raw/candidates_scored.pkl")

q = df[~df.auto_ok]
print("candidates", len(df), "| auto-accepted", int(df.auto_ok.sum()), "| analyst review queue", len(q))
print(q.platform.value_counts().to_string()); print(q.draft_label.value_counts().to_string())
with open("raw/sentiment_queue.txt", "w", encoding="utf-8") as f:
    for r in q.itertuples():
        rt = "-" if pd.isna(r.rating) else str(int(r.rating)) if float(r.rating).is_integer() else str(r.rating)
        f.write(f"{r.record_id}|{rt}|{r.draft_label[:3]}|{r.tx[:210]}\n")
random.seed(5)
a = df[df.auto_ok]; s = a.sample(min(150, len(a)), random_state=5)
with open("raw/sentiment_validation_sample.txt", "w", encoding="utf-8") as f:
    for r in s.itertuples():
        rt = "-" if pd.isna(r.rating) else str(int(r.rating))
        f.write(f"{r.record_id}|{rt}|{r.draft_label[:3]}|{r.tx[:200]}\n")
