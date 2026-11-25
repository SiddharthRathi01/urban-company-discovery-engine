import json, os, re
import pandas as pd
X = "output/urban_company_reviews_master.xlsx"; C = "output/urban_company_reviews_master.csv"
print("files in output/:", sorted(os.listdir("output")))
sheets = pd.read_excel(X, sheet_name=None)
print({k: v.shape for k, v in sheets.items()})
m = sheets["Master"]; c = pd.read_csv(C, encoding="utf-8-sig", keep_default_na=False, dtype=str)
print("rows  xlsx:", len(m), " csv:", len(c), " unique record_id:", c.record_id.nunique(), " unique (platform,original id):", len(c.drop_duplicates(["platform", "original_review_id"])))
print("columns identical:", list(m.columns) == list(c.columns))
# CSV vs Excel sync
mm = m.fillna("").astype(str)
diff = 0
for col in ["record_id", "original_review_id", "source_url", "platform", "sentiment_label", "review_date"]:
    diff += int((mm[col].values != c[col].values).sum())
ILL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
tdiff = sum(1 for a, b in zip(c.review_text, m.review_text.fillna("").astype(str)) if ILL.sub("", a).replace("\r\n", "\n").strip() != b.replace("\r\n", "\n").strip())
print("xlsx-vs-csv field differences:", diff, "| review_text differences:", tdiff)
# original text preserved
raw = {}
def put(p, i, t): raw[(p, str(i))] = t
for f in ("play", "play_positive_topup", "play_mid_topup"):
    for r in json.load(open(f"raw/{f}.json", encoding="utf-8")): put("Google Play Store", r["review_id"], r["text"])
for f in ("consumercomplaints", "consumercomplaints_perma_full"):
    for r in json.load(open(f"raw/{f}.json", encoding="utf-8")): put("ConsumerComplaints.in", r["review_id"], r["text"])
for f in ("pissedconsumer", "pissedconsumer_perma_full"):
    for r in json.load(open(f"raw/{f}.json", encoding="utf-8")): put("PissedConsumer", r["review_id"], r["text"])
for l in open("raw/reddit.jsonl", encoding="utf-8"):
    r = json.loads(l); put("Reddit", r["review_id"], r["text"] if (r["text"] or "").strip() else r["title"])
bad = [(r.platform, r.original_review_id) for r in c.itertuples() if raw[(r.platform, r.original_review_id)] != r.review_text]
print("review_text differing from the originally collected text:", len(bad), bad[:3])
# traceability
print("empty review_text:", int((c.review_text.str.strip() == "").sum()), "| empty source_url:", int((c.source_url == "").sum()), "| non-http urls:", int((~c.source_url.str.startswith("https://")).sum()))
print("duplicate urls:", int(c.source_url.duplicated().sum()))
print(pd.crosstab(c.platform, c.url_verification_status).to_string())
print(c.groupby("platform").source_url.agg(lambda s: s.iloc[0]).to_string())
print("sentiment:", c.sentiment_label.value_counts().to_dict())
print("missing dates:", int((c.review_date == "").sum()), "| ratings present:", int((c.rating != "").sum()))
print("required fields present:", all(x in c.columns for x in ["record_id","original_review_id","review_text","platform","source_url","url_type","url_verification_status","review_date","rating","reviewer","service_category","city","sentiment_label","sentiment_method","word_count","collection_date"]))
ex = sheets["Excluded Records"]; print("excluded:", len(ex)); print(ex.groupby(["platform"]).size().to_dict()); print(ex.exclusion_reason.str.slice(0, 50).value_counts().head(12).to_string())
print(sheets["QC Log"].to_string(max_colwidth=95))
