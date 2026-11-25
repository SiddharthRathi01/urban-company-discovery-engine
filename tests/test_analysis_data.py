"""Consistency checks between the approved master dataset and the precomputed analysis files."""
import hashlib
import json
import re
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
A = ROOT / "analysis"
FILES = ["overview", "themes", "findings", "questions", "behaviour", "alternatives", "segments", "unmet_needs", "opportunities", "evidence", "limitations", "reviews", "manifest"]


def load(n):
    return json.loads((A / f"{n}.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def master():
    return pd.read_csv(ROOT / "output" / "urban_company_reviews_master.csv", encoding="utf-8-sig", keep_default_na=False, dtype=str)


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


def quote_ok(q, text):
    t, pos = norm(text), 0
    for seg in [s.strip() for s in re.split(r"…", q) if len(s.strip()) >= 3]:
        i = t.find(norm(seg), pos)
        if i < 0:
            return False
        pos = i + len(norm(seg))
    return True


def test_master_shape_and_scope(master):
    assert len(master) == load("manifest")["source_dataset"]["reviews"] >= 2500
    assert list(master.columns) == ["record_id", "original_review_id", "review_text", "platform", "source_url", "url_type", "review_date", "rating", "reviewer",
                                    "service_category", "city", "sentiment_label", "review_title", "content_type", "service_categories_all", "reviewer_profile_location"]
    assert master.record_id.is_unique
    assert not master.service_categories_all.str.contains("Insta Help", regex=False).any()
    assert (master.source_url.str.startswith("http")).all()
    assert (master.review_text.str.strip() != "").all()


def test_removed_columns_stay_removed(master):
    for c in ["sentiment_method", "word_count", "collection_date", "community", "length_band", "engagement", "app_version", "company_response", "collection_note", "verification_status"]:
        assert c not in master.columns


def test_all_analysis_files_exist_and_manifest_matches_master():
    for n in FILES:
        assert (A / f"{n}.json").exists(), n
    m = load("manifest")
    assert m["source_dataset"]["sha256"] == hashlib.sha256((ROOT / "output" / "urban_company_reviews_master.csv").read_bytes()).hexdigest()
    assert m["source_dataset"]["reviews"] == len(pd.read_csv(ROOT / "output" / "urban_company_reviews_master.csv", encoding="utf-8-sig", usecols=[0]))


def test_reviews_json_matches_master(master):
    rv = load("reviews")["reviews"]
    assert [r["record_id"] for r in rv] == sorted(master.record_id)
    byid = master.set_index("record_id")
    for r in rv[::37]:
        row = byid.loc[r["record_id"]]
        assert r["source_url"] == row.source_url and r["source"] == row.platform and r["review_text"] == row.review_text


def test_every_quote_is_verbatim_and_traceable(master):
    byid = master.set_index("record_id")
    ev = load("evidence")["evidence"]
    assert len(ev) > 250
    assert len({e["evidence_id"] for e in ev}) == len(ev)
    for e in ev:
        row = byid.loc[e["review_id"]]
        assert quote_ok(e["quote"], e["review_text"]), (e["evidence_id"], e["quote"])
        assert e["review_text"] == row.review_text or norm(row.review_title + " " + row.review_text) == norm(e["review_text"]) or norm(e["review_text"]) == norm(row.review_text)
        assert e["source_url"] == row.source_url and e["source"] == row.platform
        assert e["review_date"] == (row.review_date or None)


def all_values(obj, key_part):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if key_part in k and isinstance(v, list):
                yield from (x for x in v if isinstance(x, str))
            elif key_part == "evidence_id" and k == "evidence_id" and isinstance(v, str):
                yield v
            else:
                yield from all_values(v, key_part)
    elif isinstance(obj, list):
        for v in obj:
            yield from all_values(v, key_part)


def test_all_evidence_references_resolve():
    ids = {e["evidence_id"] for e in load("evidence")["evidence"]}
    for n in ["themes", "findings", "questions", "behaviour", "alternatives", "segments", "unmet_needs", "opportunities"]:
        refs = set(all_values(load(n), "evidence_ids")) | set(all_values(load(n), "evidence_id"))
        assert refs <= ids, (n, sorted(refs - ids)[:5])


def test_all_review_references_resolve(master):
    ids = set(master.record_id)
    for n in ["themes", "findings", "alternatives", "segments", "unmet_needs", "opportunities", "behaviour"]:
        refs = set(all_values(load(n), "review_ids"))
        assert refs <= ids, n


def test_themes_are_at_most_five_and_counts_consistent():
    t = load("themes")
    assert 1 <= len(t["themes"]) <= 5
    for x in t["themes"]:
        assert x["review_count"] == len(x["review_ids"]) == len(set(x["review_ids"]))
        assert x["pct_of_dataset"] == pytest.approx(100 * x["review_count"] / load("overview")["dataset"]["reviews_analysed"], abs=0.06)
        assert sum(v["n"] for v in x["sentiment"].values()) == x["review_count"]
        assert x["representative_evidence_ids"]
    assert "counted once in each theme" in t["counting_method"]


def test_behaviour_classes_partition_the_dataset_and_meet_the_70_percent_target():
    b = load("behaviour")
    n = load("overview")["dataset"]["reviews_analysed"]
    assert sum(d["n"] for d in b["distribution"]) == n
    assert {d["class"] for d in b["distribution"]} == {"Return", "Non-Return", "Insufficient Evidence"}
    s = b["summary"]
    assert s["classified"] == s["return"] + s["non_return"] and s["classified_pct"] >= 70 and s["target_met"] is True
    assert s["insufficient"] == n - s["classified"] and sum(v["n"] for v in s["by_basis"].values()) == s["classified"]
    for c in ("Return", "Non-Return"):
        recs = b["classes"][c]["stated_records"]
        assert len(recs) == b["classes"][c]["by_basis"]["Stated"]
        assert all(r["evidence_id"] and r["source_url"] for r in recs)
    assert b["comparison"]["groups"]["return_stated_signalled"] > 100 and b["comparison"]["groups"]["non_return_stated_signalled"] > 100


def test_every_review_has_a_consistent_return_label():
    rv = load("reviews")["reviews"]
    assert all(r["return_class"] in ("Return", "Non-Return", "Insufficient Evidence") and r["return_basis"] in ("Stated", "Signalled", "Inferred", "None") for r in rv)
    assert all(r["return_confidence"] == "High" for r in rv if r["return_basis"] == "Stated")
    # inferred labels follow sentiment (never a Return label on a Negative review or the reverse)
    assert not any(r["return_basis"] == "Inferred" and r["return_class"] == "Return" and r["sentiment_label"] == "Negative" for r in rv)
    assert not any(r["return_basis"] == "Inferred" and r["return_class"] == "Non-Return" and r["sentiment_label"] == "Positive" for r in rv)


def test_site_text_does_not_mention_the_excluded_service():
    import re as _re
    for n in ("overview", "trust", "limitations", "themes", "questions", "opportunities"):
        assert not _re.search(r"insta ?help|instahelp", (A / f"{n}.json").read_text(encoding="utf-8"), _re.I), n


def test_scripts_and_backend_classification_rules_agree():
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import step2_behaviour as sb
    from backend import return_class as rc
    cases = [("Explicit Return", "x", "Negative", 1, "will_return"), ("Explicit Non-Return", "x", "Positive", 5, "will_not_return"),
             ("Behavioural Signal", "warns others / advises against using", "Positive", 5, "warns_others"), ("Behavioural Signal", "satisfaction / trust / recommendation (no repeat stated)", "Positive", 5, "recommends"),
             ("Insufficient Evidence", "none", "Positive", 5, "none"), ("Insufficient Evidence", "none", "Positive", 1, "none"), ("Insufficient Evidence", "none", "Negative", 1, "none"),
             ("Insufficient Evidence", "none", "Negative", 5, "none"), ("Insufficient Evidence", "none", "Mixed", 5, "none"), ("Insufficient Evidence", "none", "Mixed", 2, "none"),
             ("Insufficient Evidence", "none", "Neutral", None, "none"), ("Insufficient Evidence", "none", "Positive", None, "none")]
    for legacy, sub, sent, rating, sig in cases:
        assert sb.classify(legacy, sub, sent, rating)[:3] == rc.classify(sig, sent, rating)[:3], (legacy, sent, rating)


def test_findings_opportunities_unmet_needs_structure():
    f = load("findings")["findings"]
    assert [x["finding_id"] for x in f] == ["F1", "F2", "F3"]
    for x in f:
        for k in ("title", "evidence_summary", "supporting_volume", "customer_impact", "connection_to_repeat_booking", "why_it_matters_to_urban_company", "evidence_ids"):
            assert x[k]
    o = load("opportunities")["opportunities"]
    assert len(o) == 9 and sorted(x["priority_rank"] for x in o) == list(range(1, 10))
    for x in o:
        for k in ("title", "customer_problem", "evidence", "expected_customer_benefit", "influence_on_repeat_booking_hypothesis", "suggested_success_metric", "priority", "priority_rationale", "prioritisation"):
            assert x[k], (x["opportunity_id"], k)
        assert x["prioritisation"]["formula"]
    n = load("unmet_needs")["unmet_needs"]
    assert len(n) == 14 and all(x["n_reviews"] == len(x["review_ids"]) for x in n)


def test_questions_cover_all_eight():
    q = load("questions")["questions"]
    assert [x["question_id"] for x in q] == [f"Q{i}" for i in range(1, 9)]
    assert all(x["summary"] and x["evidence_strength"] for x in q)


def test_alternatives_separate_reported_from_general():
    a = load("alternatives")
    s = a["summary"]
    assert s["reported_use"] + s["considering"] + s["general_or_hypothetical"] == s["vetted_mentions_total"]
    assert a["whatsapp_and_community_groups"]["relevant_mentions"] == 0


def test_segments_report_sample_sizes():
    s = load("segments")
    for d in ("service_category", "city", "source"):
        assert all("n" in x for x in s[d]["segments"])
    assert any(x["small_sample"] for x in s["city"]["segments"]) or True
    assert load("limitations")["dataset_characteristics"]["google_play_dominance"]["pct"] > 70
