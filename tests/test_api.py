import json
"""API contract tests against the precomputed analysis (read-only endpoints)."""
import pytest

P = "/api/v1"
N = json.loads((__import__("pathlib").Path(__file__).resolve().parents[1] / "analysis" / "overview.json").read_text(encoding="utf-8"))["dataset"]["reviews_analysed"]


def ok(client, url):
    r = client.get(P + url)
    assert r.status_code == 200, (url, r.text[:300])
    j = r.json()
    assert set(j) == {"data", "meta"}
    return j


def err(client, url, status, code):
    r = client.get(P + url)
    assert r.status_code == status, (url, r.text[:300])
    j = r.json()
    assert set(j) == {"error"} and set(j["error"]) == {"code", "message", "details"}
    assert j["error"]["code"] == code
    return j["error"]


def test_health_and_meta(client):
    assert client.get("/health").json()["status"] == "ok"
    j = ok(client, "/meta")
    assert j["data"]["analysis_source"] == "precomputed" and j["data"]["uploads_affect_analysis"] is False
    assert j["meta"]["source"] == "precomputed" and j["meta"]["dataset_reviews"] == N


def test_overview(client):
    d = ok(client, "/overview")["data"]
    assert d["dataset"]["reviews_analysed"] == N and "insta_help_reviews_removed" not in d["dataset"]
    assert len(d["headline_metrics"]["themes"]) <= 5


def test_themes_list_and_detail(client):
    j = ok(client, "/themes")
    assert 1 <= len(j["data"]) <= 5 and "review_ids" not in j["data"][0] and "theme_overlap_matrix" in j["meta"]
    d = ok(client, "/themes/t3")["data"]
    assert d["theme_id"] == "T3" and d["review_ids"] and d["evidence_quotes"] and all(e["source_url"] for e in d["evidence_quotes"])
    assert "evidence_quotes" not in ok(client, "/themes/T3?expand_evidence=false")["data"]
    err(client, "/themes/T9", 404, "theme_not_found")


def test_findings_questions(client):
    assert [f["finding_id"] for f in ok(client, "/findings")["data"]] == ["F1", "F2", "F3"]
    assert ok(client, "/findings/F2")["data"]["evidence_quotes"]
    assert len(ok(client, "/questions")["data"]) == 8
    assert ok(client, "/questions/Q6")["data"]["comparison"]
    err(client, "/questions/Q9", 404, "question_not_found")


def test_behaviour(client):
    d = ok(client, "/behaviour")["data"]
    assert sum(x["n"] for x in d["distribution"]) == N and d["summary"]["classified_pct"] >= 70
    c = ok(client, "/behaviour/classes/non-return")["data"]
    assert len(c["stated_records"]) == c["by_basis"]["Stated"] and "review_ids" not in c and c["evidence_quotes"]
    err(client, "/behaviour/classes/nope", 404, "behaviour_class_not_found")


def test_alternatives(client):
    j = ok(client, "/alternatives")
    assert len(j["data"]) == 4 and j["meta"]["summary"]["reported_use"] > 0
    assert ok(client, "/alternatives/A2")["data"]["evidence_quotes"]


def test_segments(client):
    assert len(ok(client, "/segments")["data"]) == 6
    j = ok(client, "/segments/service-category?min_n=50")
    assert all(s["n"] >= 50 for s in j["data"]) and j["meta"]["dimension"] == "service_category"
    assert ok(client, "/segments/city?page_size=2")["meta"]["page_size"] == 2
    assert ok(client, "/segments/household_type")["data"][0]["n_vetted_examples"] > 0
    err(client, "/segments/colour", 422, "invalid_filter")
    err(client, "/segments/city/NOPE", 404, "segment_not_found")


def test_unmet_needs_and_opportunities(client):
    n = ok(client, "/unmet-needs?min_reviews=50")["data"]
    assert n and all(x["n_reviews"] >= 50 for x in n)
    assert ok(client, "/unmet-needs/N02")["data"]["evidence_quotes"]
    hi = ok(client, "/opportunities?priority=high")["data"]
    assert len(hi) == 3 and all(o["priority"] == "High" for o in hi)
    ranks = [o["priority_rank"] for o in ok(client, "/opportunities")["data"]]
    assert ranks == sorted(ranks)
    err(client, "/opportunities?priority=urgent", 422, "invalid_filter")
    err(client, "/opportunities/O99", 404, "opportunity_not_found")


def test_reviews_pagination_filters_sorting(client):
    j = ok(client, "/reviews?page_size=5&page=2")
    assert j["meta"]["total"] == N and j["meta"]["page"] == 2 and len(j["data"]) == 5 and j["meta"]["total_pages"] == -(-N // 5)
    r = ok(client, "/reviews?source=Reddit,PissedConsumer&sentiment=negative&theme=T3&page_size=50")
    assert r["data"] and all(x["source"] in ("Reddit", "PissedConsumer") and x["sentiment_label"] == "Negative" and "T3" in x["themes"] for x in r["data"])
    assert all(x["rating"] is None or float(x["rating"]) <= 2 for x in ok(client, "/reviews?rating_max=2&page_size=20")["data"])
    s = ok(client, "/reviews?q=refund&return_class=Non-Return&return_basis=Stated&page_size=50&include_text=true")
    assert all("refund" in (x["review_text"] + (x["review_title"] or "")).lower() for x in s["data"])
    desc = ok(client, "/reviews?sort=rating&order=desc&page_size=3")["data"]
    assert [d["rating"] for d in desc] == ["5", "5", "5"] or all(d["rating"] is not None for d in desc)
    asc = ok(client, "/reviews?sort=rating&order=asc&page_size=3")["data"]
    assert all(float(d["rating"]) <= 1.0 for d in asc)
    assert ok(client, "/reviews?unmet_need=N02&page_size=3")["meta"]["total"] == ok(client, "/unmet-needs/N02")["data"]["n_reviews"]


def test_reviews_errors(client):
    err(client, "/reviews?sentiment=awful", 422, "invalid_filter")
    err(client, "/reviews?page=0", 422, "invalid_request")
    err(client, "/reviews?page_size=1000", 422, "invalid_request")
    err(client, "/reviews?page=99999", 404, "page_out_of_range")
    err(client, "/reviews?sort=colour", 422, "invalid_filter")
    err(client, "/reviews?date_from=yesterday", 422, "invalid_filter")
    err(client, "/reviews/NOPE-1", 404, "review_not_found")
    assert client.get("/api/v1/nowhere").json()["error"]["code"] == "not_found"


def test_review_detail_and_evidence_traceability(client):
    ev = ok(client, "/evidence?theme=T3&page_size=3")
    assert ev["meta"]["total"] > 20
    e = ev["data"][0]
    assert {"evidence_id", "review_id", "quote", "source", "source_url", "review_date"} <= set(e) and "review_text" not in e
    full = ok(client, f"/evidence/{e['evidence_id']}")["data"]
    assert e["quote"].split(" …")[0].replace("… ", "") in " ".join(full["review_text"].split())
    r = ok(client, f"/reviews/{e['review_id']}")["data"]
    assert r["source_url"].startswith("http") and any(x["evidence_id"] == e["evidence_id"] for x in r["evidence"])
    assert ok(client, "/evidence?supports=opportunity:O1")["meta"]["total"] > 0
    err(client, "/evidence/EV999999", 404, "evidence_not_found")


def test_limitations(client):
    d = ok(client, "/limitations")["data"]
    assert {"negative_representation", "google_play_dominance", "missing_city_and_category", "return_evidence", "reddit_text", "source_coverage"} <= set(d["dataset_characteristics"])


def test_trust_mood_ask_and_opportunity_filter(client):
    t = ok(client, "/trust")["data"]
    assert [f["n"] for f in t["funnel"]][-1] == N and len(t["funnel"]) == 3 and "brief_coverage" not in t and len(t["pipeline"]) == 8
    assert t["validation"]["quotes"]["verified"] == t["validation"]["quotes"]["total"]
    m = ok(client, "/mood?by=source")["data"]
    assert {x["key"] for x in m} == {"Google Play Store", "Reddit", "PissedConsumer", "ConsumerComplaints.in"} and sum(x["n"] for x in m) == N
    assert all(x["positive"] + x["neutral"] + x["negative"] + x["mixed"] + x["uncertain"] == x["n"] for x in m)
    th = ok(client, "/mood?by=theme")["data"]
    assert {x["key"] for x in th} == {"T1", "T2", "T3", "T4", "T5"} and th[0]["label"]
    assert ok(client, "/mood?by=issue&min_n=20")["data"][0]["label"]
    err(client, "/mood?by=colour", 422, "invalid_filter")
    a = ok(client, "/ask?q=refund delayed")["data"]
    assert a["mode"] == "keyword_search" and 1 <= len(a["comments"]) <= 3 and all(c["source_url"].startswith("http") for c in a["comments"])
    assert ok(client, "/ask?q=why did customers not book again after a booking went wrong")["data"]["matched_question"]["question_id"]
    err(client, "/ask?q=the and of", 422, "no_searchable_words")
    r = ok(client, "/reviews?opportunity=O2&page_size=5")
    assert r["meta"]["total"] == ok(client, "/opportunities/O2")["data"]["evidence"]["reviews"]
    err(client, "/reviews?opportunity=O99", 422, "invalid_filter")
    rid = r["data"][0]["record_id"]
    assert any(o["opportunity_id"] == "O2" for o in ok(client, f"/reviews/{rid}")["data"]["opportunities"])


def test_website_is_served_when_built(client):
    from backend.api import settings
    if not (settings.FRONTEND_DIST / "index.html").exists():
        import pytest
        pytest.skip("frontend not built")
    for path in ("/", "/overview/analysis", "/ask", "/workflow"):
        r = client.get(path)
        assert r.status_code == 200 and "text/html" in r.headers["content-type"] and '<div id="root">' in r.text
    assert client.get("/api/v1/nowhere").json()["error"]["code"] == "not_found"
    assert client.get("/docs").status_code == 200
    asset = next((settings.FRONTEND_DIST / "assets").glob("*.js"))
    assert client.get(f"/assets/{asset.name}").status_code == 200


def test_return_filters_and_new_class_names(client):
    j = ok(client, "/reviews?return_class=Return&return_basis=Stated,Signalled&page_size=5")
    assert j["meta"]["total"] > 500 and all(r["return_class"] == "Return" and r["return_basis"] in ("Stated", "Signalled") for r in j["data"])
    assert ok(client, "/reviews?return_confidence=High&page_size=3")["meta"]["total"] == ok(client, "/reviews?return_basis=Stated&page_size=3")["meta"]["total"]
    err(client, "/reviews?return_class=Explicit Return", 422, "invalid_filter")
    err(client, "/behaviour/classes/explicit-return", 404, "behaviour_class_not_found")
    m = ok(client, "/mood?by=return_class")["data"]
    assert {x["key"] for x in m} == {"Return", "Non-Return", "Insufficient Evidence"}


def test_downloads_serve_only_the_listed_project_files(client):
    for key, ctype in (("dataset", "text/csv"), ("notebook", "application/x-ipynb+json"), ("evidence-log.pdf", "application/pdf")):
        r = client.get(f"/downloads/{key}")
        assert r.status_code == 200 and r.headers["content-type"].startswith(ctype), key
    assert "inline" in client.get("/downloads/evidence-log.pdf").headers["content-disposition"]
    assert "attachment" in client.get("/downloads/evidence-log.pdf?download=true").headers["content-disposition"]
    assert client.get("/downloads/dataset").headers["content-disposition"].startswith("attachment")
    assert "CLOUDFLARE" not in client.get("/downloads/..%2F.env").text and client.get("/downloads/secrets").status_code == 404


def test_ready_answers_need_no_ai_call(client):
    from pathlib import Path
    ready = json.loads((Path(__file__).resolve().parents[1] / "analysis" / "ask_ready.json").read_text(encoding="utf-8"))
    q = next(iter(ready["answers"].values()))["query"]
    d = client.get("/api/v1/ask/answer", params={"q": q}).json()["data"]
    assert d["prepared"] is True and d["answer"] and d["citations"]
    b = client.get("/api/v1/questions/Q4/brief").json()["data"]
    assert b["prepared"] is True and b["headline"]
