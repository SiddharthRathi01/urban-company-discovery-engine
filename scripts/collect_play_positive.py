"""Top-up: detailed (8+ words) 4-5 star Play reviews, random sample from a large pool, to balance positive vs negative content."""
import json, re, time, random
import pandas as pd
from google_play_scraper import reviews, Sort
PLAY_ID = "com.urbanclap.urbanclap"
have = {r["review_id"] for r in json.load(open("raw/play.json", encoding="utf-8"))}
pool = {}
for star, cap in ((5, 2500), (4, 2500)):
    token, got = None, 0
    while got < cap:
        try:
            b, token = reviews(PLAY_ID, lang="en", country="in", sort=Sort.NEWEST, filter_score_with=star, count=200, continuation_token=token)
        except Exception as e:
            print("err", e); time.sleep(5); continue
        for r in b:
            if r["reviewId"] in have or not r["content"]: continue
            if len(re.findall(r"\w+", r["content"])) < 8: continue
            pool[r["reviewId"]] = r
        got += len(b); print(f"star {star} scanned {got} pool {len(pool)}", flush=True)
        if not b or token is None: break
        time.sleep(1)
random.seed(42)
by = {5: [], 4: []}
for r in pool.values(): by[r["score"]].append(r)
pick = random.sample(by[5], min(200, len(by[5]))) + random.sample(by[4], min(150, len(by[4])))
rows = [dict(source="Google Play Store", review_id=r["reviewId"], text=r["content"], reviewer=r["userName"], rating=r["score"], date=r["at"].strftime("%Y-%m-%d"),
             url=f"https://play.google.com/store/apps/details?id={PLAY_ID}&reviewId={r['reviewId']}", thumbs_up=r.get("thumbsUpCount"),
             app_version=r.get("reviewCreatedVersion"), developer_reply=r.get("replyContent"), topup="positive_balance") for r in pick]
json.dump(rows, open("raw/play_positive_topup.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
print("pool", len(pool), "picked", len(rows), "date range", min(r["date"] for r in rows), max(r["date"] for r in rows))
