"""Read the master CSV, apply the agreed Step 2 scope (Insta Help excluded from the ANALYSIS only), and verify quotes."""
import hashlib
import re
import pandas as pd
from . import config

INSTA_NAMED = re.compile(r"insta[\s\-_]*(?:help|maid|house|service|services|pack|gold|booking|bookings|helper|helpers|clean|cook)|instant[\s\-]*(?:help|maid|service|booking)|instamaid|\binsta\b", re.I)
# reviews that clearly describe an instant house-help booking without naming it (read individually in the earlier Step 2 scoping work)
INSTA_UNNAMED_IDS = {"GP-0418", "GP-0472", "GP-0527", "GP-0659", "GP-0735", "GP-0886", "GP-1032", "GP-1399", "PC-0003", "GP-0507", "GP-0764"}


def dataset_sha256():
    return hashlib.sha256(config.MASTER_CSV.read_bytes()).hexdigest()


def load_reviews(include_insta_help=False):
    """Returns (analysis_df, full_df). full_df always has all master rows; analysis_df applies the Insta Help scope rule."""
    df = pd.read_csv(config.MASTER_CSV, encoding="utf-8-sig", keep_default_na=False, dtype=str)
    df["text"] = (df.review_title.str.strip() + " " + df.review_text.str.strip()).str.strip()
    df["rating_f"] = pd.to_numeric(df.rating, errors="coerce")
    df["insta_help"] = (df.text.str.contains(INSTA_NAMED) | df.service_categories_all.str.contains("Insta Help / House Help", regex=False)
                        | df.record_id.isin(INSTA_UNNAMED_IDS))
    out = df if include_insta_help else df[~df.insta_help]
    return out.reset_index(drop=True), df


def _n(s):
    return re.sub(r"\s+", " ", s or "").strip()


def verify_quote(quote, text):
    """True if the quote is verbatim in the review text (whitespace-normalised, case-sensitive).
    A quote may contain '…' or '...' to skip text; every segment (>= 6 chars) must appear verbatim and in order."""
    if not quote or not _n(quote):
        return False
    t = _n(text)
    pos = 0
    segs = [s.strip() for s in re.split(r"…|\.\.\.", quote) if len(s.strip()) >= 6]
    if not segs:
        return False
    for s in segs:
        i = t.find(_n(s), pos)
        if i < 0:
            return False
        pos = i + len(_n(s))
    return True
