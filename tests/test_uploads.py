"""CSV upload foundation: validation, storage separation, job status, and isolation from the precomputed analysis."""
import json
from pathlib import Path

import pytest

from backend.api import settings
from backend.api.uploads import processor
from backend.api.uploads.validator import UploadRejected, validate

P = "/api/v1/uploads"
GOOD = ("review_text,platform,rating,review_date,city\n"
        "The technician arrived two hours late and left without finishing,Google Play Store,2,2026-05-01,Pune\n"
        "Great service very polite,Google Play Store,5,12/05/2026,Delhi\n")


def post(client, content, name="reviews.csv", ctype="text/csv"):
    data = content if isinstance(content, bytes) else content.encode("utf-8")
    return client.post(P, files={"file": (name, data, ctype)})


def code(r):
    return r.json()["error"]["details"]["errors"][0]["code"]


def test_valid_upload_is_stored_separately_and_not_analysed(client, fingerprint):
    before = fingerprint()
    r = post(client, GOOD)
    assert r.status_code == 201, r.text
    meta = r.json()["data"]
    assert meta["status"] == "validated" and meta["analysis_status"] == "not_analysed" and meta["summary"]["accepted"] == 2
    d = Path(settings.UPLOAD_DIR) / meta["upload_id"]
    assert d.is_dir() and (d / "original.csv").exists() and (d / "accepted.csv").exists()
    assert Path(settings.UPLOAD_DIR).resolve() not in [(settings.ANALYSIS_DIR).resolve(), settings.MASTER_CSV.parent.resolve()]
    assert fingerprint() == before
    v = client.get(f"{P}/{meta['upload_id']}/validation").json()["data"]
    assert v["column_mapping"]["review_text"] == "review_text" and v["summary"]["rows_in_file"] == 2


def test_process_job_reports_not_configured_and_leaves_analysis_untouched(client, fingerprint):
    meta = post(client, GOOD.replace("Great service", "Excellent service")).json()["data"]
    before = fingerprint()
    assert client.get(f"{P}/{meta['upload_id']}/job").json()["data"]["status"] == "not_started"
    job = client.post(f"{P}/{meta['upload_id']}/process").json()["data"]
    assert job["status"] == "not_configured" and job["provider_configured"] is False and job["result"] is None and job["rows_to_process"] == 2
    assert client.get(f"{P}/{meta['upload_id']}/job").json()["data"]["job_id"] == job["job_id"]
    assert client.get(f"{P}/{meta['upload_id']}").json()["data"]["analysis_status"] == "not_analysed"
    assert fingerprint() == before
    assert client.get("/api/v1/overview").json()["data"]["dataset"]["reviews_analysed"] >= 2500


def test_rejections(client):
    assert post(client, GOOD, name="r.txt").status_code == 415
    assert post(client, GOOD, ctype="image/png").status_code == 415
    r = post(client, b"")
    assert r.status_code == 422 and code(r) == "empty_file"
    r = post(client, "rating,city\n5,Pune\n")
    assert r.status_code == 422 and code(r) == "missing_required_column"
    assert "review_text" in r.json()["error"]["details"]["errors"][0]["accepted_names"]
    r = post(client, b"review_text\n\x00\x01\x02binary")
    assert code(r) == "not_text_csv"
    r = post(client, "review_text\ncaf\xe9 service".encode("latin-1"))
    assert code(r) == "invalid_encoding"
    r = post(client, "review_text,review_text\na,b\n")
    assert code(r) == "duplicate_columns"
    r = post(client, "review_text\n\n   \n")
    assert code(r) == "no_valid_rows"


def test_row_level_validation_duplicates_and_warnings(client):
    approved = json.loads((settings.ANALYSIS_DIR / "reviews.json").read_text(encoding="utf-8"))["reviews"][0]["review_text"].replace('"', "'")
    csv_text = ("review_id,review_text,rating,review_date,source_url\n"
                "a1,Booking was cancelled twice without notice,9,not-a-date,ftp://x\n"          # warnings: rating, date, url
                "a2,Booking was cancelled twice without notice,,,\n"                              # duplicate text in file
                "a1,Another distinct review about pricing,3,2026-01-02,https://example.com/r\n"  # duplicate id
                "a4,,4,,\n"                                                                       # missing text
                "a5,x,4,,\n"                                                                      # too short
                "a6,too,many,fields,here,extra\n"                                                 # malformed
                f'a7,"{approved}",4,,\n'                                                          # already in approved dataset
                "a8,Fine review with enough words to pass,5,2026-02-03,\n")
    r = post(client, csv_text)
    assert r.status_code == 201, r.text
    rep = client.get(f"{P}/{r.json()['data']['upload_id']}/validation").json()["data"]
    s, c = rep["summary"], rep["issue_counts"]
    assert s["accepted"] == 2 and s["rows_in_file"] == 8 and s["rejected"] == 6
    assert c["duplicate_in_file"] == 1 and c["duplicate_review_id"] == 1 and c["missing_review_text"] == 1 and c["review_text_too_short"] == 1
    assert c["column_count_mismatch"] == 1 and c["already_in_approved_dataset"] == 1
    assert {"invalid_rating", "invalid_date", "invalid_url"} <= set(c)
    assert all("line" in i and "message" in i for i in rep["issues"]) and s["malformed"] == 1


def test_validator_function_directly():
    rep = validate(b"Text;Stars;Posted\nGreat job done;4;2026-03-04\nBad;1;04/03/2026\n", "a.csv", "text/csv")
    assert rep["summary"]["delimiter"] == ";" and rep["column_mapping"] == {"review_text": "Text", "rating": "Stars", "review_date": "Posted"}
    assert [r["review_date"] for r in rep["accepted_rows"]] == ["2026-03-04", "2026-03-04"]
    with pytest.raises(UploadRejected):
        validate(b"foo,bar\n1,2\n", "a.csv", "text/csv")


def test_size_limit_duplicate_upload_list_delete(client, monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_MB", 0.0001)
    r = post(client, "review_text\n" + "long review text " * 50)
    assert r.status_code == 413 and r.json()["error"]["code"] == "file_too_large"
    monkeypatch.undo()
    first = post(client, "review_text\nA unique review used for the duplicate upload test\n")
    assert first.status_code == 201
    uid = first.json()["data"]["upload_id"]
    dup = post(client, "review_text\nA unique review used for the duplicate upload test\n")
    assert dup.status_code == 409 and dup.json()["error"]["details"]["upload_id"] == uid
    lst = client.get(P).json()
    assert lst["meta"]["total"] >= 1 and uid in [u["upload_id"] for u in lst["data"]]
    assert client.delete(f"{P}/{uid}").json()["data"]["deleted"] is True
    assert client.get(f"{P}/{uid}").status_code == 404
    assert client.get(f"{P}/../etc").status_code in (404, 422)
    assert client.get(f"{P}/UP-bad").json()["error"]["code"] == "upload_not_found"


def test_processor_plugin_is_isolated_and_failures_are_contained(client, monkeypatch):
    class Boom:
        name, configured = "boom", True
        def process(self, d, rows):
            raise RuntimeError("provider exploded")
    class Fine:
        name, configured = "fine", True
        def process(self, d, rows):
            return processor.JobOutcome("completed", "ok", {"schema_version": "1.0", "files": [], "summary": {"rows": len(rows)}})
    processor.register_processor("boom", Boom); processor.register_processor("fine", Fine)
    meta = post(client, "review_text\nReview to test the processor plugin interface\n").json()["data"]
    monkeypatch.setattr(settings, "UPLOAD_PROCESSOR", "boom")
    j = client.post(f"{P}/{meta['upload_id']}/process").json()["data"]
    assert j["status"] == "failed" and "provider exploded" not in json.dumps(j)
    monkeypatch.setattr(settings, "UPLOAD_PROCESSOR", "fine")
    j = client.post(f"{P}/{meta['upload_id']}/process").json()["data"]
    assert j["status"] == "completed" and j["result"]["summary"]["rows"] == 1
    monkeypatch.setattr(settings, "UPLOAD_PROCESSOR", "does-not-exist")
    assert client.post(f"{P}/{meta['upload_id']}/process").json()["data"]["status"] == "not_configured"
