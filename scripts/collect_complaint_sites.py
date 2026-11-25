"""Collect public complaint/review-site entries (consumercomplaints.in, PissedConsumer).
Pages are sampled evenly across each site's archive for temporal diversity. Polite 1.5s delay."""
import json, re, time, requests
from bs4 import BeautifulSoup
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
clean = lambda t: re.sub(r"[ \t]+", " ", re.sub(r"\s*\n\s*", "\n", t)).strip()

def pages_spread(total_pages, n):
    return sorted({round(1 + i * (total_pages - 1) / (n - 1)) for i in range(n)})

def get(url):
    for i in range(3):
        try:
            r = requests.get(url, headers=H, timeout=30)
            if r.status_code == 200: return r
            print("  status", r.status_code, url)
        except Exception as e: print("  err", e)
        time.sleep(3)
    return None

def consumercomplaints(n_pages=13):
    base = "https://www.consumercomplaints.in/urban-company-b115885"
    first = get(base)
    m = re.search(r"Complaints\s+(\d{3,5})", BeautifulSoup(first.text, "html.parser").get_text(" ", strip=True))
    total = int(m.group(1)); last_page = -(-total // 20); print("CC total", total, "pages", last_page)
    rows = []
    for p in pages_spread(last_page, n_pages):
        url = base if p == 1 else f"{base}/page/{p}"
        r = get(url)
        if not r: continue
        s = BeautifulSoup(r.text, "html.parser")
        for b in s.select("div.complaint-box"):
            a = next((x for x in b.select("a[href]") if re.search(r"-c\d+$", x["href"])), None)
            cid = b.get("id", "").lstrip("c")
            title = b.select_one(".complaint-box__title"); txt = b.select_one(".complaint-box__more-txt") or b.select_one(".complaint-box__text")
            body = b.select_one(".complaint-box__text")
            if body and txt and len(txt.get_text()) < len(body.get_text()): txt = body
            user = b.select_one(".author-box__user"); loc = b.select_one(".author-box__location"); dt = b.select_one(".author-box__date")
            rows.append(dict(source="ConsumerComplaints.in", review_id=cid, title=title and clean(title.get_text()),
                             text=clean(txt.get_text("\n")) if txt else "", reviewer=user and clean(user.get_text()),
                             rating=None, date_raw=dt and clean(dt.get_text()),
                             location_raw=loc and clean(loc.get_text()).replace("from ", "", 1),
                             url="https://www.consumercomplaints.in" + a["href"] if a else f"{url}#c{cid}",
                             resolved=bool(re.search(r"^\s*\[Resolved\]", a.get_text())) if a else None))
        print("CC page", p, len(rows), flush=True); time.sleep(1.5)
    return rows

def pissedconsumer(n_pages=10, total_pages=250):
    base = "https://urban-company.pissedconsumer.com/review.html"
    rows = []
    for p in pages_spread(total_pages, n_pages):
        url = f"{base}?page={p}" if p > 1 else base
        r = get(url)
        if not r: continue
        s = BeautifulSoup(r.text, "html.parser")
        for it in s.select("div.review-item"):
            rid = it.get("data-id")
            body = it.select_one("[itemprop=reviewBody]"); head = it.select_one("[itemprop=headline]")
            dp = it.select_one("meta[itemprop=datePublished]"); auth = it.select_one("[itemprop=author] [itemprop=name]")
            loc = it.select_one(".location-line"); rt = it.select_one("[itemprop=ratingValue]")
            rows.append(dict(source="PissedConsumer", review_id=rid, title=head and clean(head.get_text()),
                             text=clean(body.get_text("\n")) if body else "", reviewer=auth and clean(auth.get_text()),
                             rating=float(rt.get("content") or rt.get_text()) if rt else None,
                             date_raw=dp.get("content")[:10] if dp else None,
                             location_raw=loc and clean(loc.get_text(" ")),
                             url=f"{url}#review-{rid}"))
        print("PC page", p, len(rows), flush=True); time.sleep(1.5)
    return rows

if __name__ == "__main__":
    cc = consumercomplaints(); json.dump(cc, open("raw/consumercomplaints.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    pc = pissedconsumer(); json.dump(pc, open("raw/pissedconsumer.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("DONE cc", len(cc), "pc", len(pc))
