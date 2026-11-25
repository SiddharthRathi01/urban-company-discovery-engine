"""Collect public Reddit posts + comments that mention Urban Company / UrbanClap.
Source: Arctic Shift public Reddit archive API (reddit.com blocks unauthenticated clients).
Saves incrementally (JSONL, one line per kept item) so a stop never loses work.
Only text that explicitly names the company is kept; the permalink is the one the archive reports for the item."""
import json, re, time, os, requests, datetime as dt

API = "https://arctic-shift.photon-reddit.com/api"
H = {"User-Agent": "research-review-collector/0.1 (product research; public posts only)"}
MENTION = re.compile(r"urban\s*company|urban\s*clap|urbanclap|urbancompany", re.I)
SUBS = """india bangalore mumbai hyderabad pune kolkata noida ahmedabad AskIndia IndianSkincareAddicts urbancompany jaipur indore
Bengaluru Mumbai Hyderabad Pune Chennai chennai Delhi delhi gurgaon Gurgaon IndiaSpeaks CasualIndia IndianHomes HomeImprovementIndia
IndianFemaleAdvice AskMenIndia bangalorerentals mumbaiRent Kerala chandigarh lucknow Lucknow surat nagpur coimbatore bhopal patna vadodara
TwoXIndia indiasocial IndianBeautyDeals personalfinanceindia IndiaTech india_investments""".split()
OUT = "raw/reddit.jsonl"
QUERIES = ["urban company", "urbanclap"]
CAP = 700


def call(path, params, tries=5):
    for i in range(tries):
        try:
            r = requests.get(f"{API}/{path}/search", params=params, headers=H, timeout=90)
            if r.status_code == 200: return r.json().get("data") or []
            if r.status_code == 429: time.sleep(8 * (i + 1)); continue
            if r.status_code == 422: return None
            time.sleep(3)
        except Exception:
            time.sleep(4)
    return None


def page_all(kind, sub, q):
    key = "query" if kind == "posts" else "body"
    out, before = [], None
    while len(out) < CAP:
        p = {key: q, "subreddit": sub, "limit": 100, "sort": "desc"}
        if before: p["before"] = before
        d = call(kind, p)
        if not d: break
        out += d
        if len(d) < 100: break
        before = dt.datetime.fromtimestamp(min(x["created_utc"] for x in d), dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        time.sleep(0.6)
    return out


seen = set()
if os.path.exists(OUT):
    for l in open(OUT, encoding="utf-8"):
        try: j = json.loads(l); seen.add((j["kind"], j["review_id"]))
        except Exception: pass
f = open(OUT, "a", encoding="utf-8")
total = len(seen)
for sub in dict.fromkeys(SUBS):
    n0 = total
    for kind in ("posts", "comments"):
        for q in QUERIES:
            for x in page_all(kind, sub, q) or []:
                k = (kind[:-1], x["id"])
                if k in seen: continue
                title = x.get("title") or "" if kind == "posts" else ""
                body = (x.get("selftext") if kind == "posts" else x.get("body")) or ""
                if body in ("[removed]", "[deleted]"): body = ""
                if not (title + " " + body).strip() or not MENTION.search(title + " " + body): continue
                perma = x.get("permalink")
                if not perma: continue  # never construct a URL: keep only items whose archive record carries the permalink
                seen.add(k); total += 1
                f.write(json.dumps(dict(source="Reddit", kind=kind[:-1], review_id=x["id"], subreddit=x.get("subreddit") or sub, title=title, text=body,
                                        reviewer=x.get("author") or "", created_utc=x["created_utc"],
                                        date=dt.datetime.fromtimestamp(x["created_utc"], dt.timezone.utc).strftime("%Y-%m-%d"),
                                        score=x.get("score"), url="https://www.reddit.com" + perma if perma.startswith("/") else perma),
                                   ensure_ascii=False) + "\n")
                f.flush()
    print(f"{sub}: +{total - n0} (total {total})", flush=True)
print("DONE", total, flush=True)
