"""Write the Excel workbook + CSV from the cleaned master dataset."""
import re, datetime as dt
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

OUT = "output"
df = pd.read_pickle("raw/master.pkl")
qc = pd.read_pickle("raw/qc.pkl")
excluded = pd.read_pickle("raw/excluded.pkl")
links = pd.read_pickle("raw/linkcheck.pkl")
ILLEGAL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")

# ---------------------------------------------------------------- CSV (text kept exactly as collected)
csv_path = f"{OUT}/urban_company_reviews_master.csv"
df.to_csv(csv_path, index=False, encoding="utf-8-sig")
excluded.to_csv(f"{OUT}/urban_company_excluded_not_relevant.csv", index=False, encoding="utf-8-sig")

# ---------------------------------------------------------------- summaries
order = [o for o in ["Google Play Store", "Apple App Store", "ConsumerComplaints.in", "PissedConsumer", "Reddit"] if o in set(df.source)]
platform_url = {
    "Google Play Store": "https://play.google.com/store/apps/details?id=com.urbanclap.urbanclap&hl=en_IN",
    "Apple App Store": "https://apps.apple.com/in/app/urban-company-home-services/id1032480595",
    "ConsumerComplaints.in": "https://www.consumercomplaints.in/urban-company-b115885",
    "PissedConsumer": "https://urban-company.pissedconsumer.com/review.html",
    "Reddit": "https://www.reddit.com/search/?q=%22urban%20company%22",
}
rows = []
for s in order:
    g = df[df.source == s]
    rows.append([s, len(g), len(g) / len(df), g.review_date.min(), g.review_date.max(),
                 int(g.rating.notna().sum()), round(g.rating.mean(), 2) if g.rating.notna().any() else None,
                 int((g.city_mentioned != "").sum()), int((g.service_category != "").sum()),
                 int(g.review_date.isna().sum()), int(g.text_length_chars.median()), platform_url[s]])
summary_cols = ["Source", "Unique reviews", "Share of dataset", "Earliest review", "Latest review", "Reviews with star rating",
                "Avg rating (where rated)", "City mentioned in text", "Service category identified", "Missing date",
                "Median text length (chars)", "Source page"]
rows.append(["TOTAL", len(df), 1.0, df.review_date.min(), df.review_date.max(), int(df.rating.notna().sum()),
             round(df.rating.mean(), 2), int((df.city_mentioned != "").sum()), int((df.service_category != "").sum()),
             int(df.review_date.isna().sum()), int(df.text_length_chars.median()), ""])
summary = pd.DataFrame(rows, columns=summary_cols)

rating = (df[df.rating.notna()].assign(r=lambda x: x.rating.astype(int)).pivot_table(index="source", columns="r", values="review_uid", aggfunc="count", fill_value=0)
          .reindex([s for s in order if s in df[df.rating.notna()].source.unique()]))
rating.columns = [f"{c}-star" for c in rating.columns]; rating["Total rated"] = rating.sum(axis=1); rating = rating.reset_index().rename(columns={"source": "Source"})

bal = pd.crosstab(df.source, df.rating_polarity); bal["Total"] = bal.sum(axis=1)
bal = bal.reindex(order); bal.loc["ALL SOURCES"] = bal.sum(); bal = bal.reset_index().rename(columns={"source": "Source", "rating_polarity": ""})
bal2 = pd.crosstab(df.rating_polarity, df.info_level); bal2["Total"] = bal2.sum(axis=1); bal2.loc["ALL"] = bal2.sum(); bal2 = bal2.reset_index().rename(columns={"rating_polarity": "Polarity (rating-based proxy)"})
cat = (df[df.service_category != ""].pivot_table(index="service_category", columns="source", values="review_uid", aggfunc="count", fill_value=0)
       .reindex(columns=order, fill_value=0)); cat["Total"] = cat.sum(axis=1); cat = cat.sort_values("Total", ascending=False).reset_index().rename(columns={"service_category": "Service category (keyword tag)"})
city = df[df.city_mentioned != ""].city_mentioned.str.split("; ").explode().value_counts().rename_axis("City mentioned in review text").reset_index(name="Reviews")

# ---------------------------------------------------------------- workbook
wb = Workbook()
HDR = PatternFill("solid", fgColor="1F3864"); HF = Font(bold=True, color="FFFFFF", name="Calibri", size=11)
thin = Side(style="thin", color="D9D9D9"); BORDER = Border(bottom=thin)
clean = lambda v: ILLEGAL.sub("", v) if isinstance(v, str) else v


def write_table(ws, frame, widths=None, start_row=1, wrap_cols=(), link_cols=()):
    for j, c in enumerate(frame.columns, 1):
        cell = ws.cell(row=start_row, column=j, value=c); cell.fill = HDR; cell.font = HF
        cell.alignment = Alignment(wrap_text=True, vertical="center")
    for i, rec in enumerate(frame.itertuples(index=False), start_row + 1):
        for j, v in enumerate(rec, 1):
            if pd.isna(v) if not isinstance(v, (list, dict)) else False: v = None
            cell = ws.cell(row=i, column=j, value=clean(v))
            col = frame.columns[j - 1]
            cell.alignment = Alignment(wrap_text=col in wrap_cols, vertical="top")
            if col in link_cols and isinstance(v, str) and v.startswith("http"):
                cell.hyperlink = v; cell.font = Font(color="0563C1", underline="single")
    if widths:
        for j, c in enumerate(frame.columns, 1): ws.column_dimensions[get_column_letter(j)].width = widths.get(c, 16)
    ws.freeze_panes = ws.cell(row=start_row + 1, column=1)
    ws.row_dimensions[start_row].height = 32


# --- README
ws = wb.active; ws.title = "README"
today = dt.date.today().strftime("%d %B %Y")
n = lambda src: int((df.source == src).sum())
pos = int((df.rating_polarity == "Positive (4-5 stars)").sum()); neg = int((df.rating_polarity == "Negative (1-2 stars)").sum())
mix = int((df.rating_polarity == "Mixed (3 stars)").sum()); unr = int((df.rating_polarity == "Unrated").sum())
sub = df[df.info_level != "Low (<5 words)"]
spos = int((sub.rating_polarity == "Positive (4-5 stars)").sum()); sneg = int((sub.rating_polarity == "Negative (1-2 stars)").sum()); smix = int((sub.rating_polarity == "Mixed (3 stars)").sum())
lines = [
    ("Urban Company - Public Customer Review Dataset (Step 1)", "title"),
    (f"Collected {today} from publicly accessible sources only. No logged-in Urban Company pages or app data were used.", None),
    (f"{len(df):,} relevant, de-duplicated reviews in Master  |  {len(excluded)} entries removed as not relevant (see 'Excluded - Not Relevant')", None),
    ("", None),
    ("WHAT'S IN THIS WORKBOOK", "h"),
    ("Master - all relevant unique reviews, one row each. Filterable; frozen header; source_url is clickable.", None),
    ("Excluded - Not Relevant - entries removed by the relevance audit, each with the reason, so every decision can be checked or reversed.", None),
    ("Source Summary / Rating by Source / Balance (Polarity) / Balance x Detail / Category Tags / City Tags - counts only; no analysis.", None),
    ("QC Log - duplicate, missing-field and relevance checks. Link Check - result of source-link validation.", None),
    ("", None),
    ("RELEVANCE AUDIT (what 'relevant' means here)", "h"),
    ("Relevant = a customer's (or prospective customer's) account of, question about, or opinion on Urban Company: booking, pricing, refunds, professionals, the app, support, Native products, or comparisons/switching to alternatives. Positive and negative are both kept.", None),
    ("Excluded: professional/partner-side posts (e.g. a technician asking for a joining fee back), spam/scam listings, unreadable/no-content entries, and (Reddit) investor/IPO talk with no customer-experience content.", None),
    ("How it was checked: every PissedConsumer and ConsumerComplaints entry was read; a random sample of 100 app-store reviews was read (99/100 relevant); keyword sweeps for partner-side language, spam, other companies and gibberish were run over everything and each hit was read. Reddit mentions were screened with explicit-mention and investor-talk filters and then read.", None),
    ("Kept on purpose: competitor comparisons (Pronto, Snabbit, NoBroker...), questions/enquiries (they show unmet needs and can't-reach-support moments), Native water-purifier/lock reviews (Urban Company's own product), and very short generic reviews (flagged via info_level = 'Low').", None),
    ("", None),
    ("POSITIVE vs NEGATIVE BALANCE", "h"),
    (f"By star rating (rated reviews): {pos} positive (4-5 stars), {mix} mixed (3 stars), {neg} negative (1-2 stars); {unr} unrated (complaint-site entries and Reddit, which carry no star rating).", None),
    (f"Reviews with real content (5+ words): {spos} positive, {smix} mixed, {sneg} negative. A detailed-positive top-up of 350 Play reviews was added because the first pass had only 482 detailed positives against 669 detailed negatives, and 35% of positive reviews were one-liners like 'Good'.", None),
    ("Rating is only a proxy for polarity. No sentiment analysis has been done; that is a later step. Complaint sites (ConsumerComplaints, PissedConsumer) are negative by nature.", None),
    ("", None),
    ("COLUMN NOTES", "h"),
    ("review_text / review_title - original text exactly as published; nothing summarised or edited. Apple reviews and complaint-site entries have a separate title; Play Store reviews have none. Reddit: title is the post title (blank for comments).", None),
    ("content_type / community - App review, Complaint, or Reddit Post/Comment; community is the subreddit for Reddit rows.", None),
    ("rating - 1-5 stars where the platform provides it (Play, Apple; PissedConsumer only when the reviewer gave one). ConsumerComplaints.in and Reddit have no star ratings, so blank. PissedConsumer shows a few decimal ratings (e.g. 1.4); kept as displayed on the site.", None),
    ("rating_polarity - rating-based proxy only: Positive 4-5, Mixed 3, Negative 1-2, Unrated. info_level - Low (<5 words), Standard (5-24), Rich (25+).", None),
    ("engagement - Play 'thumbs up' count or Reddit score. reviewer_name - display name/handle as shown publicly; not invented or altered.", None),
    ("service_category / service_categories_all - FIRST-PASS KEYWORD TAG on title+text where a service is explicitly named (e.g. 'plumber', 'massage'). Blank when none is named. To be refined later; not ground truth.", None),
    ("city_mentioned - city named inside the review text itself. reviewer_location - location shown on the reviewer's profile (complaint sites only); a profile field, not a statement in the review.", None),
    ("source_url / url_type - Play and Reddit: direct link to the review/post/comment. ConsumerComplaints.in: direct complaint page. PissedConsumer: listing page + #review-ID anchor. Apple: the app's public review page; Apple's RSS feed provides no per-review permalink.", None),
    ("identical_short_text_flag - 'Y' where a short text (<40 chars, e.g. 'Good service') appears more than once from different reviewers. Kept: they are different people's reviews.", None),
    ("", None),
    ("HOW THE DATA WAS COLLECTED", "h"),
    (f"Google Play (India, English): {n('Google Play Store'):,} reviews - stratified by star (newest 200 + 60 most-relevant per star, de-duplicated) plus the 350-review detailed-positive top-up (random sample from a pool of 1,414 four/five-star reviews of 8+ words).", None),
    (f"Apple App Store (India): {n('Apple App Store')} - the 500 most recent reviews, the hard maximum the public RSS feed returns.", None),
    (f"ConsumerComplaints.in ({n('ConsumerComplaints.in')}) and PissedConsumer ({n('PissedConsumer')}): pages sampled evenly across each site's whole archive for time diversity.", None),
    (f"Reddit ({n('Reddit')}): posts and comments naming Urban Company/UrbanClap in Indian city and household subreddits. reddit.com blocks unauthenticated clients, so the text comes from the Arctic Shift public Reddit archive; links point to the original reddit.com threads. Deleted/removed items are not included.", None),
    ("", None),
    ("SOURCES CHECKED BUT NOT USED", "h"),
    ("Trustpilot - blocked automated access (bot challenge, HTTP 403). Not bypassed.", None),
    ("Quora - bot challenge (HTTP 403). Not bypassed.", None),
    ("urbancompany.com/reviews - Urban Company's own showcase page; only ~10 reviews server-rendered, company-curated. Not used.", None),
    ("Sitejabber - only 1 review. MouthShut - no usable Urban Company listing found. YouTube comments - need a YouTube Data API key (not collected).", None),
    ("", None),
    ("KNOWN BIASES (for later steps)", "h"),
    ("Complaint sites contain complaints by design. App-store reviews skew to extremes. Customers who simply stopped booking leave no review at all. The dataset is a sample, not a census.", None),
]
for i, (t, kind) in enumerate(lines, 1):
    c = ws.cell(row=i, column=1, value=t); c.alignment = Alignment(wrap_text=True, vertical="top")
    if kind == "title": c.font = Font(bold=True, size=16, color="1F3864")
    elif kind == "h": c.font = Font(bold=True, size=11, color="FFFFFF"); c.fill = HDR
ws.column_dimensions["A"].width = 140

# --- Master
ws = wb.create_sheet("Master")
widths = {"review_uid": 10, "source": 22, "review_title": 28, "review_text": 90, "rating": 8, "rating_scale": 10, "review_date": 12,
          "reviewer_name": 22, "service_category": 22, "service_categories_all": 28, "city_mentioned": 16, "reviewer_location": 28,
          "source_url": 45, "url_type": 30, "platform_review_id": 20, "app_version": 10, "engagement": 10, "content_type": 16, "community": 16, "rating_polarity": 20, "info_level": 20, "word_count": 8, "company_reply": 40,
          "text_length_chars": 10, "identical_short_text_flag": 12, "collection_note": 40, "collected_on": 12}
write_table(ws, df, widths, wrap_cols=("review_text", "review_title", "company_reply"), link_cols=("source_url",))
ws.auto_filter.ref = ws.dimensions
ws2 = wb.create_sheet("Excluded - Not Relevant")
write_table(ws2, excluded, dict(widths) | {"relevance_status": 28, "relevance_note": 60}, wrap_cols=("review_text", "review_title", "relevance_note"), link_cols=("source_url",))
for r in range(2, ws2.max_row + 1): ws2.row_dimensions[r].height = 60
ws2.auto_filter.ref = ws2.dimensions
# keep rows readable: cap row height
for r in range(2, ws.max_row + 1): ws.row_dimensions[r].height = 60

# --- Source Summary
ws = wb.create_sheet("Source Summary")
write_table(ws, summary, {c: 18 for c in summary.columns} | {"Source": 24, "Source page": 70}, link_cols=("Source page",))
for r in range(2, len(summary) + 2): ws.cell(row=r, column=3).number_format = "0.0%"
for c in range(1, len(summary.columns) + 1): ws.cell(row=len(summary) + 1, column=c).font = Font(bold=True)
ws.freeze_panes = "B2"

for name, frame, w in [("Rating by Source", rating, {"Source": 24}), ("Balance (Polarity)", bal, {"Source": 24}), ("Balance x Detail", bal2, {"Polarity (rating-based proxy)": 30}), ("Category Tags", cat, {"Service category (keyword tag)": 34}), ("City Tags", city, {"City mentioned in review text": 34})]:
    ws = wb.create_sheet(name); write_table(ws, frame, {c: w.get(c, 18) for c in frame.columns})

ws = wb.create_sheet("QC Log"); write_table(ws, qc.rename(columns={"check": "Check", "count": "Count"}), {"Check": 95, "Count": 12})
ws = wb.create_sheet("Link Check")
lc = links.rename(columns={"http_status": "HTTP status", "review_text_found_on_page": "Review text/ID found on page", "check": "Check type"})
write_table(ws, lc, {"review_uid": 16, "source": 24, "url": 80, "HTTP status": 12, "Review text/ID found on page": 18, "Check type": 28}, link_cols=("url",))

xlsx_path = f"{OUT}/urban_company_reviews_master.xlsx"
wb.save(xlsx_path)
print("saved", xlsx_path, csv_path)
print(summary.to_string())
