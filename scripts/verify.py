import json, re, pandas as pd
x=pd.read_excel("output/urban_company_reviews_master.xlsx",sheet_name=None)
print({k:v.shape for k,v in x.items()})
m=x["Master"]; c=pd.read_csv("output/urban_company_reviews_master.csv",encoding="utf-8-sig",keep_default_na=False)
print("csv rows",len(c),"xlsx master rows",len(m), "unique uid",c.review_uid.nunique(), "unique (source,id)",len(c.drop_duplicates(["source","platform_review_id"])))
ILL=re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
raw={}
for f,k in [("play","text"),("apple","body"),("consumercomplaints","text"),("pissedconsumer","text")]:
    for r in json.load(open(f"raw/{f}.json",encoding="utf-8")): raw[(r["source"],r["review_id"])]=r[k]
bad=0
for r in c.itertuples():
    if raw[(r.source,str(r.platform_review_id))]!=r.review_text: bad+=1
print("CSV text differing from raw:",bad)
mm=m.fillna("").astype(str); bad2=sum(1 for a,b in zip(c.review_text,m.review_text.fillna("")) if ILL.sub("",a).replace("\r\n","\n")!=str(b).replace("\r\n","\n"))
print("xlsx text differing from csv (after stripping illegal ctrl chars):",bad2)
print("rows with control chars stripped for xlsx:",sum(1 for t in c.review_text if ILL.search(t)))
print(c.rating.replace("",None).dropna().astype(float).value_counts().sort_index().to_dict())
