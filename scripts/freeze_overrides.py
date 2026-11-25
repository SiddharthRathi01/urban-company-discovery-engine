"""Convert the analyst's per-chunk decisions (keyed by record_id) into decisions keyed by (platform, original_review_id), which stay valid
when record_ids are renumbered. Merges into raw/analyst_labels.json: {"labels": {key: code}, "read": [keys], "exclude": {key: reason}}."""
import glob, json, sys, os
import pandas as pd

d = pd.read_pickle("raw/candidates_scored.pkl").set_index("record_id")
key = lambda rid: f"{d.loc[rid, 'platform']}||{d.loc[rid, 'original_review_id']}"
store = json.load(open("raw/analyst_labels.json", encoding="utf-8")) if os.path.exists("raw/analyst_labels.json") else {"labels": {}, "read": [], "exclude": {}}
files = sorted(sys.argv[1:]) or sorted(glob.glob("raw/ov_*.txt"))
queue = [l.split("|")[0] for l in open(sys.argv[0].replace("freeze_overrides.py", "") + "../raw/sentiment_queue.txt" if False else "raw/sentiment_queue.txt", encoding="utf-8") if l.strip()]
parsed = {}
for f in files:
    for l in open(f, encoding="utf-8"):
        l = l.strip()
        if not l or l.startswith("#"): continue
        rid, code = l.split()[:2]; parsed[rid] = code
n_x = 0
for rid in queue:
    if rid not in d.index: continue
    k = key(rid); plat = d.loc[rid, "platform"]
    store["read"] = list(set(store["read"]) | {k})
    code = parsed.get(rid)
    if code is None and plat in ("ConsumerComplaints.in", "PissedConsumer") and k not in store["labels"] and k not in store["exclude"]:
        code = "N"   # complaint-site default (all complaints), never overriding an explicit earlier decision
    if code == "X": store["exclude"][k] = "Professional-side / off-topic (analyst read)"; store["labels"].pop(k, None); n_x += 1
    elif code: store["labels"][k] = code
json.dump(store, open("raw/analyst_labels.json", "w", encoding="utf-8"), ensure_ascii=False, indent=0)
print("queue rows read:", len(store["read"]), "| explicit/default labels:", len(store["labels"]), "| excluded by analyst:", len(store["exclude"]))
