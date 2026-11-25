"""Validate source links. CC/PC: every link fetched and the review text/ID confirmed on the page.
Play: random sample (Play serves the same app page for any reviewId, so only reachability is testable without JS).
Apple: app review page reachability."""
import re, time, random, requests, pandas as pd
from concurrent.futures import ThreadPoolExecutor
from bs4 import BeautifulSoup
H={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36"}
df=pd.read_pickle("raw/master.pkl")
norm=lambda t: re.sub(r"\W+"," ",t.casefold()).strip()
res=[]
def fetch(u):
    for _ in range(3):
        try:
            r=requests.get(u,headers=H,timeout=30)
            return r.status_code,r.text
        except Exception as e: err=str(e); time.sleep(2)
    return 0,err
def chk_cc(row):
    code,html=fetch(row.source_url); time.sleep(0.3)
    ok = code==200 and norm(row.review_text)[:60] in norm(BeautifulSoup(html,"html.parser").get_text(" ")) if code==200 else False
    return dict(review_uid=row.review_uid,source=row.source,url=row.source_url,http_status=code,review_text_found_on_page=ok,check="full")
cc=df[df.source=="ConsumerComplaints.in"]
with ThreadPoolExecutor(4) as ex: res+=list(ex.map(chk_cc,cc.itertuples()))
# PissedConsumer: group by listing page
pc=df[df.source=="PissedConsumer"]; cache={}
for row in pc.itertuples():
    page=row.source_url.split("#")[0]
    if page not in cache: cache[page]=fetch(page); time.sleep(1)
    code,html=cache[page]
    res.append(dict(review_uid=row.review_uid,source=row.source,url=row.source_url,http_status=code,
                    review_text_found_on_page=(code==200 and f'id="review-{row.platform_review_id}"' in html),check="full"))
random.seed(7)
gp=df[df.source=="Google Play Store"]; samp=gp.sample(40,random_state=7)
def chk_gp(row):
    code,_=fetch(row.source_url); time.sleep(0.3)
    return dict(review_uid=row.review_uid,source=row.source,url=row.source_url,http_status=code,review_text_found_on_page=None,check="sample (reachability only)")
with ThreadPoolExecutor(3) as ex: res+=list(ex.map(chk_gp,samp.itertuples()))
code,_=fetch(df[df.source=="Apple App Store"].source_url.iloc[0])
res.append(dict(review_uid="AS-* (all 500)",source="Apple App Store",url=df[df.source=="Apple App Store"].source_url.iloc[0],http_status=code,review_text_found_on_page=None,check="app page reachability"))
out=pd.DataFrame(res); out.to_pickle("raw/linkcheck.pkl")
print(out.groupby(["source","check"]).agg(n=("url","size"),http200=("http_status",lambda s:(s==200).sum()),text_found=("review_text_found_on_page",lambda s:s.fillna(False).sum())))
print(out[(out.http_status!=200)|(out.review_text_found_on_page==False)].head(20))
