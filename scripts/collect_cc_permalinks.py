"""ConsumerComplaints.in: scan ALL listing pages and keep only complaints whose individual permalink appears in the page markup."""
import json, re, time, requests
from bs4 import BeautifulSoup

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
clean = lambda t: re.sub(r"[ \t]+", " ", re.sub(r"\s*\n\s*", "\n", t)).strip()
base = "https://www.consumercomplaints.in/urban-company-b115885"
rows, seen_boxes = [], 0
for p in range(1, 80):
    url = base if p == 1 else f"{base}/page/{p}"
    r = None
    for _ in range(3):
        try:
            r = requests.get(url, headers=H, timeout=30)
            if r.status_code == 200: break
        except Exception: pass
        time.sleep(3)
    if not r or r.status_code != 200: continue
    s = BeautifulSoup(r.text, "html.parser")
    for b in s.select("div.complaint-box"):
        seen_boxes += 1
        a = next((x for x in b.select("a[href]") if re.search(r"-c\d+$", x["href"])), None)
        if not a: continue
        cid = b.get("id", "").lstrip("c")
        title = b.select_one(".complaint-box__title"); body = b.select_one(".complaint-box__text") or b.select_one(".complaint-box__more-txt")
        user = b.select_one(".author-box__user"); loc = b.select_one(".author-box__location"); dtm = b.select_one(".author-box__date")
        rows.append(dict(source="ConsumerComplaints.in", review_id=cid, title=title and clean(title.get_text()),
                         text=clean(body.get_text("\n")) if body else "", reviewer=user and clean(user.get_text()), rating=None,
                         date_raw=dtm and clean(dtm.get_text()), location_raw=loc and clean(loc.get_text()).replace("from ", "", 1),
                         url="https://www.consumercomplaints.in" + a["href"], listing_page=url))
    print(f"page {p}: boxes so far {seen_boxes}, with permalink {len(rows)}", flush=True)
    time.sleep(2)
json.dump(rows, open("raw/consumercomplaints_perma_full.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("DONE boxes", seen_boxes, "with permalink", len(rows))
