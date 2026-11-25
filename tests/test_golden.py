"""Golden set: upload a hand-labelled CSV, run the engine (fake Cloudflare transport), compare engine and human labels."""
import time

import pytest

from backend import config
from backend import llm as L
from backend.api import llm_service, settings
from tests.fakes import TOKEN, FakeCloudflare

G = "/api/v1/golden"
CSV = (
    "id,comment,your sentiment,return label,your problem label,stars\n"
    "A1,Great service and I will definitely book again,Positive,Return,quality,5\n"
    "A2,The technician was late and refused to help,Negative,Non-Return,punctuality,1\n"
    "A3,Okay service nothing special,Neutral,Insufficient Evidence,none,\n"
    "A4,Lovely polite beautician,Positive,Non-Return,quality,\n"
    "A5,The chatbot never replied and I say do not use this app,Neutral,Return,support,\n"
)


@pytest.fixture
def cf(monkeypatch, tmp_path):
    fake = FakeCloudflare(neurons=2.0)
    monkeypatch.setattr(L.time, "sleep", lambda s: None)
    llm_service.set_llm_factory(lambda: L.CloudflareLLM(cache_dir=tmp_path / "cache", transport=fake, tracker=L.get_tracker(), account="acc", token=TOKEN))
    yield fake
    llm_service.set_llm_factory(None)


def post(client, text, name="golden.csv", **form):
    return client.post(G, files={"file": (name, text.encode("utf-8"), "text/csv")}, data=form)


def wait(client, gid, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        j = client.get(f"{G}/{gid}/job").json()["data"]
        if j["status"] in ("completed", "failed", "not_configured"):
            return j
        time.sleep(0.2)
    raise AssertionError("evaluation did not finish")


def test_upload_maps_columns_and_normalises_labels(client):
    r = post(client, CSV)
    assert r.status_code == 201, r.text
    m = r.json()["data"]
    assert m["summary"]["accepted"] == 5 and m["summary"]["with_sentiment_label"] == 5 and m["summary"]["with_return_label"] == 5 and m["summary"]["with_problem_label"] == 5
    assert m["column_mapping"] == {"text": "comment", "id": "id", "human_sentiment": "your sentiment", "human_return": "return label", "human_theme": "your problem label", "rating": "stars"}
    assert post(client, CSV).status_code == 409                                  # same file + mapping
    client.delete(f"{G}/{m['golden_id']}")


def test_explicit_mapping_and_rejections(client):
    csv = "Comment text,Mood,x\nThe plumber fixed the leak quickly,pos,1\nBilling was a mess and nobody called back,neg,2\n"
    r = post(client, csv, mapping='{"text": "Comment text", "human_sentiment": "Mood"}')
    assert r.status_code == 201 and r.json()["data"]["summary"]["accepted"] == 2 and r.json()["data"]["column_mapping"] == {"text": "Comment text", "human_sentiment": "Mood"}
    client.delete(f"{G}/{r.json()['data']['golden_id']}")
    for bad, code in [("rating,x\n5,1\n", "missing_required_column"), ("comment,x\nhello there friend,1\n", "missing_human_labels"), ("comment,sentiment\n,Positive\n  ,Negative\n", "no_valid_rows")]:
        r = post(client, bad)
        assert r.status_code == 422 and r.json()["error"]["details"]["errors"][0]["code"] == code, (code, r.text)
    assert post(client, "comment,sentiment\nhello,Positive\n", mapping='{"text": "nope"}').json()["error"]["details"]["errors"][0]["code"] == "unknown_column"
    assert post(client, "comment,sentiment\nhello,Positive\n", mapping="not json").json()["error"]["code"] == "invalid_mapping"
    assert client.post(G, files={"file": ("g.txt", b"comment,sentiment\nhi,Positive\n", "text/plain")}).status_code == 415


def test_row_level_issues(client, monkeypatch):
    csv = "comment,sentiment,return\nOne distinct review about plumbing work,Positive,maybe\nOne distinct review about plumbing work,Positive,Return\nAnother review about cleaning,sorta,\nThird review about salon work,Negative,Non-Return\n"
    r = post(client, csv)
    assert r.status_code == 201
    m = r.json()["data"]
    assert m["summary"]["accepted"] == 2 and m["issue_counts"] == {"unrecognised_return_label": 1, "duplicate_in_file": 1, "unrecognised_sentiment": 1, "no_usable_human_label": 1}
    client.delete(f"{G}/{m['golden_id']}")
    monkeypatch.setattr(settings, "MAX_GOLDEN_ROWS", 3)
    assert post(client, CSV.replace("Great service", "Great service number two")).status_code == 413


def test_evaluation_metrics_rows_reuse_primary_and_delete(client, cf):
    gid = post(client, CSV.replace("quality", "quality of work")).json()["data"]["golden_id"]
    job = client.post(f"{G}/{gid}/evaluate").json()["data"]
    assert job["status"] in ("queued", "running", "completed")
    job = wait(client, gid)
    assert job["status"] == "completed", job
    ev = client.get(f"{G}/{gid}/evaluation").json()["data"]
    s = ev["summary"]
    assert s["rows"] == 5 and s["analysed"] == 5 and s["match_counts"] == {"Full match": 3, "Partial match": 1, "Non-match": 1, "Not analysed": 0}
    assert s["sentiment"]["compared"] == 5 and s["sentiment"]["agree"] == 4 and s["sentiment"]["agreement_pct"] == 80.0
    assert s["return"]["compared"] == 5 and s["return"]["agree"] == 3 and s["return"]["agreement_pct"] == 60.0
    assert s["return"]["confusion"]["Return"]["Return"] == 1 and s["sentiment"]["kappa"] is not None and "caution" in s
    assert ev["usage"]["requests"] >= 1 and ev["usage"]["neurons"] > 0 and TOKEN not in str(ev)
    rows = client.get(f"{G}/{gid}/rows?page_size=10").json()
    assert rows["meta"]["total"] == 5
    by_id = {r["review_id"]: r for r in rows["data"]}
    assert by_id["A1"]["engine_return"] == "Return" and by_id["A1"]["engine_return_basis"] == "Stated" and by_id["A5"]["engine_return"] == "Non-Return" and by_id["A5"]["engine_return_basis"] == "Signalled"
    assert by_id["A4"]["match_status"] == "Partial match" and by_id["A5"]["match_status"] == "Non-match" and by_id["A2"]["engine_return_basis"] == "Inferred"
    assert client.get(f"{G}/{gid}/rows?match=non-match").json()["meta"]["total"] == 1
    calls = cf.calls
    again = client.post(f"{G}/{gid}/evaluate").json()["data"]
    assert again["status"] == "completed" and again["reused_saved_results"] is True and cf.calls == calls
    # primary flag is exclusive
    gid2 = post(client, "comment,sentiment\nSecond golden set review text goes here,Positive\n").json()["data"]["golden_id"]
    client.post(f"{G}/{gid}/primary"); client.post(f"{G}/{gid2}/primary")
    listing = client.get(G).json()
    assert [x["golden_id"] for x in listing["data"] if x["primary"]] == [gid2] and listing["meta"]["primary"] == gid2
    assert next(x for x in listing["data"] if x["golden_id"] == gid)["evaluated"] is True
    assert client.get(f"{G}/{gid2}/evaluation").json()["error"]["code"] == "evaluation_not_found"
    for g in (gid, gid2):
        assert client.delete(f"{G}/{g}").json()["data"]["deleted"] is True
    assert client.get(f"{G}/{gid}").status_code == 404


def test_evaluation_requires_credentials(client, monkeypatch):
    llm_service.set_llm_factory(None)
    monkeypatch.setattr(config, "account_id", lambda: None)
    gid = post(client, "comment,sentiment\nA review used only by the credentials test,Positive\n").json()["data"]["golden_id"]
    j = client.post(f"{G}/{gid}/evaluate").json()["data"]
    assert j["status"] == "not_configured"
    client.delete(f"{G}/{gid}")


def test_kappa_and_return_rules_unit():
    from backend.api.golden.store import kappa
    assert kappa([("a", "a"), ("b", "b")], ["a", "b"]) == 1.0
    assert kappa([("a", "b"), ("b", "a")], ["a", "b"]) == -1.0
    assert kappa([], ["a"]) is None
