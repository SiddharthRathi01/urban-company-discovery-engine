"""Round 2 top-up (Play Store only): more detailed (12+ words) 4-5 star Play reviews, as a random sample from a large pool, excluding every review already collected.
Positives carry the evidence about customers who are likely to book again. Output: raw/play_positive_topup2.json"""
import json
import random
import re
import time

from google_play_scraper import Sort, reviews

PLAY_ID = "com.urbanclap.urbanclap"
have = set()
for f in ("play", "play_positive_topup", "play_mid_topup"):
    have |= {r["review_id"] for r in json.load(open(f"raw/{f}.json", encoding="utf-8"))}
print("already collected:", len(have), flush=True)

pool = {}
for sort, name, cap in ((Sort.NEWEST, "newest", 3500), (Sort.MOST_RELEVANT, "relevant", 1500)):
    for star in (5, 4):
        token, got = None, 0
        while got < cap:
            try:
                b, token = reviews(PLAY_ID, lang="en", country="in", sort=sort, filter_score_with=star, count=200, continuation_token=token)
            except Exception as e:  # noqa: BLE001
                print("err", str(e)[:80], flush=True); time.sleep(5); continue
            for r in b:
                if r["reviewId"] in have or not r["content"] or r["reviewId"] in pool:
                    continue
                if len(re.findall(r"\w+", r["content"])) < 12:
                    continue
                pool[r["reviewId"]] = r
            got += len(b)
            print(f"{name} star {star}: scanned {got} pool {len(pool)}", flush=True)
            if not b or token is None:
                break
            time.sleep(0.8)

random.seed(2026)
by = {5: [], 4: []}
for r in pool.values():
    by[r["score"]].append(r)
pick = random.sample(by[5], min(320, len(by[5]))) + random.sample(by[4], min(160, len(by[4])))
rows = [dict(source="Google Play Store", review_id=r["reviewId"], text=r["content"], reviewer=r["userName"], rating=r["score"], date=r["at"].strftime("%Y-%m-%d"),
             url=f"https://play.google.com/store/apps/details?id={PLAY_ID}&reviewId={r['reviewId']}", thumbs_up=r.get("thumbsUpCount"),
             app_version=r.get("reviewCreatedVersion"), developer_reply=r.get("replyContent"), topup="positive_balance_round2") for r in pick]
json.dump(rows, open("raw/play_positive_topup2.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
print("DONE pool", len(pool), "picked", len(rows), "date range", min(r["date"] for r in rows), max(r["date"] for r in rows), flush=True)
