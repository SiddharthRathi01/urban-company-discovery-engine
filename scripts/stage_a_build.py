"""STAGE A: assemble all collected records, apply traceability + relevance + duplicate rules, verify every URL.
Output: raw/candidates.pkl (retained records, pre-sentiment), raw/stage_a_logs.pkl (QC, duplicates, exclusions, link check)."""
import json, re, sys, os, time, datetime as dt
from concurrent.futures import ThreadPoolExecutor
import pandas as pd, requests
from bs4 import BeautifulSoup
sys.path.insert(0, "scripts")
from build_dataset import tag_categories, tag_cities, norm_key, parse_date

RAW = "raw"
TODAY = dt.date.today().isoformat()
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36", "Accept-Language": "en-IN,en;q=0.9"}
jl = lambda f: json.load(open(f"{RAW}/{f}.json", encoding="utf-8"))
PLAY_NOTE = "Play Store (India, English)"

# ------------------------------------------------------------------ 1. load every record ever collected
recs = []
def add(**k):
    base = dict(review_title="", reviewer_location="", community="", content_type="", engagement=None, app_version="", company_reply="", collection_note="")
    base.update(k); recs.append(base)

for f, note in (("play", "Play: stratified by star (newest 200 + 60 most-relevant per star)"),
                ("play_positive_topup", "Play top-up: random sample of detailed (8+ words) 4-5 star reviews"),
                ("play_mid_topup", "Play top-up: random sample of detailed (12+ words) 2-3 star reviews"),
                ("play_positive_topup2", "Play top-up round 2: random sample of detailed (12+ words) 4-5 star reviews")):
    for r in jl(f):
        add(platform="Google Play Store", original_review_id=r["review_id"], review_text=r["text"], rating=float(r["rating"]), review_date=r["date"],
            reviewer=r["reviewer"], source_url=r["url"], url_candidate_type="Individual review link (Play reviewId deep link)", content_type="App review",
            engagement=r.get("thumbs_up"), app_version=r.get("app_version") or "", company_reply=r.get("developer_reply") or "", collection_note=note)
for r in jl("apple"):
    add(platform="Apple App Store", original_review_id=r["review_id"], review_title=r["title"], review_text=r["body"], rating=float(r["rating"]),
        review_date=r["date"], reviewer=r["reviewer"], source_url="", url_candidate_type="NONE - Apple exposes no individual review URL", content_type="App review",
        app_version=r.get("app_version") or "", collection_note="Apple iTunes customer-reviews RSS (India), most recent 500")
cc_new = {r["review_id"]: r for r in jl("consumercomplaints_perma_full")} if os.path.exists(f"{RAW}/consumercomplaints_perma_full.json") else {}
for r in jl("consumercomplaints"):                       # first pass (listing-anchor URLs unless a real permalink exists)
    perma = cc_new.get(r["review_id"], {}).get("url") or (r["url"] if "#c" not in r["url"] else "")
    add(platform="ConsumerComplaints.in", original_review_id=r["review_id"], review_title=r["title"] or "", review_text=r["text"], rating=None,
        review_date=parse_date(r["date_raw"]), reviewer=r["reviewer"] or "", reviewer_location=r["location_raw"] or "", source_url=perma,
        url_candidate_type="Individual complaint page" if perma else "NONE - only a rolling listing page (no individual URL in source)", content_type="Complaint",
        collection_note="ConsumerComplaints.in, pass 1 (sampled listing pages)")
for r in cc_new.values():
    add(platform="ConsumerComplaints.in", original_review_id=r["review_id"], review_title=r["title"] or "", review_text=r["text"], rating=None,
        review_date=parse_date(r["date_raw"]), reviewer=r["reviewer"] or "", reviewer_location=r["location_raw"] or "", source_url=r["url"],
        url_candidate_type="Individual complaint page", content_type="Complaint", collection_note="ConsumerComplaints.in, full scan of listing pages for complaints with individual URLs")
pc_new = {r["review_id"]: r for r in jl("pissedconsumer_perma_full")} if os.path.exists(f"{RAW}/pissedconsumer_perma_full.json") else {}
for r in jl("pissedconsumer"):
    perma = pc_new.get(r["review_id"], {}).get("url") or ""
    add(platform="PissedConsumer", original_review_id=r["review_id"], review_title=r["title"] or "", review_text=r["text"], rating=r["rating"],
        review_date=parse_date(r["date_raw"]), reviewer=r["reviewer"] or "", reviewer_location=r["location_raw"] or "", source_url=perma,
        url_candidate_type="Individual review page" if perma else "NONE - only a rolling listing page (no individual URL in source)", content_type="Complaint / review",
        collection_note="PissedConsumer, pass 1 (sampled listing pages)")
for r in pc_new.values():
    add(platform="PissedConsumer", original_review_id=r["review_id"], review_title=r["title"] or "", review_text=r["text"], rating=r["rating"],
        review_date=parse_date(r["date_raw"]), reviewer=r["reviewer"] or "", reviewer_location=r["location_raw"] or "", source_url=r["url"],
        url_candidate_type="Individual review page", content_type="Complaint / review", collection_note="PissedConsumer, full scan of listing pages for reviews with individual URLs")
if os.path.exists(f"{RAW}/reddit.jsonl"):
    for l in open(f"{RAW}/reddit.jsonl", encoding="utf-8"):
        r = json.loads(l)
        title_only = not (r["text"] or "").strip()      # post consists of its title only: title is stored as the review text
        add(platform="Reddit", original_review_id=r["review_id"], review_title="" if title_only else (r["title"] or ""),
            review_text=(r["title"] or "") if title_only else r["text"], rating=None, review_date=r["date"],
            reviewer=r["reviewer"], source_url=r["url"], url_candidate_type=f"Individual Reddit {r['kind']} permalink", community=f"r/{r['subreddit']}",
            content_type="Post (title only)" if title_only else "Post", engagement=r.get("score"),
            collection_note="Reddit post naming Urban Company/UrbanClap; text + permalink from the Arctic Shift public archive")
df = pd.DataFrame(recs)
df["rating"] = pd.to_numeric(df.rating, errors="coerce")
df["review_text"] = df.review_text.fillna("").astype(str); df["review_title"] = df.review_title.fillna("").astype(str)
df["original_review_id"] = df.original_review_id.astype(str)
qc = [("Records loaded from all collection passes (before any de-duplication)", len(df))]
for p, g in df.groupby("platform"): qc.append((f"   of which {p}", len(g)))

# ------------------------------------------------------------------ 2. duplicates (by ID first, then text)
dups = []
d1 = df.duplicated(["platform", "original_review_id"], keep="first")
dups.append(("1. Same platform + original review ID (same record collected in more than one pass)", df[d1], "removed"))
df = df[~d1].copy()
df["_norm"] = (df.review_title + " " + df.review_text).map(norm_key)
d2 = df.duplicated(["platform", "reviewer", "review_date", "_norm"], keep="first")
dups.append(("2. Same platform + reviewer + date + text", df[d2], "removed"))
df = df[~d2].copy()
long_ = df._norm.str.len() >= 40
d3 = long_ & df.duplicated("_norm", keep="first")
dups.append(("3. Identical text (>=40 normalised chars) under a different ID/reviewer/platform", df[d3], "removed"))
df = df[~d3].copy()
qc.append(("Unique records after de-duplication", len(df)))
for lab, fr, _ in dups: qc.append((f"Duplicates removed - {lab}", len(fr)))
df["_unique_raw"] = True

# ------------------------------------------------------------------ 3. traceability exclusions
trace_fail = df[df.source_url.fillna("") == ""].copy()
trace_fail["exclusion_reason"] = "No individual-review URL and no stable public page identifying the review"
df = df[df.source_url.fillna("") != ""].copy()
qc.append(("Excluded for lack of individual-review traceability (no individual URL)", len(trace_fail)))
for p, g in trace_fail.groupby("platform"): qc.append((f"   of which {p}", len(g)))

# ------------------------------------------------------------------ 4. relevance exclusions (manual decisions after reading + rules)
MANUAL = {
    ("ConsumerComplaints.in", "3441711"): ("Professional-side", "Beautician (partner) complaining her partner ID was blocked"),
    ("ConsumerComplaints.in", "2705875"): ("Professional-side", "Complaint about partner category-manager, written about a cousin who is a partner"),
    ("Google Play Store", "03392aed-2804-4dd3-963e-a25bbd3fe219"): ("Professional-side", "8-year partner complaining about permanent account block"),
    ("PissedConsumer", "7433790"): ("Professional-side", "Person trying to join as a partner; partner app not working"),
    ("PissedConsumer", "7028083"): ("Professional-side", "Partner applicant asking for profile approval"),
    ("PissedConsumer", "5623175"): ("Professional-side", "Former partner asking to rejoin"),
    ("PissedConsumer", "5218815"): ("Professional-side", "Trainee/partner complaint about training and ID block"),
    ("PissedConsumer", "7301287"): ("Spam / scam listing", "Repeated promotional 'customer care number' text with obfuscated phone number"),
    ("Google Play Store", "e91eac40-2264-4a3e-851b-c934b25b642c"): ("Unreadable / no content", "Emoji and stray characters only"),
}
if os.path.exists(f"{RAW}/analyst_labels.json"):          # exclusions decided while reading the sentiment queue
    for k_, why in json.load(open(f"{RAW}/analyst_labels.json", encoding="utf-8"))["exclude"].items():
        pl_, oid_ = k_.split("||", 1); MANUAL[(pl_, oid_)] = ("Professional-side / off-topic", "identified while reading the review text (partner, ex-employee, applicant or not about Urban Company)")
if os.path.exists(f"{RAW}/reddit_relevance.json"):       # decisions made by reading each Reddit item
    for k, v in json.load(open(f"{RAW}/reddit_relevance.json", encoding="utf-8")).items(): MANUAL[("Reddit", k)] = (v[0], v[1])
def rel(r):
    return MANUAL.get((r.platform, r.original_review_id))
rr = df.apply(rel, axis=1)
mask = rr.notna()
rel_ex = df[mask].copy(); rel_ex["exclusion_reason"] = rr[mask].map(lambda x: f"{x[0]}: {x[1]}")
df = df[~mask].copy()
qc.append(("Excluded by relevance audit (professional-side / spam / unreadable / off-topic)", len(rel_ex)))
for p, g in rel_ex.groupby("platform"): qc.append((f"   of which {p}", len(g)))

# ------------------------------------------------------------------ 5. short-identical-text flag (kept, flagged for examination)
short_dup = (~df._norm.str.len().ge(40)) & df.duplicated("_norm", keep=False)
df["identical_short_text_flag"] = short_dup.map({True: "Y", False: ""})
grp = df[short_dup].groupby("_norm").agg(text=("review_text", "first"), n=("review_text", "size"), platforms=("platform", lambda s: ", ".join(sorted(set(s)))),
                                         records=("original_review_id", lambda s: ", ".join(s.astype(str)))).reset_index(drop=True).sort_values("n", ascending=False)
qc.append(("Short identical texts kept but flagged for examination (different reviewers)", int(short_dup.sum())))

# ------------------------------------------------------------------ 6. verify every URL
def norm_alnum(t): return re.sub(r"[\W_]+", "", t.lower())
CACHE_F = f"{RAW}/link_cache.json"
CACHE = json.load(open(CACHE_F, encoding="utf-8")) if os.path.exists(CACHE_F) else {}
def verify(r):
    u = r.source_url
    if r.platform != "Reddit" and u in CACHE and CACHE[u][1].startswith("Verified"): return tuple(CACHE[u])
    if r.platform == "Reddit":
        return ("Individual permalink (from archive record)", "Not machine-verified: reddit.com blocks automated access; permalink taken from the archive record, not constructed", None)
    res = None
    for i in range(4):
        try:
            res = requests.get(u, headers=H, timeout=40)
            if res.status_code == 200: break
            if res.status_code in (429, 503): time.sleep(5 * (i + 1)); continue
            break
        except Exception as e:
            time.sleep(3)
    if res is None: return (r.url_candidate_type, "FAILED: no response", 0)
    if res.status_code != 200: return (r.url_candidate_type, f"FAILED: HTTP {res.status_code}", res.status_code)
    html = res.text
    body = (r.review_text or r.review_title)
    if r.platform == "Google Play Store":
        id_ok = r.original_review_id in html
        toks = re.findall(r"[A-Za-z0-9]{3,}", body)[:4]
        txt_ok = bool(toks) and re.search(r".{0,14}".join(map(re.escape, toks)), html, re.I | re.S) is not None
        if not toks: txt_ok = norm_alnum(body)[:10] in norm_alnum(html)
    else:
        page = norm_alnum(BeautifulSoup(html, "html.parser").get_text(" "))
        id_ok = r.original_review_id in html
        nb = norm_alnum(body)
        txt_ok = nb[:50] in page or (len(nb) > 130 and nb[60:110] in page)
    if id_ok and txt_ok: return (r.url_candidate_type, "Verified: review ID and text found at this URL", 200)
    if txt_ok: return (r.url_candidate_type, "Verified: review text found at this URL", 200)
    return (r.url_candidate_type, "FAILED: page loads but review not found on it", 200)

rows = list(df.itertuples())
t0 = time.time()
with ThreadPoolExecutor(5) as ex: out = list(ex.map(verify, rows))
for r_, o_ in zip(rows, out):
    if o_[1].startswith("Verified"): CACHE[r_.source_url] = list(o_)
json.dump(CACHE, open(CACHE_F, "w", encoding="utf-8"))
df["url_type"] = [o[0] for o in out]; df["url_verification_status"] = [o[1] for o in out]; df["http_status"] = [o[2] for o in out]
print(f"verified {len(df)} URLs in {time.time()-t0:.0f}s")
link_check = df[["platform", "original_review_id", "source_url", "url_type", "http_status", "url_verification_status"]].copy()
bad = df[df.url_verification_status.str.startswith("FAILED")].copy()
bad["exclusion_reason"] = "URL failed verification: " + bad.url_verification_status
df = df[~df.url_verification_status.str.startswith("FAILED")].copy()
qc.append(("Excluded because the source URL failed verification", len(bad)))
for p, g in bad.groupby("platform"): qc.append((f"   of which {p}", len(g)))
qc.append(("Records retained after traceability, relevance and URL checks", len(df)))

# ------------------------------------------------------------------ 7. tagging (explicit mentions only)
blob = df.review_title + " " + df.review_text
tg = blob.map(tag_categories)
df["service_category"] = tg.map(lambda x: x[0]); df["service_categories_all"] = tg.map(lambda x: x[1])
df["city_mentioned"] = blob.map(tag_cities)
df["word_count"] = blob.map(lambda t: len(re.findall(r"\w+", t)))
df["collection_date"] = TODAY
excluded = pd.concat([trace_fail, rel_ex, bad], ignore_index=True)
df.drop(columns=["_norm", "_unique_raw"], errors="ignore").to_pickle(f"{RAW}/candidates.pkl")
pd.to_pickle(dict(qc=qc, dups=[(a, b.drop(columns=["_norm"], errors="ignore"), c) for a, b, c in dups], short_groups=grp, excluded=excluded.drop(columns=["_norm"], errors="ignore"),
                  link_check=link_check, raw_total=sum(1 for _ in recs)), f"{RAW}/stage_a_logs.pkl")
for a, b in qc: print(f"{b:>6}  {a}")
print(df.platform.value_counts().to_string())
