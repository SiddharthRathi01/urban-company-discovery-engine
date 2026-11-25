"""LIVE tests against the real Cloudflare Workers AI API. They spend a small number of neurons (about 130 for the whole file), so they only run when asked:

    set RUN_LIVE_LLM_TESTS=1          (PowerShell: $env:RUN_LIVE_LLM_TESTS=1)
    .python\\python.exe -m pytest tests/test_live_cloudflare.py -s

Credentials come from the backend .env (CLOUDFLARE_ACCOUNT_ID, CLOUDFLARE_API_TOKEN). Nothing secret is printed."""
import os

import pytest

from backend import config, csv_analysis
from backend import llm as L
from backend.api import llm_service, settings
from tests.test_upload_analysis import P, REVIEWS, make_csv, upload, wait_done

pytestmark = pytest.mark.skipif(os.environ.get("RUN_LIVE_LLM_TESTS") != "1" or not config.is_configured(), reason="live LLM tests are opt-in (RUN_LIVE_LLM_TESTS=1) and need credentials")


@pytest.fixture
def live(monkeypatch):
    llm_service.set_llm_factory(None)
    monkeypatch.setattr(settings, "UPLOAD_PROCESSOR", "cloudflare")
    yield L.get_tracker()


def spent(tracker, before):
    after = tracker.summary()
    return {"requests": after["requests"] - before["requests"], "failed": after["failed_requests"] - before["failed_requests"], "input_tokens": after["input_tokens"] - before["input_tokens"],
            "output_tokens": after["output_tokens"] - before["output_tokens"], "neurons": round(after["neurons"] - before["neurons"], 2)}


def test_connection_and_single_review(live):
    b = live.summary()
    llm = llm_service.get_llm()
    c = llm.check_connection()
    assert c["connected"] is True and c["test_completion"]
    row = {"row_id": "ROW-00001", "review_id": "X-1", "review_title": "", "review_text": "The professional arrived two hours late, did a poor job, and support never called back.", "platform": "", "source_url": "", "review_date": "", "rating": "1"}
    raw, errors = csv_analysis._extract_batch(llm, [row], "livesingle")
    assert not errors
    rec = csv_analysis._record(row, raw["ROW-00001"])
    assert rec["sentiment"] == "Negative" and rec["themes"] and rec["evidence_source"] == "model_quote"
    print("\nconnection + single review:", spent(live, b))


def test_csv_upload_to_analysis_to_dashboard_and_ask(live, client):
    b = live.summary()
    uid = upload(client, make_csv(prefix="LIVE"))
    client.post(f"{P}/{uid}/process")
    job = wait_done(client, uid, timeout=300)
    assert job["status"] == "completed", job
    a = client.get(f"{P}/{uid}/analysis").json()["data"]
    assert a["dataset"]["reviews_analysed"] == len(REVIEWS) and 1 <= len(a["themes"]) <= 5 and a["insights"] and a["evidence"]
    assert sum(v["n"] for v in a["sentiment"].values()) == len(REVIEWS)
    src = {r[0].replace("T-", "LIVE-"): " ".join(r[1].split()) for r in REVIEWS}
    for e in a["evidence"]:
        assert " ".join(e["quote"].replace(" …", "").split()) in src[e["review_id"]]
    print("\nupload analysis:", spent(live, b), "| job usage:", {k: a["usage"][k] for k in ("requests", "input_tokens", "output_tokens", "neurons", "processing_seconds")})
    b2 = live.summary()
    ans = client.get("/api/v1/ask/answer?q=refund not received").json()["data"]
    assert ans["answer"] and ans["citations"]
    print("ask answer:", spent(live, b2))
    assert client.delete(f"{P}/{uid}").json()["data"]["deleted"]
