"""CSV Upload -> LLM analysis -> saved insights, and grounded Ask answers, with a fake Cloudflare transport (no network, no credentials)."""
import csv
import io
import json
import time

import pytest

from backend import config
from backend import llm as L
from backend.api import llm_service, settings
from backend.api.uploads import storage
from tests.fakes import TOKEN, FakeCloudflare

P = "/api/v1/uploads"
REVIEWS = [
    ("T-001", "The AC technician arrived almost three hours late and did not even call to inform me. Very unprofessional.", "https://example.com/r/1", "Play Store"),
    ("T-002", "Lovely experience. The beautician was polite and the facial was exactly as described in the app.", "https://example.com/r/2", "Play Store"),
    ("T-003", "I was charged 700 rupees extra for a part. A local mechanic quoted half of that. Will not book again.", "https://example.com/r/3", "Reddit"),
    ("T-004", "Paid for deep cleaning but the bathroom was only wiped. The support chat closed my ticket without any reply.", "https://example.com/r/4", "Play Store"),
    ("T-005", "Great app. I have used it five times and the professionals were skilled each time.", "https://example.com/r/5", "Reddit"),
    ("T-006", "Booking got cancelled by the company an hour before the slot and the refund took more than a week.", "https://example.com/r/6", "Play Store"),
    ("T-007", "Plumber fixed the leak quickly and cleaned up after himself. Would definitely call him again.", "https://example.com/r/7", "Play Store"),
    ("T-008", "The chatbot keeps repeating the same answers and nobody calls back about my complaint.", "https://example.com/r/8", "Reddit"),
]


def make_csv(rows=REVIEWS, extra="", prefix="T"):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["review_id", "review_text", "platform", "source_url", "rating"])
    for rid, text, url, src in rows:
        w.writerow([rid.replace("T-", prefix + "-"), text, src, url, ""])
    return (buf.getvalue() + extra).encode("utf-8")


@pytest.fixture
def cf(monkeypatch, tmp_path):
    """A real CloudflareLLM wired to the fake transport, with the cloudflare processor active."""
    fake = FakeCloudflare(neurons=2.0)
    monkeypatch.setattr(settings, "UPLOAD_PROCESSOR", "cloudflare")
    monkeypatch.setattr(L.time, "sleep", lambda s: None)
    llm_service.set_llm_factory(lambda: L.CloudflareLLM(cache_dir=tmp_path / "cache", transport=fake, tracker=L.get_tracker(), account="acc", token=TOKEN))
    yield fake
    llm_service.set_llm_factory(None)


def upload(client, data, name="reviews.csv"):
    r = client.post(P, files={"file": (name, data, "text/csv")})
    assert r.status_code == 201, r.text
    return r.json()["data"]["upload_id"]


def wait_done(client, uid, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        j = client.get(f"{P}/{uid}/job").json()["data"]
        if j["status"] in ("completed", "failed", "not_configured"):
            return j
        time.sleep(0.2)
    raise AssertionError("job did not finish: " + json.dumps(j))


def test_full_workflow_upload_to_saved_insights(client, cf, fingerprint):
    before = fingerprint()
    uid = upload(client, make_csv(prefix="W"))
    assert client.get(f"{P}/{uid}/analysis").json()["error"]["code"] == "analysis_not_found"
    job0 = client.post(f"{P}/{uid}/process").json()["data"]
    assert job0["status"] in ("queued", "running", "completed") and job0["provider"] == "cloudflare"
    job = wait_done(client, uid)
    assert job["status"] == "completed", job
    assert job["result"]["summary"]["reviews_analysed"] == 8 and job["usage"]["requests"] == cf.calls and job["usage"]["neurons"] == pytest.approx(2.0 * cf.calls)
    assert job["progress"]["phase"] == "done"

    a = client.get(f"{P}/{uid}/analysis").json()["data"]
    assert a["provider"] == "cloudflare_workers_ai" and a["dataset"]["reviews_analysed"] == 8 and a["dataset"]["extraction_failed"] == 0
    assert sum(v["n"] for v in a["sentiment"].values()) == 8
    assert 1 <= len(a["themes"]) <= 5
    # counts are computed by code from per-review extractions
    reviews = client.get(f"{P}/{uid}/analysis/reviews?page_size=50").json()["data"]
    for t in a["themes"]:
        assert t["review_count"] == sum(1 for r in reviews if t["name"] in r["theme_names"]) == len(t["review_ids"])
        assert t["pct_of_analysed"] == pytest.approx(100 * t["review_count"] / 8, abs=0.06)
    # original ids and URLs preserved; every quote is verbatim in the uploaded review
    src = {rid.replace("T-", "W-"): (text, url) for rid, text, url, _ in REVIEWS}
    assert {r["review_id"] for r in reviews} == set(src)
    assert all(r["source_url"] == src[r["review_id"]][1] for r in reviews)
    assert a["evidence"]
    for e in a["evidence"]:
        text, url = src[e["review_id"]]
        assert " ".join(e["quote"].replace(" …", "").split()) in " ".join(text.split()) and e["source_url"] == url
    # the model's invented quote (review ending ...3) was replaced by a verbatim excerpt; invented citations, digit-text and evidence-free items were dropped
    assert a["quality"]["reviews_with_review_start_excerpt"] >= 1
    assert a["quality"]["citations_dropped_unverifiable"] >= 3 and a["quality"]["items_dropped_for_digits"] == 1 and a["quality"]["items_dropped_without_evidence"] >= 2
    assert [i["title"] for i in a["insights"]] == ["Delays frustrate customers", "Support gaps"]
    assert len(a["opportunities"]) == 1 and a["opportunities"][0]["related_themes"] and all(x in {e["evidence_id"] for e in a["evidence"]} for x in a["opportunities"][0]["evidence_ids"])
    assert "hypothesis" in " ".join(a["opportunities"][0]) or a["opportunities"][0]["suggested_improvement_hypothesis"]
    assert a["usage"]["requests"] == cf.calls and a["usage"]["input_tokens"] > 0 and a["usage"]["output_tokens"] > 0
    assert TOKEN not in json.dumps(a) and TOKEN not in json.dumps(job)
    # filters / pagination on per-review results
    neg = client.get(f"{P}/{uid}/analysis/reviews?sentiment=negative").json()
    assert neg["meta"]["total"] == a["sentiment"]["Negative"]["n"]
    assert client.get(f"{P}/{uid}").json()["data"]["analysis_status"] == "analysed"
    # the approved Urban Company analysis is untouched
    assert fingerprint() == before


def test_saved_results_are_reused_without_new_llm_calls(client, cf):
    uid = upload(client, make_csv(prefix="R"))
    client.post(f"{P}/{uid}/process")
    assert wait_done(client, uid)["status"] == "completed"
    calls = cf.calls
    again = client.post(f"{P}/{uid}/process").json()["data"]
    assert again["status"] == "completed" and again["reused_saved_results"] is True and cf.calls == calls
    forced = client.post(f"{P}/{uid}/process?force=true").json()["data"]
    assert forced["status"] in ("queued", "running", "completed")
    assert wait_done(client, uid)["status"] == "completed"
    assert cf.calls == calls            # identical prompts -> served from the response cache, still no paid calls


def test_row_limit_and_failed_extractions_are_reported_honestly(client, cf, monkeypatch):
    monkeypatch.setattr(config, "MAX_ANALYSIS_REVIEWS", 6)
    cf.fail_extract_for = {"ROW-00002"}
    uid = upload(client, make_csv(prefix="L"))
    client.post(f"{P}/{uid}/process")
    job = wait_done(client, uid)
    assert job["status"] == "completed" and "beyond the 6-review limit" in job["message"]
    d = client.get(f"{P}/{uid}/analysis").json()["data"]["dataset"]
    assert d["rows_in_upload"] == 8 and d["rows_submitted_to_analysis"] == 6 and d["rows_not_analysed_due_to_limit"] == 2 and d["extraction_failed"] == 1 and d["reviews_analysed"] == 5


def test_not_configured_when_no_credentials(client, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_PROCESSOR", "cloudflare")
    monkeypatch.setattr(config, "account_id", lambda: None)
    monkeypatch.setattr(config, "api_token", lambda: None)
    llm_service.set_llm_factory(None)
    uid = upload(client, make_csv(extra="T-009,Another review that is different from all the others here,https://example.com/r/9,Reddit,\n"))
    job = client.post(f"{P}/{uid}/process").json()["data"]
    assert job["status"] == "not_configured" and job["provider_configured"] is False
    assert client.get(f"{P}/{uid}").json()["data"]["analysis_status"] == "not_analysed"


def test_interrupted_jobs_are_recovered_and_delete_is_blocked_while_running(client):
    uid = upload(client, make_csv(extra="T-010,A different review used by the recovery test only here,https://example.com/r/10,Reddit,\n"))
    storage.update_job(uid, status="running", job_id="JOB-x")
    assert client.delete(f"{P}/{uid}").json()["error"]["code"] == "job_running"
    assert storage.recover_interrupted_jobs() >= 1
    j = client.get(f"{P}/{uid}/job").json()["data"]
    assert j["status"] == "failed" and "Interrupted" in j["message"]
    assert client.delete(f"{P}/{uid}").json()["data"]["deleted"] is True


# ------------------------------------------------------------------------------------------------ status, usage, single review, ask
def test_llm_status_exposes_no_secrets(client, cf):
    r = client.get("/api/v1/llm/status")
    d = r.json()["data"]
    assert d["provider"] == "cloudflare" and d["configured"] is True and d["model"] == "@cf/google/gemma-4-26b-a4b-it"
    assert TOKEN not in r.text and "cfut_" not in r.text


def test_single_review_analysis_and_usage_tracking(client, cf):
    before = client.get("/api/v1/llm/usage").json()["data"]
    r = client.post("/api/v1/llm/analyse-review", json={"text": "The technician was late and the support chat closed my ticket. Terrible."})
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["sentiment"] in ("Negative", "Mixed") and d["themes"] and d["evidence_quote"] and d["extraction_status"] == "ok"
    after = client.get("/api/v1/llm/usage").json()["data"]
    assert after["requests"] == before["requests"] + 1 and after["neurons"] == pytest.approx(before["neurons"] + 2.0)
    assert after["input_tokens"] > before["input_tokens"] and after["failed_requests"] == before["failed_requests"]
    assert client.post("/api/v1/llm/analyse-review", json={"text": "x"}).status_code == 422


def test_ask_answer_is_grounded_cached_and_drops_invented_citations(client, cf):
    r = client.get("/api/v1/ask/answer?q=refund delayed money")
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["answer"] and d["citations"] and d["citations_dropped_unverifiable"] == 1 and d["cached"] is False and d["usage"]["neurons"] == 2.0
    for c in d["citations"]:
        rev = client.get(f"/api/v1/reviews/{c['review_id']}").json()["data"]
        assert " ".join(c["quote"].split()) in " ".join((rev["review_title"] or "").split() + rev["review_text"].split()) or c["quote"] in rev["review_text"]
        assert c["source_url"].startswith("http")
    calls = cf.calls
    d2 = client.get("/api/v1/ask/answer?q=refund delayed money").json()["data"]
    assert d2["cached"] is True and d2["usage"]["neurons"] == 0.0 and cf.calls == calls
    assert client.get("/api/v1/ask/answer?q=zzzqqq xxyyzz").json()["data"]["answer"] is None
    assert client.get("/api/v1/ask/answer?q=the and of").status_code == 422
    assert d["headline"] and "[" not in d["answer"] and d["reviews_matching"] >= d["reviews_considered"] >= 1
    assert d["evidence_strength"] == "moderate"  # "strong" needs at least three verified citations


def test_ask_answer_out_of_scope_and_question_brief(client, cf):
    oos = client.get("/api/v1/ask/answer?q=what is the capital of France").json()["data"]
    assert oos["answer"] is None and oos["reason"] == "out_of_scope"
    b = client.get("/api/v1/questions/Q4/brief")
    assert b.status_code == 200, b.text
    d = b.json()["data"]
    assert d["headline"] and d["answer"] and not any(ch.isdigit() for ch in d["headline"] + d["answer"])
    assert client.get("/api/v1/questions/Q99/brief").status_code == 404


def test_ask_answer_requires_configuration(client, monkeypatch):
    llm_service.set_llm_factory(None)
    monkeypatch.setattr(config, "account_id", lambda: None)
    r = client.get("/api/v1/ask/answer?q=refund delayed")
    assert r.status_code == 503 and r.json()["error"]["code"] == "llm_not_configured"
