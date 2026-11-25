"""STAGE C: apply analyst sentiment decisions, then write the authoritative master workbook + CSV IN PLACE (same two file names)."""
import json, os, re, datetime as dt
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

OUT = "output"
XLSX = f"{OUT}/urban_company_reviews_master.xlsx"
CSV = f"{OUT}/urban_company_reviews_master.csv"
df = pd.read_pickle("raw/candidates_scored.pkl")
logs = pd.read_pickle("raw/stage_a_logs.pkl")
AL = json.load(open("raw/analyst_labels.json", encoding="utf-8"))
val = json.load(open("raw/sentiment_validation_result.json", encoding="utf-8"))
LAB = {"P": "Positive", "N": "Negative", "M": "Mixed", "T": "Neutral", "U": "Uncertain"}

# ------------------------------------------------------------------ sentiment: lexicon draft + analyst read of the original text
lab, meth = [], []
n_read = n_over = 0
for r in df.itertuples():
    k = f"{r.platform}||{r.original_review_id}"
    if k in AL["labels"]:
        new = LAB[AL["labels"][k]]; lab.append(new); n_read += 1
        if new == r.draft_label: meth.append("Analyst read of original text (lexicon draft confirmed)")
        else: meth.append("Analyst read of original text (overrode lexicon draft)"); n_over += 1
    elif k in AL["read"]:
        lab.append(r.draft_label); meth.append("Analyst read of original text (lexicon draft confirmed)"); n_read += 1
    else:
        lab.append(r.draft_label); meth.append("Lexicon on text (clear polarity, consistent with star rating); validated on random samples")
df["sentiment_label"] = lab; df["sentiment_method"] = meth
queue_ids = set(range(n_read)); ov = {i: 1 for i in range(n_over)}   # counts only, used in the QC log

# ------------------------------------------------------------------ final master table in the required field order
bands = pd.cut(df.word_count, [-1, 4, 14, 39, 10**6], labels=["1-4 words", "5-14 words", "15-39 words", "40+ words"]).astype(str)
df["length_band"] = bands
M = df.rename(columns={"original_review_id": "original_review_id", "platform": "platform", "reviewer": "reviewer", "city_mentioned": "city"})
cols = ["record_id", "original_review_id", "review_text", "platform", "source_url", "url_type", "url_verification_status", "review_date", "rating",
        "reviewer", "service_category", "city", "sentiment_label", "sentiment_method", "word_count", "collection_date",
        "review_title", "content_type", "community", "length_band", "service_categories_all", "reviewer_profile_location", "engagement",
        "identical_short_text_flag", "app_version", "company_reply", "collection_note"]
M["reviewer_profile_location"] = M.reviewer_location
M = M[cols].sort_values(["platform", "review_date"], ascending=[True, False]).reset_index(drop=True)
from backend import data as _bd
_txt = (M.review_title.fillna("").str.strip() + " " + M.review_text.fillna("").str.strip()).str.strip()
_ins = _txt.str.contains(_bd.INSTA_NAMED) | M.service_categories_all.str.contains("Insta Help / House Help", regex=False) | M.record_id.isin(_bd.INSTA_UNNAMED_IDS)
INSTA = M[_ins].copy()                      # Step 2 scope: Insta Help reviews are removed from Master + CSV
M = M[~_ins].reset_index(drop=True)
M.to_pickle("raw/final_master.pkl")
DROP = ["sentiment_method", "word_count", "collection_date", "community", "length_band", "engagement", "identical_short_text_flag", "app_version", "company_reply", "collection_note", "url_verification_status"]
M_out = M.drop(columns=DROP)   # Step 2 cleanup: exactly these 11 columns are removed from Master + CSV
M_out.to_csv(CSV, index=False, encoding="utf-8-sig")

# ------------------------------------------------------------------ summary tables
order = [p for p in ["Google Play Store", "ConsumerComplaints.in", "PissedConsumer", "Reddit", "Apple App Store"] if p in set(M.platform)]
SENT = ["Positive", "Negative", "Neutral", "Mixed", "Uncertain"]
src = []
for p in order:
    g = M[M.platform == p]
    src.append([p, len(g), len(g) / len(M), g.review_date.min(), g.review_date.max(), int(g.rating.notna().sum()), round(g.rating.mean(), 2) if g.rating.notna().any() else None,
                int(g.url_verification_status.str.startswith("Verified").sum()), int((g.city != "").sum()), int((g.service_category != "").sum()), int(g.word_count.median())])
src.append(["TOTAL", len(M), 1.0, M.review_date.min(), M.review_date.max(), int(M.rating.notna().sum()), round(M.rating.mean(), 2), int(M.url_verification_status.str.startswith("Verified").sum()),
            int((M.city != "").sum()), int((M.service_category != "").sum()), int(M.word_count.median())])
SRC = pd.DataFrame(src, columns=["Platform", "Unique reviews", "Share of dataset", "Earliest review", "Latest review", "Reviews with star rating", "Avg rating (where rated)",
                                 "URLs machine-verified", "City explicitly mentioned", "Service category identified", "Median words"])
rt = M.assign(r=M.rating.map(lambda x: "No rating" if pd.isna(x) else (str(int(x)) + " star" if float(x).is_integer() else f"{x} star (decimal as shown)")))
RATING = pd.crosstab(rt.platform, rt.r).reindex(order); RATING["Total"] = RATING.sum(axis=1); RATING.loc["TOTAL"] = RATING.sum(); RATING = RATING.reset_index().rename(columns={"platform": "Platform", "r": ""})
sd = pd.crosstab(M.platform, M.sentiment_label).reindex(index=order, columns=SENT, fill_value=0); sd["Total"] = sd.sum(axis=1); sd.loc["TOTAL"] = sd.sum()
SENTP = sd.reset_index().rename(columns={"platform": "Platform"})
pct = (sd.drop(columns="Total").div(sd["Total"], axis=0) * 100).round(1).reset_index().rename(columns={"platform": "Platform (% of that platform)"})
xr = pd.crosstab(rt.r.where(rt.platform.isin(["Google Play Store", "PissedConsumer"]), "No rating"), M.sentiment_label).reindex(columns=SENT, fill_value=0)
xr = M[M.rating.notna()].assign(r=lambda d: d.rating.map(lambda x: f"{int(round(x))} star"))
XR = pd.crosstab(xr.r, xr.sentiment_label).reindex(columns=SENT, fill_value=0); XR["Total"] = XR.sum(axis=1); XR = XR.reset_index().rename(columns={"r": "Star rating (rated reviews only)"})
METH = M.sentiment_method.value_counts().rename_axis("Sentiment classification method").reset_index(name="Records")
CAT = pd.crosstab(M[M.service_category != ""].service_category, M[M.service_category != ""].platform).reindex(columns=order, fill_value=0); CAT["Total"] = CAT.sum(axis=1)
CAT = CAT.sort_values("Total", ascending=False).reset_index().rename(columns={"service_category": "Service category (keyword tag)"})
CITY = M[M.city != ""].city.str.split("; ").explode().value_counts().rename_axis("City explicitly mentioned in review text").reset_index(name="Reviews")
LEN = pd.crosstab(M.length_band, M.platform).reindex(index=["1-4 words", "5-14 words", "15-39 words", "40+ words"], columns=order, fill_value=0); LEN["Total"] = LEN.sum(axis=1)
LEN.loc["TOTAL"] = LEN.sum(); LEN = LEN.reset_index().rename(columns={"length_band": "Length band (title + text)"})
LC = logs["link_check"]
_keep = set(zip(M.platform, M.original_review_id.astype(str)))
LC = LC[[(a, str(b)) in _keep for a, b in zip(LC.platform, LC.original_review_id)]].reset_index(drop=True)
LCS = LC.assign(status=LC.url_verification_status.map(lambda s: "Not machine-verified (Reddit blocks automated access)" if s.startswith("Not machine") else ("Verified: individual URL, review ID and text found" if "ID and text" in s else ("Verified: text found at URL" if s.startswith("Verified") else "FAILED"))))
LCS = pd.crosstab(LCS.platform, LCS.status).reset_index().rename(columns={"platform": "Platform"})
excl = logs["excluded"].copy()
EX = pd.DataFrame(dict(platform=excl.platform, original_review_id=excl.original_review_id, exclusion_reason=excl.exclusion_reason, review_date=excl.review_date, rating=excl.rating,
                       review_title=excl.review_title, review_text=excl.review_text, url_candidate=excl.source_url.where(excl.source_url.fillna("") != "", "(none available)"), reviewer=excl.reviewer))
_ix = pd.DataFrame(dict(platform=INSTA.platform, original_review_id=INSTA.original_review_id, exclusion_reason="Out of Step 2 scope: Insta Help (instant house-help) review, removed from Master",
                        review_date=INSTA.review_date, rating=INSTA.rating, review_title=INSTA.review_title, review_text=INSTA.review_text, url_candidate=INSTA.source_url, reviewer=INSTA.reviewer))
EX = pd.concat([EX, _ix], ignore_index=True)
EX = EX.sort_values(["exclusion_reason", "platform"]).reset_index(drop=True)
# ------------------------------------------------------------------ duplicate-check sheet
dup_rows = []
for lab_, fr, _ in logs["dups"]:
    dup_rows.append([lab_, len(fr), "Removed"])
dup_rows.append(["4. Same short text (<40 chars) from different reviewers (e.g. 'Good service')", int((M.identical_short_text_flag == "Y").sum()), "KEPT and flagged (column identical_short_text_flag) for examination"])
DUPS = pd.DataFrame(dup_rows, columns=["Duplicate rule applied (in this order)", "Records affected", "Action"])
ex_dup = pd.concat([fr.assign(rule=lab_) for lab_, fr, _ in logs["dups"] if len(fr)], ignore_index=True) if any(len(fr) for _, fr, _ in logs["dups"]) else pd.DataFrame()
DUPX = pd.DataFrame(dict(rule=ex_dup.rule, platform=ex_dup.platform, original_review_id=ex_dup.original_review_id, reviewer=ex_dup.reviewer, review_date=ex_dup.review_date,
                         review_text=ex_dup.review_text.str.slice(0, 300))) if len(ex_dup) else pd.DataFrame(columns=["rule", "platform", "original_review_id", "reviewer", "review_date", "review_text"])
_t = M.review_text.str.strip().str.lower().str.replace(r"\W+", " ", regex=True).str.strip()
_g = M.assign(_t=_t)[(_t.str.len() < 40) & _t.duplicated(keep=False)]
SG = _g.groupby("_t").agg(**{"Short identical text": ("review_text", "first"), "Times repeated": ("review_text", "size"), "Platforms": ("platform", lambda x: ", ".join(sorted(set(x)))),
                         "Original review IDs": ("original_review_id", lambda x: ", ".join(x.astype(str)))}).reset_index(drop=True).sort_values("Times repeated", ascending=False)

# ------------------------------------------------------------------ QC log
qc = list(logs["qc"])
qc += [("", ""), ("STEP 2 SCOPE: INSTA HELP REMOVED FROM MASTER", ""), ("Insta Help (instant house-help) reviews removed from Master and CSV", len(INSTA))]
for _p, _n in INSTA.platform.value_counts().items(): qc.append((f"   of which {_p}", int(_n)))
qc += [("", ""), ("FINAL DATASET", ""), ("Final unique reviews in Master (all with a verified/identifiable individual source URL; Insta Help removed)", len(M))]
for p in order: qc.append((f"   {p}", int((M.platform == p).sum())))
qc.append(("Rows with an individually verified URL (review text located at the URL)", int(M.url_verification_status.str.startswith("Verified").sum())))
qc.append(("Rows with a Reddit permalink (taken from archive record; not machine-verifiable)", int((M.platform == "Reddit").sum())))
qc.append(("Rows missing review date", int(M.review_date.isna().sum())))
qc.append(("Rows missing review text", int((M.review_text.str.strip() == "").sum())))
qc.append(("Rows missing source URL", int((M.source_url.fillna("") == "").sum())))
qc.append(("Rows missing reviewer name / handle", int((M.reviewer.fillna("") == "").sum())))
qc.append(("Rows with no star rating (platform does not provide one)", int(M.rating.isna().sum())))
qc += [("", ""), ("SENTIMENT VALIDATION", "")]
if val:
    qc += [("Random sample of auto-labelled rows read by the analyst", val["n"]), ("   labels agreed with the analyst's reading", val["agree"]), ("   agreement rate", f"{val['agree']/val['n']:.0%}"),
           ("Rows in the analyst review queue (read individually)", len(queue_ids)), ("   of which analyst changed the lexicon label", len(ov))]
QC = pd.DataFrame(qc, columns=["Check", "Count / result"])

# ------------------------------------------------------------------ workbook
wb = Workbook(); HDR = PatternFill("solid", fgColor="1F3864"); HF = Font(bold=True, color="FFFFFF", name="Calibri", size=11)
ILL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]"); clean = lambda v: ILL.sub("", v) if isinstance(v, str) else v
def table(ws, frame, widths=None, start=1, wrap=(), links=(), height=None):
    for j, c in enumerate(frame.columns, 1):
        x = ws.cell(row=start, column=j, value=str(c)); x.fill = HDR; x.font = HF; x.alignment = Alignment(wrap_text=True, vertical="center")
    for i, rec in enumerate(frame.itertuples(index=False), start + 1):
        for j, v in enumerate(rec, 1):
            if v is not None and not isinstance(v, str) and pd.isna(v): v = None
            if hasattr(v, "item"): v = v.item()
            x = ws.cell(row=i, column=j, value=clean(v)); col = frame.columns[j - 1]
            x.alignment = Alignment(wrap_text=col in wrap, vertical="top")
            if col in links and isinstance(v, str) and v.startswith("http"): x.hyperlink = v; x.font = Font(color="0563C1", underline="single")
            if height and col in wrap: ws.row_dimensions[i].height = height
    for j, c in enumerate(frame.columns, 1): ws.column_dimensions[get_column_letter(j)].width = (widths or {}).get(c, 16)
    ws.row_dimensions[start].height = 32

today = dt.date.today().strftime("%d %B %Y")
n = lambda p: int((M.platform == p).sum()); tot = len(M)
sc = M.sentiment_label.value_counts()
lines = [
 ("Urban Company - Public Customer Review Dataset (master, expanded and verified)", "title"),
 (f"Last updated {today}. {tot:,} unique public reviews/discussions, each with an individually traceable source URL. Public sources only; no logged-in Urban Company pages or app data.", None),
 ("", None),
 ("WORKBOOK GUIDE", "h"),
 ("Master - the authoritative dataset (one row per review). The CSV file is an identical copy of this sheet. Filter on any column; source_url is clickable.", None),
 (f"Insta Help exclusion: {len(INSTA)} Insta Help (instant house-help) reviews were removed from Master and the CSV for Step 2 and are kept, with their full text, on the Excluded Records sheet. Remaining records keep their original record_ids, so IDs are stable but not contiguous.", None),
 ("Step 2 cleanup: the following 11 columns were removed from Master and the CSV (no records were removed): sentiment_method, word_count, collection_date, community, length_band, engagement, identical_short_text_flag, app_version, company_reply, collection_note, url_verification_status. URL verification results remain on the Link Check sheet; the Length Distribution sheet and QC Log keep their counts from the earlier build.", None),
 ("Source Summary, Rating by Source, Sentiment Distribution, Category Tags, City Tags, Length Distribution - counts only. QC Log, Duplicate Check, Link Check, Excluded Records - audit trail for every inclusion/exclusion decision.", None),
 ("", None),
 ("INCLUSION RULES (all must hold)", "h"),
 ("1. Genuine public text written by a customer or prospective customer about Urban Company (booking, pricing, refunds, professionals, the app, support, Native products, or comparing/switching to alternatives). Positive, negative, neutral and mixed accounts are all kept.", None),
 ("2. MANDATORY TRACEABILITY: a stable URL that leads to that individual review/post, where its text can be located. Generic app pages, homepages and rolling listing pages (whose page numbers drift as new reviews arrive) do not qualify. URLs were never guessed; they were taken from the source or are the platform's own documented review-link format, and were then re-fetched to confirm the review is on the page (Link Check).", None),
 ("3. Not a duplicate (see Duplicate Check) and not professional-side, spam, solicitation, news/job posts or unreadable (see Excluded Records).", None),
 ("Short genuine reviews are kept; nothing is rewritten, paraphrased or expanded. review_text is the exact original wording.", None),
 ("", None),
 ("EXCLUSION RULES AND DECISIONS", "h"),
 (f"Apple App Store - EXCLUDED ENTIRELY ({int((excl.platform=='Apple App Store').sum())} collected). Apple's public feed gives no per-review URL; the reviewer-profile link is a non-public 'Connecting to the iTunes Store' stub and the app page does not contain the review text. The RSS feed pages are rolling (a review shifts to another page within days), so they cannot serve as a stable address. Under the traceability rule these cannot be included.", None),
 ("ConsumerComplaints.in / PissedConsumer - only complaints/reviews whose individual page URL is exposed by the site are kept. Older entries appear only on rolling listing pages (no individual URL) and are excluded, even though the text was collected.", None),
 ("Trustpilot - bot challenge (HTTP 403); not bypassed, not collected. YouTube comments - require a YouTube Data API key (not available), not collected. Quora - bot challenge; MouthShut/Sitejabber - no usable Urban Company review listings. Urban Company's own /reviews page - only ~10 curated reviews, not independent.", None),
 ("", None),
 ("HOW EACH SOURCE WAS COLLECTED", "h"),
 (f"Google Play ({n('Google Play Store'):,}): India/English. Stratified by star (newest 200 + most-relevant 60 per star), plus random top-ups of detailed 4-5 star (350) and 2-3 star (200) reviews to represent positive, mixed and neutral experiences. Link format: play.google.com/store/apps/details?id=com.urbanclap.urbanclap&reviewId=<id> - Google's review link; every URL was fetched and the review ID and text found on the page.", None),
 (f"ConsumerComplaints.in ({n('ConsumerComplaints.in')}) and PissedConsumer ({n('PissedConsumer')}): all listing pages scanned; only entries with their own page kept. These sites are complaint platforms and skew negative by nature; they are a minority of the dataset.", None),
 (f"Reddit ({n('Reddit')}): posts naming Urban Company/UrbanClap in Indian city and household subreddits; every post was read and judged relevant or not (Excluded Records). reddit.com blocks automated access, so text and permalink come from the Arctic Shift public archive; links go to the original reddit.com threads and could not be machine-verified. Comment-level search in the archive timed out, so Reddit coverage is posts only. Posts with no body are stored as their title (content_type = 'Post (title only)').", None),
 ("", None),
 ("SENTIMENT CLASSIFICATION METHOD", "h"),
 ("Labels (Positive, Negative, Neutral, Mixed, Uncertain) describe the REVIEW TEXT and were assigned after collection; star rating is not sentiment and was used only as a tie-breaker when text carried no polarity.", None),
 ("Step 1 - a VADER lexicon extended with home-services vocabulary produced a draft label per sentence/clause. Step 2 - drafts that were strongly polar and consistent with the star rating were auto-accepted (spot-validated). Step 3 - every other review (weak, conflicting, mixed, neutral, unrated Reddit/complaint text, non-English) was read individually by the analyst (Claude) from the original text and confirmed or overridden. (The per-row method column was removed from Master in the Step 2 cleanup; the breakdown of how labels were assigned is kept in the Sentiment Distribution sheet.)", None),
 ("Neutral = questions, enquiries and factual statements with no evaluation. Mixed = clearly positive and clearly negative statements in the same review. Uncertain = text unreadable/non-English or contradicting the rating so that the label cannot be asserted.", None),
 (f"Validation: the first auto-accept rule agreed with the analyst on {val['round1_agree']} of {val['round1_n']} random auto-labelled reviews ({val['round1_agree']/val['round1_n']:.0%}); every disagreement was a lukewarm 4-star 'positive' (e.g. 'could be better'). The rule was then tightened so such reviews are read individually, and a fresh random sample agreed on {val['agree']} of {val['n']} ({val['agree']/val['n']:.0%}). All disagreements were corrected in the data; the same phrases were searched for across all auto-labelled rows.", None),
 ("", None),
 ("FIELD DEFINITIONS", "h"),
 ("record_id (unique, platform-prefixed) | original_review_id (the platform's own ID) | review_text (exact original) | platform | source_url | url_type | review_date | rating (as shown by the platform; blank if none) | reviewer (public display name/handle) | service_category (keyword tag, only where the text names a service) | city (only where the text names a city) | sentiment_label.", None),
 ("Other columns: review_title (separate title where the platform has one), content_type, service_categories_all, reviewer_profile_location (profile field on complaint sites - NOT used as city).", None),
 ("", None),
 ("LIMITATIONS", "h"),
 ("Sample, not census: customers who simply stopped booking leave no review. Play dominates the dataset because it is the only large platform with verifiable individual review links; complaint platforms skew negative; Reddit is posts only and over-represents people asking for advice. Service category and city are first-pass keyword tags and are blank when the text does not name them. Sentiment labels are text-based judgments and ambiguous cases are labelled Mixed/Uncertain, not forced.", None),
]
ws = wb.active; ws.title = "README"
for i, (t, kind) in enumerate(lines, 1):
    c = ws.cell(row=i, column=1, value=t); c.alignment = Alignment(wrap_text=True, vertical="top")
    if kind == "title": c.font = Font(bold=True, size=16, color="1F3864")
    elif kind == "h": c.font = Font(bold=True, color="FFFFFF"); c.fill = HDR
ws.column_dimensions["A"].width = 150

W = {"record_id": 10, "original_review_id": 22, "review_text": 90, "platform": 20, "source_url": 50, "url_type": 34, "url_verification_status": 40, "review_date": 12, "rating": 8,
     "reviewer": 22, "service_category": 22, "city": 14, "sentiment_label": 12, "sentiment_method": 44, "word_count": 8, "collection_date": 12, "review_title": 28, "content_type": 16,
     "community": 16, "length_band": 13, "service_categories_all": 28, "reviewer_profile_location": 28, "engagement": 10, "identical_short_text_flag": 12, "app_version": 10, "company_reply": 40, "collection_note": 44}
ws = wb.create_sheet("Master"); table(ws, M_out, W, wrap=("review_text", "review_title"), links=("source_url",), height=60); ws.freeze_panes = "D2"; ws.auto_filter.ref = ws.dimensions
for name, fr, w in [("Source Summary", SRC, {"Platform": 24}), ("Rating by Source", RATING, {"Platform": 24})]:
    ws = wb.create_sheet(name); table(ws, fr, {c: w.get(c, 20) for c in fr.columns}); ws.freeze_panes = "B2"
ws = wb.create_sheet("Sentiment Distribution")
table(ws, SENTP, {c: 18 for c in SENTP.columns}); r0 = len(SENTP) + 3
ws.cell(row=r0 - 1, column=1, value="Share of each platform's reviews (%)").font = Font(bold=True); table(ws, pct, start=r0); r1 = r0 + len(pct) + 3
ws.cell(row=r1 - 1, column=1, value="Text sentiment vs star rating (rated reviews) - shows rating is not sentiment").font = Font(bold=True); table(ws, XR, start=r1); r2 = r1 + len(XR) + 3
ws.cell(row=r2 - 1, column=1, value="How each label was assigned").font = Font(bold=True); table(ws, METH, start=r2); ws.column_dimensions["A"].width = 58
for name, fr, w in [("Category Tags", CAT, {"Service category (keyword tag)": 34}), ("City Tags", CITY, {"City explicitly mentioned in review text": 40}), ("Length Distribution", LEN, {"Length band (title + text)": 28})]:
    ws = wb.create_sheet(name); table(ws, fr, {c: w.get(c, 20) for c in fr.columns})
ws = wb.create_sheet("QC Log"); table(ws, QC, {"Check": 100, "Count / result": 20})
ws = wb.create_sheet("Duplicate Check"); table(ws, DUPS, {"Duplicate rule applied (in this order)": 80, "Records affected": 16, "Action": 70}); r = len(DUPS) + 3
ws.cell(row=r - 1, column=1, value="Duplicate records removed (rules 1-3)").font = Font(bold=True)
if len(DUPX): table(ws, DUPX, start=r, wrap=("review_text",)); r += len(DUPX) + 3
else: ws.cell(row=r, column=1, value="None found"); r += 3
ws.cell(row=r - 1, column=1, value="Short identical texts kept and flagged for examination (rule 4)").font = Font(bold=True); table(ws, SG, start=r, wrap=("Original review IDs",))
ws.column_dimensions["B"].width = 18; ws.column_dimensions["C"].width = 70; ws.column_dimensions["D"].width = 60
ws = wb.create_sheet("Link Check"); table(ws, LCS, {"Platform": 26} | {c: 36 for c in LCS.columns[1:]}); r = len(LCS) + 4
ws.cell(row=r - 1, column=1, value="Every URL checked (retained records) - failed URLs were excluded and are listed in Excluded Records").font = Font(bold=True)
LD = LC.rename(columns={"platform": "Platform", "original_review_id": "Original review ID", "source_url": "Source URL", "url_type": "URL type", "http_status": "HTTP status", "url_verification_status": "Verification status"})
table(ws, LD, {"Platform": 22, "Original review ID": 24, "Source URL": 70, "URL type": 40, "HTTP status": 12, "Verification status": 60}, start=r, links=("Source URL",))
ws = wb.create_sheet("Excluded Records")
table(ws, EX, {"platform": 22, "original_review_id": 22, "exclusion_reason": 70, "review_date": 12, "rating": 8, "review_title": 30, "review_text": 80, "url_candidate": 50, "reviewer": 22}, wrap=("review_text", "review_title", "exclusion_reason"), links=("url_candidate",), height=45)
ws.freeze_panes = "A2"; ws.auto_filter.ref = ws.dimensions
wb.save(XLSX)
print("saved", XLSX, "and", CSV, "| rows:", len(M))
print(SRC.to_string()); print(SENTP.to_string()); print(LEN.to_string())
