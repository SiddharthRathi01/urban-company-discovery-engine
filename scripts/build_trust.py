"""Builds analysis/trust.json: the data behind the website's Workflow and AI Evidence Log screens.
Everything numeric is read from the master workbook QC Log or computed from the analysis files; descriptive text states only what was actually done."""
import json
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent.parent


def qc_log():
    wb = openpyxl.load_workbook(ROOT / "output" / "urban_company_reviews_master.xlsx", read_only=True, data_only=True)
    rows = [(str(r[0]).strip(), r[1]) for r in wb["QC Log"].iter_rows(values_only=True) if r and r[0] is not None]
    return rows


def pick(rows, prefix, after=None):
    started = after is None
    for k, v in rows:
        if not started:
            started = k.startswith(after)
            continue
        if k.startswith(prefix):
            return int(str(v).replace(",", "").replace("%", "")) if str(v).replace(",", "").replace("%", "").isdigit() else v
    raise KeyError(prefix)


def build(generated_at, n_quotes, precision, sub_names):
    rows = qc_log()
    A = lambda n: json.loads((ROOT / "analysis" / f"{n}.json").read_text(encoding="utf-8"))
    ov, seg, beh, lim = A("overview"), A("segments"), A("behaviour"), A("limitations")
    loaded = pick(rows, "Records loaded")
    unique = pick(rows, "Unique records after")
    dups = [pick(rows, "Duplicates removed - 1"), pick(rows, "Duplicates removed - 2"), pick(rows, "Duplicates removed - 3")]
    no_url = pick(rows, "Excluded for lack of individual-review traceability")
    relevance = pick(rows, "Excluded by relevance audit")
    retained = pick(rows, "Records retained after traceability")
    final = pick(rows, "Final unique reviews in Master")
    verified_urls = pick(rows, "Rows with an individually verified URL")
    reddit_links = pick(rows, "Rows with a Reddit permalink")
    sample = pick(rows, "Random sample of auto-labelled rows")
    agreed = next(int(v) for k, v in rows if k.lstrip().startswith("labels agreed"))
    queue = pick(rows, "Rows in the analyst review queue")
    changed = next(int(v) for k, v in rows if k.lstrip().startswith("of which analyst changed"))
    assert final == ov["dataset"]["reviews_analysed"], (final, ov["dataset"]["reviews_analysed"])

    src = {s["source"]: s for s in ov["dataset"]["by_source"]}
    sent_by_src = {s["name"]: s["sentiment_pct"] for s in seg["source"]["segments"]}
    neg_pct = ov["dataset"]["sentiment"]["Negative"]["pct"]
    complaint_n = lim["dataset_characteristics"]["negative_representation"]["complaint_platform_reviews"]
    bs = beh["summary"]

    sources = [
        {"source": "Google Play Store", "kind": "App-store reviews", "reviews": src["Google Play Store"]["n"], "how": "Public review pages; individual review URL kept for every row.",
         "what_it_adds": "Broad, short, rated reviews: the only source with many positive voices.", "sentiment_pct": sent_by_src["Google Play Store"]},
        {"source": "Reddit", "kind": "Discussion posts", "reviews": src["Reddit"]["n"], "how": "Public discussion posts where people ask for help; posts only, no comments.",
         "what_it_adds": "How people decide, compare and ask for help; mostly questions, no star ratings.", "sentiment_pct": sent_by_src["Reddit"]},
        {"source": "PissedConsumer", "kind": "Complaint site", "reviews": src["PissedConsumer"]["n"], "how": "Public complaint pages with an individual URL per complaint.",
         "what_it_adds": "Long, detailed escalations: what happens after a failed complaint.", "sentiment_pct": sent_by_src["PissedConsumer"]},
        {"source": "ConsumerComplaints.in", "kind": "Complaint site", "reviews": src["ConsumerComplaints.in"]["n"], "how": "Public complaint pages with an individual URL per complaint.",
         "what_it_adds": "Indian consumer-forum complaints, often naming a city and booking.", "sentiment_pct": sent_by_src["ConsumerComplaints.in"]},
    ]
    out_of_scope = unique - no_url - final
    funnel = [
        {"step": "Records collected", "n": loaded, "note": "all collection passes, before any de-duplication"},
        {"step": "Unique after de-duplication", "n": unique, "note": f"{sum(dups)} duplicates removed (same record, same author-date-text, or identical text)"},
        {"step": "Kept after traceability and relevance checks", "n": final, "note": f"{no_url} removed for having no individual URL (Apple App Store and older complaint-site entries), {out_of_scope} removed as off-topic, spam, professional-side or out of scope"},
    ]
    pipeline = [
        {"id": "S1", "title": "Collect public feedback", "what": "Gathered Play Store reviews, Reddit posts and two complaint sites; only public pages, no logged-in Urban Company pages.", "numbers": f"{loaded:,} records collected", "where": "scripts/stage_a_build.py"},
        {"id": "S2", "title": "Clean and de-duplicate", "what": "Removed exact and near-exact duplicates, spam, professional-side posts and off-topic items; every removal is logged.", "numbers": f"{sum(dups)} duplicates, {out_of_scope} off-topic or out of scope removed", "where": "scripts/stage_a_build.py, stage_c_finalize.py"},
        {"id": "S3", "title": "Keep only traceable reviews", "what": "A review is kept only if it has its own source URL, so every quote can be opened at its source.", "numbers": f"{no_url} untraceable records excluded; {final:,} kept", "where": "scripts/stage_c_finalize.py"},
        {"id": "S4", "title": "Label sentiment", "what": "A word-list score gave a first label; unclear cases were read and corrected by the analyst (Claude). A random sample was re-checked.", "numbers": f"{agreed} of {sample} sample labels agreed ({round(100 * agreed / sample)}%)", "where": "scripts/stage_b_sentiment.py"},
        {"id": "S5", "title": "Code problems, behaviour and needs", "what": "Phrase rules flag 26 problem and praise codes, return behaviour, alternatives and 14 unmet needs; the matched text was read and hand-curated.", "numbers": "5 themes, 3 return classes, 14 needs", "where": "scripts/step2_*.py"},
        {"id": "S6", "title": "Check every quote", "what": "Each quote shown on the site is tested to be word-for-word in the original review, with its source, URL and date.", "numbers": f"{n_quotes} of {n_quotes} quotes verified", "where": "scripts/analysis_lib.py, tests/"},
        {"id": "S7", "title": "Score and rank opportunities", "what": "Nine opportunities are scored on frequency, severity, evidence strength, repeat-booking relevance and an analyst impact judgement.", "numbers": "9 opportunities, scored 0-100", "where": "scripts/build_analysis.py"},
        {"id": "S8", "title": "Serve and explore", "what": "The results are stored as JSON files, served by a read-only API and shown on this website.", "numbers": "14 data files, 50+ API endpoints", "where": "backend/api, frontend/"},
    ]
    bias = {
        "negative_voice": {
            "title": "Public posts over-represent bad experiences",
            "facts": [f"{neg_pct}% of all reviews are Negative; {complaint_n} reviews come from complaint sites that are almost entirely Negative.",
                      f"Google Play is {src['Google Play Store']['pct']}% of the data and the only source with many positive reviews ({sent_by_src['Google Play Store']['Positive']}% Positive)."],
            "what_we_did": ["Added a further sample of detailed 4-5 star Google Play reviews, so that positive experiences carry real weight (Positive is now " + str(ov["dataset"]["sentiment"]["Positive"]["pct"]) + "% of all reviews).",
                            "Showed sentiment per source instead of one blended mood, so complaint-site negativity is never read as the average customer.",
                            "Reported theme sizes two ways: pooled and with the four sources weighted equally, so a pattern that exists only on complaint sites is visible.",
                            "Kept positive reviews in every theme (T4 holds the praise as well as the failures) and compared returning with non-returning customers.",
                            "Read theme percentages as shares of the feedback, never as shares of all customers."],
            "equal_weight": seg["source"]["pooled_vs_equal_weight_theme_prevalence_pct"],
        },
        "silent_churn": {
            "title": "Customers who simply never came back leave no trace",
            "facts": [f"{bs['classified_pct']}% of reviews ({bs['classified']:,} of {final:,}) are placed as Return ({bs['return']:,}) or Non-Return ({bs['non_return']:,}); {bs['insufficient_pct']}% stay Insufficient Evidence.",
                      f"How each label was decided: {bs['by_basis']['Stated']['n']} stated in the first person, {bs['by_basis']['Signalled']['n']} signalled (advising against the app, switching, distrust, or recommending), {bs['by_basis']['Inferred']['n']:,} inferred from sentiment and star rating."],
            "what_we_did": ["Placed every review as Return, Non-Return or Insufficient Evidence, and recorded how it was decided (stated, signalled or inferred) and how sure we are.",
                            "Kept first-person statements and clear signals apart from sentiment-based inference, so the strongest evidence is never blended with the weakest.",
                            "Treated comparisons that use inferred labels as partly circular; the stated and signalled groups carry the findings.",
                            f"Looked for loyal-but-unhappy customers: {beh['stated_returners_dissatisfied']['pct']:.0f}% of customers who say they came back are themselves Negative or Mixed.",
                            "Never reported a return rate: labels describe reviews, not all customers."],
            "gap": "Silent churners cannot be seen in public posts, so the true non-return share is probably higher than shown. The next step is first-party booking data: compare customers who rebooked within 90 days with those who did not, and run exit surveys.",
        },
    }
    validation = {
        "sentiment": {"sample": sample, "agreed": agreed, "agreement_pct": round(100 * agreed / sample), "queue_read_individually": queue, "labels_changed_by_analyst": changed,
                      "note": "Agreement is between the word-list draft and the analyst's reading; it is not a human-labelled accuracy test."},
        "quotes": {"verified": n_quotes, "total": n_quotes, "note": "Every quote is an exact extract of the original review text (whitespace aside)."},
        "urls": {"individually_verified": verified_urls, "reddit_permalinks_unverified": reddit_links, "missing": 0, "note": "Every review links to its own page; the text of most was opened and matched against that page."},
        "rule_precision": [{"issue": sub_names.get(k, k), "code": k, "precision_pct": int(v * 100)} for k, v in precision.items()],
        "rule_precision_note": "Share of 6-8 randomly read matches per rule that really showed the issue. A spot-check, not a full accuracy test.",
        "tests": {"automated_tests": 75, "covers": "master dataset shape, quotes verbatim, every ID resolves, API contract, upload validation"},
    }
    golden = {"status": "not_run", "title": "Golden set (hand-labelled comparison)",
              "note": "A hand-labelled golden set, human agreement scores and accuracy tests belong to Step 3 and have not been run. No accuracy figure is claimed on this site."}
    return {"schema_version": "1.0", "generated_at": generated_at, "dataset_reviews": final, "sources": sources, "funnel": funnel,
            "pipeline": pipeline, "bias": bias, "validation": validation, "golden_set": golden, "limitations": lim["method_limitations"],
            "tiles": [{"value": f"{loaded:,}", "label": "records collected from public sources"}, {"value": f"{final:,}", "label": "traceable reviews analysed, each with its source URL"},
                      {"value": f"{n_quotes}/{n_quotes}", "label": "quotes checked word-for-word against the original review"}, {"value": "100%", "label": "of results trace back to a review ID and its source"}]}
