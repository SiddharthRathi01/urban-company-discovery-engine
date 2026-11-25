"""PissedConsumer: collect reviews WITH their individual permalinks (taken from the page, never constructed).
Pages are sampled evenly across the archive. Polite 1.5s delay."""
import json, re, time, requests
from bs4 import BeautifulSoup

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
BASE = "https://urban-company.pissedconsumer.com/review.html"
clean = lambda t: re.sub(r"[ \t]+", " ", re.sub(r"\s*\n\s*", "\n", t)).strip()


def get(url):
    for _ in range(3):
        try:
            r = requests.get(url, headers=H, timeout=30)
            if r.status_code == 200: return r
        except Exception: pass
        time.sleep(3)
    return None


def spread(total, n):
    return sorted({round(1 + i * (total - 1) / (n - 1)) for i in range(n)})


rows, noperma = [], 0
for p in range(1, 264):
    r = get(f"{BASE}?page={p}" if p > 1 else BASE)
    if not r: continue
    html = r.text
    # permalinks that appear on the page: .../<slug>-<yyyymmdd><reviewid>.html
    perma = {}
    for m in re.finditer(r'https://urban-company\.pissedconsumer\.com/[a-z0-9\-]+-(\d{8})(\d{6,9})\.html', html):
        perma.setdefault(m.group(2), m.group(0))
    s = BeautifulSoup(html, "html.parser")
    for it in s.select("div.review-item"):
        rid = it.get("data-id")
        body = it.select_one("[itemprop=reviewBody]"); head = it.select_one("[itemprop=headline]")
        dp = it.select_one("meta[itemprop=datePublished]"); auth = it.select_one("[itemprop=author] [itemprop=name]")
        loc = it.select_one(".location-line"); rt = it.select_one("[itemprop=ratingValue]")
        url = perma.get(rid)
        if not url: noperma += 1
        if url: rows.append(dict(source="PissedConsumer", review_id=rid, title=head and clean(head.get_text()),
                         text=clean(body.get_text("\n")) if body else "", reviewer=auth and clean(auth.get_text()),
                         rating=float(rt.get("content") or rt.get_text()) if rt else None,
                         date_raw=dp.get("content")[:10] if dp else None, location_raw=loc and clean(loc.get_text(" ")),
                         url=url, listing_page=f"{BASE}?page={p}"))
    print("page", p, "rows", len(rows), "without permalink", noperma, flush=True)
    time.sleep(1.5)
json.dump(rows, open("raw/pissedconsumer_perma_full.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("DONE", len(rows), "with permalink", sum(1 for r in rows if r["url"]))
