"""Collect public Play Store + App Store reviews for Urban Company (India storefront)."""
import json, time, requests
from google_play_scraper import reviews, Sort

PLAY_ID = "com.urbanclap.urbanclap"
APPLE_ID = "1032480595"

def collect_play(per_star_newest=200, per_star_relevant=60):
    out = {}
    for sort, n, label in [(Sort.NEWEST, per_star_newest, "newest"), (Sort.MOST_RELEVANT, per_star_relevant, "relevant")]:
        for star in (1, 2, 3, 4, 5):
            got, token = 0, None
            while got < n:
                try:
                    batch, token = reviews(PLAY_ID, lang="en", country="in", sort=sort,
                                           filter_score_with=star, count=min(100, n - got),
                                           continuation_token=token)
                except Exception as e:
                    print("play err", e); time.sleep(5); break
                for r in batch:
                    out.setdefault(r["reviewId"], r)
                got += len(batch)
                if not batch or token is None: break
                time.sleep(1)
            print(f"play {label} star={star} got={got} unique_total={len(out)}", flush=True)
    rows = []
    for r in out.values():
        rows.append(dict(source="Google Play Store", review_id=r["reviewId"], text=r["content"],
                         reviewer=r["userName"], rating=r["score"], date=r["at"].strftime("%Y-%m-%d"),
                         url=f"https://play.google.com/store/apps/details?id={PLAY_ID}&reviewId={r['reviewId']}",
                         thumbs_up=r.get("thumbsUpCount"), app_version=r.get("reviewCreatedVersion"),
                         developer_reply=r.get("replyContent")))
    return rows

def collect_apple():
    rows = []
    for p in range(1, 11):
        r = requests.get(f"https://itunes.apple.com/in/rss/customerreviews/page={p}/id={APPLE_ID}/sortby=mostrecent/json", timeout=30)
        if r.status_code != 200: break
        e = r.json()["feed"].get("entry", [])
        e = [e] if isinstance(e, dict) else e
        for x in e:
            rows.append(dict(source="Apple App Store", review_id=x["id"]["label"],
                             text=(x.get("title", {}).get("label", "") + "\n" + x["content"]["label"]).strip(),
                             title=x.get("title", {}).get("label", ""), body=x["content"]["label"],
                             reviewer=x["author"]["name"]["label"], rating=int(x["im:rating"]["label"]),
                             date=x["updated"]["label"][:10],
                             url=x["author"].get("uri", {}).get("label") or f"https://apps.apple.com/in/app/id{APPLE_ID}?see-all=reviews",
                             app_version=x.get("im:version", {}).get("label")))
        print("apple page", p, len(e), flush=True); time.sleep(1)
    return rows

if __name__ == "__main__":
    ap = collect_apple(); json.dump(ap, open("raw/apple.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    pl = collect_play(); json.dump(pl, open("raw/play.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print("DONE apple", len(ap), "play", len(pl))
