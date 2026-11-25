"""The public site: official files are read-only, visitors' files are analysed in a temporary session and never stored."""
import csv
import io
import os

import pytest

from backend.api import settings
from tests.test_upload_analysis import REVIEWS, cf, make_csv  # noqa: F401  (cf is a fixture)


@pytest.fixture
def public(monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_MODE", True)


def stored(path):
    return sorted(os.listdir(path)) if path.is_dir() else []


def test_write_endpoints_are_switched_off_and_uploads_are_not_listed(client, public):
    f = {"file": ("x.csv", make_csv(), "text/csv")}
    for call in (lambda: client.post("/api/v1/uploads", files=f), lambda: client.post("/api/v1/uploads/UP-1/process"), lambda: client.delete("/api/v1/uploads/UP-1"),
                 lambda: client.post("/api/v1/golden", files=f), lambda: client.post("/api/v1/golden/GS-1/evaluate"), lambda: client.post("/api/v1/golden/GS-1/primary"),
                 lambda: client.delete("/api/v1/golden/GS-1")):
        r = call()
        assert r.status_code == 403 and r.json()["error"]["code"] == "disabled_on_public_site"
    assert client.get("/api/v1/uploads").json()["data"] == []


def test_temporary_upload_analysis_runs_in_steps_and_stores_nothing(client, public, cf):
    before = stored(settings.UPLOAD_DIR)
    r = client.post("/api/v1/temp/uploads/validate", files={"file": ("mine.csv", make_csv(), "text/csv")})
    assert r.status_code == 200, r.text
    d = r.json()["data"]
    assert d["summary"]["accepted"] == len(REVIEWS) and len(d["rows"]) == len(REVIEWS) and d["rows_per_request"] == 12
    rows, recs, parts = d["rows"], [], []
    for i in range(0, len(rows), d["rows_per_request"]):
        e = client.post("/api/v1/temp/uploads/extract", json={"rows": rows[i:i + 12], "session": "tmp-abc123"})
        assert e.status_code == 200, e.text
        recs += e.json()["data"]["records"]; parts.append(e.json()["data"]["usage"])
    assert len(recs) == len(rows) and all(x["extraction_status"] == "ok" for x in recs)
    s = client.post("/api/v1/temp/uploads/summarise", json={"rows": rows, "records": recs, "session": "tmp-abc123", "filename": "mine.csv", "rows_in_file": len(rows), "usage_parts": parts})
    assert s.status_code == 200, s.text
    a = s.json()["data"]["analysis"]
    assert a["dataset"]["reviews_analysed"] == len(REVIEWS) and a["themes"] and a["usage"]["requests"] == sum(p["requests"] for p in parts) + 2
    assert a["return_behaviour"]["reviews"] == len(REVIEWS)
    assert stored(settings.UPLOAD_DIR) == before, "a visitor's file must never be written to the server"


def test_temporary_rejections_and_limits(client, public, cf):
    assert client.post("/api/v1/temp/uploads/validate", files={"file": ("bad.csv", b"id,score\n1,5\n", "text/csv")}).status_code == 422
    assert client.post("/api/v1/temp/uploads/extract", json={"rows": [{"row_id": "ROW-1", "review_text": "x"}] * 13}).status_code == 422   # at most 12 per request
    assert client.post("/api/v1/temp/uploads/extract", json={"rows": [{"row_id": "ROW-1"}]}).status_code == 422


def test_temporary_golden_set_is_evaluated_and_not_stored(client, public, cf, monkeypatch):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["comment", "your sentiment", "return label"])
    w.writerow([REVIEWS[0][1], "Negative", "Non-Return"])
    w.writerow([REVIEWS[1][1], "Positive", "Return"])
    w.writerow([REVIEWS[6][1], "Positive", "Return"])
    before = stored(settings.GOLDEN_DIR)
    v = client.post("/api/v1/temp/golden/validate", files={"file": ("gold.csv", buf.getvalue().encode(), "text/csv")})
    assert v.status_code == 200, v.text
    rows = v.json()["data"]["rows"]
    assert len(rows) == 3
    e = client.post("/api/v1/temp/golden/evaluate", json={"rows": rows})
    assert e.status_code == 200, e.text
    ev = e.json()["data"]
    assert ev["summary"]["rows"] == 3 and ev["summary"]["sentiment"]["compared"] == 3 and len(ev["rows"]) == 3 and ev["usage"]["requests"] >= 1
    assert stored(settings.GOLDEN_DIR) == before, "a visitor's golden set must never be stored"
