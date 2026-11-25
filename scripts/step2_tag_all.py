import sys, re
sys.path.insert(0, "scripts")
import pandas as pd
from step2_common import *
from step2_codes2 import *
import step2_curated as cur

base, full = load()
base = tag_issues(base)
rc = [cur.classify_return(r.record_id, r.text, r.sentiment_label) for r in base.itertuples()]
base["stated_class"] = [x[0] for x in rc]          # first-pass detail: Explicit Return / Explicit Non-Return / Behavioural Signal / Insufficient Evidence
base["return_subtype"] = [x[1] for x in rc]
import step2_behaviour as beh
nb = [beh.classify(a, b_, r.sentiment_label, r.rating_f) for a, b_, r in zip(base.stated_class, base.return_subtype, base.itertuples())]
base["return_class"] = [x[0] for x in nb]          # Return / Non-Return / Insufficient Evidence
base["return_basis"] = [x[1] for x in nb]          # Stated / Signalled / Inferred / None
base["return_confidence"] = [x[2] for x in nb]     # High / Medium / Low
base["return_reason"] = [x[3] for x in nb]
base["prior_repeat"] = base.record_id.isin(cur.ENR_PRIOR_REPEAT)

for k, rx in ALT_RE.items(): base["alt_" + k] = base.text.map(lambda t, rx=rx: bool(rx.search(t)))

INTENT = re.compile(r"\b(?:need(?:ed|s)?|want(?:ed)?|looking for|require[d]?|plan(?:ned|ning)?|thinking of|because|since|due to|had to|have to|so (?:i|we) (?:booked|called|got|hired)|therefore|hence|in order to|before (?:the|my|our|we|i)|ahead of|for (?:the|my|our|a) (?:upcoming|coming))\b", re.I)
SENT_SPLIT = re.compile(r"(?<=[.!?\n])\s+")


def trig(t, rx):
    return any(rx.search(x) and INTENT.search(x) for x in SENT_SPLIT.split(t))


for k, rx in TRIG_RE.items(): base["trg_" + k] = base.text.map(lambda t, rx=rx: trig(t, rx))
for k, rx in HH_RE.items(): base["hh_" + k] = base.text.map(lambda t, rx=rx: bool(rx.search(t)))
for k, rx in DISC_RE.items(): base["dc_" + k] = base.text.map(lambda t, rx=rx: bool(rx.search(t)))
for k, rx in NEED_RE.items(): base["nd_" + k] = base.text.map(lambda t, rx=rx: bool(rx.search(t)))
base.to_pickle("raw/step2_tagged.pkl")
full.to_pickle("raw/step2_full.pkl")
print(base.return_class.value_counts().to_dict()); print(pd.crosstab(base.return_class, base.return_basis)); print(base.groupby(["return_class","return_basis"]).return_confidence.value_counts().unstack(fill_value=0))
print(base.return_subtype.value_counts().to_dict())
for pref, name in [("alt_", "ALTERNATIVES"), ("trg_", "TRIGGERS"), ("hh_", "HOUSEHOLD"), ("dc_", "DISCOVERY"), ("nd_", "UNMET NEEDS")]:
    print("\n##", name)
    print(base[[c for c in base.columns if c.startswith(pref)]].sum().sort_values(ascending=False).to_string())
