import re, collections, pandas as pd
df=pd.read_csv("output/urban_company_reviews_master.csv",encoding="utf-8-sig",keep_default_na=False,dtype=str)
df["tx"]=(df.review_title+" "+df.review_text).str.lower()
STOP=set("the a an and or but of to in on at for with is are was were be been it its this that i we you they he she my our your their me us them as by from have has had not no do does did so very just also will would can could if then than there here when what which who how all any some more most one two get got".split())
def grams(texts,n):
    c=collections.Counter()
    for t in texts:
        w=[x for x in re.findall(r"[a-z']+",t)]
        seen=set()
        for i in range(len(w)-n+1):
            g=w[i:i+n]
            if g[0] in STOP or g[-1] in STOP: continue
            if sum(x in STOP for x in g)>n-1: continue
            seen.add(" ".join(g))
        c.update(seen)
    return c
for name,sub in [("Negative (all)",df[df.sentiment_label=="Negative"]),("Positive",df[df.sentiment_label=="Positive"]),("Mixed",df[df.sentiment_label=="Mixed"]),("Reddit",df[df.platform=="Reddit"])]:
    print("\n=====",name,len(sub))
    for n in (2,3):
        print(f" top {n}-grams:",[f"{g}({c})" for g,c in grams(sub.tx,n).most_common(34)])
