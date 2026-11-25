"""Top-up 2: (a) detailed 2-3 star Play reviews (mixed/neutral experiences), (b) extra ConsumerComplaints pages (direct permalinks).
Everything here is a random sample (fixed seed) from a larger pool, excluding records already collected."""
import json, re, time, random, requests
from bs4 import BeautifulSoup
from google_play_scraper import reviews, Sort

PLAY_ID = "com.urbanclap.urbanclap"
have = {r["review_id"] for f in ("play", "play_positive_topup") for r in json.load(open(f"raw/{f}.json", encoding="utf-8"))}
pool = {2: {}, 3: {}}
for star, cap in ((3, 2600), (2, 2600)):
    token, got = None, 0
    while got < cap:
        try:
            b, token = reviews(PLAY_ID, lang="en", country="in", sort=Sort.NEWEST, filter_score_with=star, count=200, continuation_token=token)
        except Exception as e:
            print("err", e); time.sleep(5); continue
        for r in b:
            if r["reviewId"] in have or not r["content"]: continue
            if len(re.findall(r"\w+", r["content"])) < 12: continue
            pool[star][r["reviewId"]] = r
        got += len(b); print(f"star {star} scanned {got} pool {len(pool[star])}", flush=True)
        if not b or token is None: break
        time.sleep(1)
random.seed(43)
pick = random.sample(list(pool[3].values()), min(130, len(pool[3]))) + random.sample(list(pool[2].values()), min(70, len(pool[2])))
rows = [dict(source="Google Play Store", review_id=r["reviewId"], text=r["content"], reviewer=r["userName"], rating=r["score"], date=r["at"].strftime("%Y-%m-%d"),
             url=f"https://play.google.com/store/apps/details?id={PLAY_ID}&reviewId={r['reviewId']}", thumbs_up=r.get("thumbsUpCount"),
             app_version=r.get("reviewCreatedVersion"), developer_reply=r.get("replyContent"), topup="mid_rating_detail") for r in pick]
json.dump(rows, open("raw/play_mid_topup.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
print("play mid top-up:", len(rows))

# ---- ConsumerComplaints extra pages (not previously fetched)
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
clean = lambda t: re.sub(r"[ \t]+", " ", re.sub(r"\s*\n\s*", "\n", t)).strip()
base = "https://www.consumercomplaints.in/urban-company-b115885"
used = {round(1 + i * 78 / 12) for i in range(13)}
pages = [p for p in range(2, 80) if p not in used and p % 6 == 4]
old = {r["review_id"] for r in json.load(open("raw/consumercomplaints.json", encoding="utf-8"))}
cc = []
for p in pages:
    try: r = requests.get(f"{base}/page/{p}", headers=H, timeout=30)
    except Exception: continue
    if r.status_code != 200: continue
    s = BeautifulSoup(r.text, "html.parser")
    for b in s.select("div.complaint-box"):
        a = next((x for x in b.select("a[href]") if re.search(r"-c\d+$", x["href"])), None)
        cid = b.get("id", "").lstrip("c")
        if not a or cid in old: continue
        title = b.select_one(".complaint-box__title"); body = b.select_one(".complaint-box__text") or b.select_one(".complaint-box__more-txt")
        user = b.select_one(".author-box__user"); loc = b.select_one(".author-box__location"); dt = b.select_one(".author-box__date")
        cc.append(dict(source="ConsumerComplaints.in", review_id=cid, title=title and clean(title.get_text()), text=clean(body.get_text("\n")) if body else "",
                       reviewer=user and clean(user.get_text()), rating=None, date_raw=dt and clean(dt.get_text()),
                       location_raw=loc and clean(loc.get_text()).replace("from ", "", 1), url="https://www.consumercomplaints.in" + a["href"], resolved=None))
    print("CC page", p, len(cc), flush=True); time.sleep(1.5)
random.seed(44)
cc = random.sample(cc, min(100, len(cc)))
json.dump(cc, open("raw/consumercomplaints_topup.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("cc top-up:", len(cc))
