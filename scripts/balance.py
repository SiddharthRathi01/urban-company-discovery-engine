import pandas as pd, re
df=pd.read_pickle("raw/master.pkl")
words=(df.review_title+" "+df.review_text).map(lambda t: len(re.findall(r"\w+",t)))
df["words"]=words
df["info_level"]=pd.cut(words,[-1,4,24,10000],labels=["Low (<5 words)","Standard (5-24)","Rich (25+)"])
def pol(r):
    if pd.isna(r): return "Unrated (complaint site)"
    return "Positive" if r>=3.5 else ("Negative" if r<=2.5 else "Mixed (3-star)")
df["polarity"]=df.rating.map(pol)
print(pd.crosstab(df.polarity,df.info_level,margins=True))
print(); print(pd.crosstab([df.source],df.polarity,margins=True))
sub=df[df.info_level!="Low (<5 words)"]; print("\nSTANDARD+RICH only:"); print(pd.crosstab(sub.source,sub.polarity,margins=True))
