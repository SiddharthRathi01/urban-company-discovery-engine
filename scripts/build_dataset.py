"""Build the Step-1 master dataset (Excel + CSV) from raw/*.json.

No summarising or rewriting of review text. Only: normalise fields, tag service category / city
via explicit keyword matches, remove duplicates, run QC checks, write outputs.
"""
import json, re, sys, datetime as dt
from collections import Counter
import pandas as pd

RAW = "raw"
OUT = "output"
APPLE_APP_PAGE = "https://apps.apple.com/in/app/urban-company-home-services/id1032480595?see-all=reviews"
TODAY = dt.date.today().isoformat()

# ---------------------------------------------------------------- keyword tagging (explicit mentions only)
CATEGORY_PATTERNS = {
    "AC Service & Repair": r"\bacs?\b|air[\s-]?condition|split ac|ac (?:service|repair|gas|install|servic)",
    "Salon & Beauty": r"salon|beaut(?:y|ician)|facial|wax(?:ing)?|threading|manicure|pedicure|makeup|make-up|bridal|haircut|hair ?cut|hair ?colou?r|bleach|cleanup|clean-up|\bspa\b|mehendi|mehndi|\bnails?\b",
    "Massage & Spa": r"massage|therapist|body spa|\bspa\b",
    "Men's Grooming": r"men'?s (?:salon|grooming|haircut)|barber|beard|salon for men|grooming for men",
    "Home Cleaning": r"deep clean|home clean|house clean|bathroom clean|kitchen clean|sofa clean|carpet clean|cleaning service|full home clean|cleaning professional|cleaner|cleaning",
    "Plumbing": r"plumb|water leak|leakage|pipe leak|\bflush\b|wash ?basin|faucet|\btaps\b|bathroom fitting",
    "Electrician": r"electrician|wiring|switch ?board|\bfan\b.*install|mcb|inverter|electrical",
    "Carpentry": r"carpent|furniture repair|wardrobe|door lock|drill",
    "Painting": r"\bpaint(?:ing|er|ers)?\b|wall paint|home paint",
    "Pest Control": r"pest|cockroach|termite|bed ?bug|mosquito|rodent",
    "Appliance Repair": r"washing machine|refrigerator|\bfridge\b|microwave|geyser|water heater|chimney|\btv\b|television|dishwasher|appliance",
    "Water Purifier / RO": r"water purifier|\bro\b|\bro (?:service|filter|membrane)|purifier|native (?:ro|m1|purifier)|aquaguard|kent\b",
    "Insta Help / House Help": r"insta ?help|house ?help|maid|domestic help|cook\b|housekeeping|house help",
    "Mobile / Laptop Repair": r"laptop|mobile repair|phone repair|battery replacement|screen replacement",
    "Native Smart Lock / Products": r"smart lock|native (?:lock|m1|ro)|native smart",
}
CATEGORY_RE = {k: re.compile(v, re.I) for k, v in CATEGORY_PATTERNS.items()}

CITY_ALIASES = {
    "Delhi NCR": r"delhi[\s-]?ncr|\bncr\b",
    "Delhi": r"\bnew delhi\b|\bdelhi\b",
    "Gurugram": r"\bgurugram\b|\bgurgaon\b",
    "Noida": r"\bnoida\b|greater noida",
    "Ghaziabad": r"\bghaziabad\b",
    "Faridabad": r"\bfaridabad\b",
    "Mumbai": r"\bmumbai\b|\bbombay\b|navi mumbai|\bthane\b|\bandheri\b|\bbandra\b|\bpowai\b",
    "Bengaluru": r"\bbengaluru\b|\bbangalore\b|\bbanglore\b|\bblr\b|whitefield|koramangala|hsr layout|indiranagar",
    "Hyderabad": r"\bhyderabad\b|\bsecunderabad\b|\bhyd\b",
    "Chennai": r"\bchennai\b|\bmadras\b",
    "Pune": r"\bpune\b|\bpimpri\b|\bchinchwad\b",
    "Kolkata": r"\bkolkata\b|\bcalcutta\b",
    "Ahmedabad": r"\bahmedabad\b",
    "Jaipur": r"\bjaipur\b",
    "Lucknow": r"\blucknow\b",
    "Chandigarh": r"\bchandigarh\b|\bmohali\b|\bpanchkula\b",
    "Indore": r"\bindore\b",
    "Bhopal": r"\bbhopal\b",
    "Surat": r"\bsurat\b",
    "Nagpur": r"\bnagpur\b",
    "Kochi": r"\bkochi\b|\bcochin\b|\bernakulam\b",
    "Coimbatore": r"\bcoimbatore\b",
    "Visakhapatnam": r"\bvisakhapatnam\b|\bvizag\b",
    "Patna": r"\bpatna\b",
    "Dehradun": r"\bdehradun\b",
    "Vadodara": r"\bvadodara\b|\bbaroda\b",
    "Dubai": r"\bdubai\b|\bsharjah\b|\babu dhabi\b|\buae\b",
    "Singapore": r"\bsingapore\b",
    "Sydney / Australia": r"\bsydney\b|\bmelbourne\b|\baustralia\b",
}
CITY_RE = {k: re.compile(v, re.I) for k, v in CITY_ALIASES.items()}


def tag_categories(text):
    """Return (primary, all) based on number of distinct keyword hits; blank if none."""
    hits = {}
    for cat, rx in CATEGORY_RE.items():
        n = len(rx.findall(text))
        if n: hits[cat] = n
    if "Water Purifier / RO" in hits and "Native Smart Lock / Products" in hits: pass
    if not hits: return "", ""
    ordered = sorted(hits, key=lambda c: -hits[c])
    return ordered[0], "; ".join(ordered[:4])


def tag_cities(text):
    found = [c for c, rx in CITY_RE.items() if rx.search(text)]
    if "Delhi NCR" in found and len(found) > 1: found.remove("Delhi NCR")  # keep the more specific mention
    return "; ".join(found)


def norm_key(t):
    return re.sub(r"[^\w]+", " ", t.casefold(), flags=re.UNICODE).strip()


def parse_date(s):
    if not s: return None
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%b %d, %Y", "%B %d, %Y", "%d %B %Y"):
        try: return dt.datetime.strptime(s[:len(s)] if fmt != "%Y-%m-%d" else s[:10], fmt).date().isoformat()
        except ValueError: continue
    return None


ILLEGAL_XLSX = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def load():
    rows = []
    for r in json.load(open(f"{RAW}/play.json", encoding="utf-8")):
        rows.append(dict(source="Google Play Store", platform_review_id=r["review_id"], review_title="", review_text=r["text"],
                         rating=float(r["rating"]), review_date=r["date"], reviewer_name=r["reviewer"], reviewer_location="",
                         source_url=r["url"], url_type="Direct review link (Play deep link by reviewId)",
                         app_version=r.get("app_version") or "", thumbs_up=r.get("thumbs_up"), company_reply=r.get("developer_reply") or "",
                         collection_note="Play Store, India/English; stratified: newest-200 + most-relevant-60 per star rating"))
    for r in json.load(open(f"{RAW}/play_positive_topup.json", encoding="utf-8")):
        rows.append(dict(source="Google Play Store", platform_review_id=r["review_id"], review_title="", review_text=r["text"],
                         rating=float(r["rating"]), review_date=r["date"], reviewer_name=r["reviewer"], reviewer_location="",
                         source_url=r["url"], url_type="Direct review link (Play deep link by reviewId)",
                         app_version=r.get("app_version") or "", thumbs_up=r.get("thumbs_up"), company_reply=r.get("developer_reply") or "",
                         collection_note="Play Store top-up: random sample of detailed (8+ words) 4-5 star reviews, added to balance positive vs negative content"))
    for r in json.load(open(f"{RAW}/apple.json", encoding="utf-8")):
        rows.append(dict(source="Apple App Store", platform_review_id=r["review_id"], review_title=r["title"], review_text=r["body"],
                         rating=float(r["rating"]), review_date=r["date"], reviewer_name=r["reviewer"], reviewer_location="",
                         source_url=APPLE_APP_PAGE, url_type="App review page only (Apple RSS exposes no per-review permalink)",
                         app_version=r.get("app_version") or "", thumbs_up=None, company_reply="",
                         collection_note="Apple iTunes customer-reviews RSS (India storefront); most recent 500 (feed hard limit); reviewer profile: " + (r["url"] or "")))
    for r in json.load(open(f"{RAW}/consumercomplaints.json", encoding="utf-8")):
        rows.append(dict(source="ConsumerComplaints.in", platform_review_id=r["review_id"], review_title=r["title"] or "", review_text=r["text"],
                         rating=None, review_date=parse_date(r["date_raw"]), reviewer_name=r["reviewer"] or "", reviewer_location=r["location_raw"] or "",
                         source_url=r["url"], url_type="Direct complaint link",
                         app_version="", thumbs_up=None, company_reply="",
                         collection_note="Complaint pages sampled evenly across archive; marked resolved on site: " + str(r.get("resolved"))))
    for r in json.load(open(f"{RAW}/pissedconsumer.json", encoding="utf-8")):
        rows.append(dict(source="PissedConsumer", platform_review_id=r["review_id"], review_title=r["title"] or "", review_text=r["text"],
                         rating=r["rating"], review_date=parse_date(r["date_raw"]), reviewer_name=r["reviewer"] or "", reviewer_location=r["location_raw"] or "",
                         source_url=r["url"], url_type="Listing page + #review-ID anchor",
                         app_version="", thumbs_up=None, company_reply="",
                         collection_note="Review pages sampled evenly across archive; star rating only where reviewer gave one"))
    import os
    if os.path.exists(f"{RAW}/reddit.json"):
        for r in json.load(open(f"{RAW}/reddit.json", encoding="utf-8")):
            rows.append(dict(source="Reddit", platform_review_id=r["review_id"], review_title=r["title"] or "", review_text=r["text"],
                             rating=None, review_date=r["date"], reviewer_name=r["reviewer"], reviewer_location="",
                             source_url=r["url"], url_type=f"Direct Reddit {r['kind']} link", community=f"r/{r['subreddit']}",
                             content_type=r["kind"].capitalize(), app_version="", thumbs_up=r.get("score"), company_reply="",
                             collection_note="Reddit post/comment explicitly naming Urban Company / UrbanClap; via Arctic Shift public archive"))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- relevance rules
# Manual decisions after reading flagged items (keyed on stable platform IDs).
MANUAL_EXCLUDE = {
    ("ConsumerComplaints.in", "3441711"): ("Professional-side", "Beautician (partner) complaining her partner ID was blocked - not a customer experience"),
    ("ConsumerComplaints.in", "2705875"): ("Professional-side", "Complaint about partner category-manager treatment, written about a cousin who is a partner"),
    ("Google Play Store", "03392aed-2804-4dd3-963e-a25bbd3fe219"): ("Professional-side", "8-year partner complaining about permanent account block"),
    ("Apple App Store", "14712190413"): ("Professional-side", "New technician requesting refund of registration/joining fee"),
    ("PissedConsumer", "7433790"): ("Professional-side", "Person trying to join as a partner; partner app not working"),
    ("PissedConsumer", "7028083"): ("Professional-side", "Partner-applicant asking for profile approval"),
    ("PissedConsumer", "5623175"): ("Professional-side", "Former partner asking to rejoin"),
    ("PissedConsumer", "5218815"): ("Professional-side", "Trainee/partner complaint about training and ID block (Hindi, vowel marks lost in source)"),
    ("PissedConsumer", "7301287"): ("Spam / scam listing", "Repeated promotional 'customer care number' text with obfuscated phone number"),
    ("Google Play Store", "e91eac40-2264-4a3e-851b-c934b25b642c"): ("Unreadable / no content", "Emoji and stray characters only"),
}
INVESTOR = re.compile(r"\bipo\b|share price|stock|\bshares?\b|valuation|market cap|\bmutual fund|\bnifty\b|\bsensex\b|listing gain|\bgmp\b|subscription status|\bdrhp\b|\bsebi\b|\bnse\b|\bbse\b|earnings call|quarterly results|\bq[1-4] ?fy|\bebitda\b|\bpe ratio\b|\bfunding round|\bunicorn\b|\bvc\b|\binvest(?:or|ment|ing)\b", re.I)
GIG_PARTNER = re.compile(r"gig workers?|\bpartners? (?:earn|income|payout|commission)|commission cut|\bworker rights|labou?r (?:laws?|code)|\bunion\b|\bstrike\b|\bprotest\b|take[- ]home|per month (?:for|as) (?:a )?(?:partner|professional)|(?:i|we) (?:work|worked|am working) (?:as|with|for) (?:a )?(?:uc|urban ?company)|\bi(?:'m| am) (?:a |an )?(?:uc |urban ?company )?(?:partner|professional|beautician|technician|therapist)", re.I)


def relevance(row):
    key = (row.source, str(row.platform_review_id))
    if key in MANUAL_EXCLUDE: return MANUAL_EXCLUDE[key]
    if row.source == "Reddit":
        t = row.review_title + " " + row.review_text
        if INVESTOR.search(t) and not re.search(r"\b(?:booked|booking|technician|professional|beautician|plumber|service|app)\b", t, re.I):
            return ("Investor / business news (not customer experience)", "Reddit text about IPO/stock/financials without customer-experience content")
    return ("Relevant", "")


def main():
    df = load()
    qc = []
    qc.append(("Raw rows collected", len(df)))

    # ---- missing text
    df["review_text"] = df["review_text"].fillna("").astype(str)
    df["review_title"] = df["review_title"].fillna("").astype(str)
    empty = df[(df.review_text.str.strip() == "") & (df.review_title.str.strip() == "")]
    qc.append(("Rows with no review text and no title (removed)", len(empty)))
    df = df.drop(empty.index)

    # ---- duplicates
    df["_norm"] = (df.review_title + " " + df.review_text).map(norm_key)
    removed = []
    # 1. same platform review id within a source
    d1 = df.duplicated(["source", "platform_review_id"], keep="first")
    removed.append(("Same platform review ID within a source", df[d1].assign(dup_reason="same platform review id")))
    df = df[~d1]
    # 2. same source + same reviewer + same date + same text
    d2 = df.duplicated(["source", "reviewer_name", "review_date", "_norm"], keep="first")
    removed.append(("Same reviewer + date + text within a source", df[d2].assign(dup_reason="same reviewer+date+text")))
    df = df[~d2]
    # 3. identical long text (>=40 chars normalised) posted by different accounts / across sources -> copy-paste duplicates
    long = df["_norm"].str.len() >= 40
    d3 = long & df.duplicated("_norm", keep="first")
    removed.append(("Identical text (>=40 chars) across different accounts/sources", df[d3].assign(dup_reason="identical long text, different account/source")))
    df = df[~d3]
    for label, frame in removed: qc.append((f"Duplicates removed: {label}", len(frame)))
    removed_df = pd.concat([f for _, f in removed]).drop(columns=["_norm"], errors="ignore")
    # short identical texts kept but flagged (e.g. "Good service" from different people are different reviews)
    short_dup = (~long) & df.duplicated("_norm", keep=False)
    df["identical_short_text_flag"] = short_dup.map({True: "Y", False: ""})
    qc.append(("Short identical texts kept but flagged (different reviewers)", int(short_dup.sum())))

    # ---- tagging (on title + text, i.e. explicit mentions)
    blob = (df.review_title + " " + df.review_text)
    tags = blob.map(tag_categories)
    df["service_category"] = tags.map(lambda x: x[0]); df["service_categories_all"] = tags.map(lambda x: x[1])
    df["city_mentioned"] = blob.map(tag_cities)

    # ---- missing metadata
    df["rating_scale"] = df.rating.map(lambda x: "1-5 stars" if pd.notna(x) else "")
    qc.append(("Rows missing review date", int(df.review_date.isna().sum())))
    for s, g in df.groupby("source"):
        qc.append((f"[{s}] rows missing rating (expected for sites without star ratings)", int(g.rating.isna().sum())))
        qc.append((f"[{s}] rows missing reviewer name", int((g.reviewer_name.fillna("") == "").sum())))
    qc.append(("Rows missing source URL", int((df.source_url.fillna("") == "").sum())))

    # ---- descriptors for later analysis planning (NOT sentiment analysis: rating-based proxy only)
    for c in ("community", "content_type"):
        if c not in df: df[c] = ""
        df[c] = df[c].fillna("")
    default_type = {"Google Play Store": "App review", "Apple App Store": "App review", "ConsumerComplaints.in": "Complaint", "PissedConsumer": "Complaint / review"}
    df["content_type"] = [ct or default_type.get(s, "") for ct, s in zip(df.content_type, df.source)]
    nwords = (df.review_title + " " + df.review_text).map(lambda t: len(re.findall(r"\w+", t)))
    df["word_count"] = nwords
    df["info_level"] = pd.cut(nwords, [-1, 4, 24, 10**6], labels=["Low (<5 words)", "Standard (5-24 words)", "Rich (25+ words)"]).astype(str)
    def pol(r):
        if pd.isna(r): return "Unrated"
        return "Positive (4-5 stars)" if r >= 3.5 else ("Negative (1-2 stars)" if r <= 2.5 else "Mixed (3 stars)")
    df["rating_polarity"] = df.rating.map(pol)

    # ---- relevance audit
    rel = df.apply(relevance, axis=1)
    df["relevance_status"] = rel.map(lambda x: x[0]); df["relevance_note"] = rel.map(lambda x: x[1])
    excluded = df[df.relevance_status != "Relevant"].copy()
    for k, v in excluded.relevance_status.value_counts().items(): qc.append((f"Relevance audit - excluded: {k}", int(v)))
    df = df[df.relevance_status == "Relevant"].copy()

    # ---- finish
    df["text_length_chars"] = df.review_text.str.len()
    df["collected_on"] = TODAY
    df = df.sort_values(["source", "review_date"], ascending=[True, False]).reset_index(drop=True)
    prefix = {"Google Play Store": "GP", "Apple App Store": "AS", "ConsumerComplaints.in": "CC", "PissedConsumer": "PC", "Reddit": "RD"}
    df["review_uid"] = [f"{prefix[s]}-{i:04d}" for i, s in zip(df.groupby("source").cumcount() + 1, df.source)]
    excluded = excluded.sort_values(["source", "review_date"]).reset_index(drop=True)
    excluded["review_uid"] = [f"X-{prefix[s]}-{i:03d}" for i, s in zip(excluded.groupby("source").cumcount() + 1, excluded.source)]
    cols = ["review_uid", "source", "content_type", "community", "review_title", "review_text", "rating", "rating_scale", "rating_polarity",
            "info_level", "word_count", "review_date", "reviewer_name", "service_category", "service_categories_all", "city_mentioned",
            "reviewer_location", "source_url", "url_type", "platform_review_id", "app_version", "thumbs_up", "company_reply",
            "text_length_chars", "identical_short_text_flag", "collection_note", "collected_on"]
    excluded = excluded[["review_uid", "relevance_status", "relevance_note"] + [c for c in cols if c != "review_uid"]]
    df = df[cols].rename(columns={"thumbs_up": "engagement"})
    excluded = excluded.rename(columns={"thumbs_up": "engagement"})
    qc.append(("FINAL relevant unique reviews in master dataset", len(df)))
    df.to_pickle("raw/master.pkl"); excluded.to_pickle("raw/excluded.pkl")
    pd.DataFrame(qc, columns=["check", "count"]).to_pickle("raw/qc.pkl")
    removed_df.to_pickle("raw/removed.pkl")
    print(pd.DataFrame(qc, columns=["check", "count"]).to_string())
    print(df.source.value_counts())
    print(pd.crosstab(df.rating_polarity, df.info_level, margins=True))


if __name__ == "__main__":
    main()
