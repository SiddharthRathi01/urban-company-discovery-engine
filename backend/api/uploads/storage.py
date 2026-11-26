"""File-based storage for uploads, separate from the approved dataset (output/) and the precomputed analysis (analysis/).

uploads/<upload_id>/original.csv        exactly the bytes received
                    accepted.csv        validated, normalised rows
                    validation.json     report (summary, column mapping, issues)
                    upload.json         metadata and status
                    job.json            latest processing job (created by POST /uploads/{id}/process), with live progress
                    analysis/           LLM results: analysis.json (themes, insights, opportunities, evidence, usage), reviews.json
"""
import csv
import hashlib
import json
import logging
import re
import secrets
import shutil
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from .. import settings
from ..responses import ApiError, not_found
from .processor import JOB_STATUSES, get_processor

log = logging.getLogger("discovery.uploads")
ID_RE = re.compile(r"^UP-\d{14}-[0-9a-f]{8}$")
COLUMNS = ["row_id", "source_line", "review_id", "review_title", "review_text", "platform", "source_url", "review_date", "rating", "reviewer", "service_category", "city"]
_JOB_LOCK = threading.Lock()      # serialises job.json / upload.json writes
_RUN_LOCK = threading.Lock()      # one LLM analysis at a time (keeps neuron use predictable)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_name(name):
    base = re.sub(r"[^A-Za-z0-9._ -]", "_", Path(name or "upload.csv").name)[:120]
    return base or "upload.csv"


def _dir(upload_id, root=None):
    if not ID_RE.match(upload_id or ""):
        raise not_found("upload", upload_id)
    d = (root or settings.UPLOAD_DIR) / upload_id
    if not d.is_dir():
        raise not_found("upload", upload_id)
    return d


def _write_json(path, obj):
    """Atomic write. On Windows os.replace can briefly fail while another thread is reading the target, so retry."""
    tmp = path.with_name(path.name + f".{secrets.token_hex(3)}.tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")
    for attempt in range(40):
        try:
            tmp.replace(path)
            return
        except PermissionError:
            time.sleep(0.025)
    tmp.replace(path)


def _read_json(path):
    for attempt in range(40):
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (PermissionError, json.JSONDecodeError):
            time.sleep(0.025)
    return json.loads(path.read_text(encoding="utf-8"))


def list_uploads():
    root = settings.UPLOAD_DIR
    out = []
    if root.is_dir():
        for d in sorted(root.iterdir(), reverse=True):
            if d.is_dir() and ID_RE.match(d.name) and (d / "upload.json").exists():
                m = _read_json(d / "upload.json")
                m["has_analysis"] = (d / "analysis" / "analysis.json").exists()
                out.append(m)
    return out


def find_by_hash(sha):
    return next((u for u in list_uploads() if u.get("sha256") == sha), None)


def create_upload(raw, filename, report):
    sha = hashlib.sha256(raw).hexdigest()
    prior = find_by_hash(sha)
    if prior:
        raise ApiError(409, "duplicate_upload", "This exact file was already uploaded.", {"upload_id": prior["upload_id"]})
    uid = f"UP-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{secrets.token_hex(4)}"
    d = settings.UPLOAD_DIR / uid
    d.mkdir(parents=True, exist_ok=False)
    (d / "original.csv").write_bytes(raw)
    with open(d / "accepted.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows({k: r.get(k, "") for k in COLUMNS} for r in report["accepted_rows"])
    rep = {k: v for k, v in report.items() if k != "accepted_rows"}
    _write_json(d / "validation.json", rep)
    meta = {"upload_id": uid, "filename": safe_name(filename), "size_bytes": len(raw), "sha256": sha, "created_at": now(), "status": "validated",
            "summary": report["summary"], "analysis_status": "not_analysed", "storage": f"uploads/{uid}/",
            "note": "Stored separately from the approved dataset and the precomputed analysis. Request analysis to generate insights."}
    _write_json(d / "upload.json", meta)
    log.info("stored upload %s: %d accepted, %d rejected", uid, report["summary"]["accepted"], report["summary"]["rejected"])
    return meta


def get_upload(upload_id):
    d = _dir(upload_id)
    m = _read_json(d / "upload.json")
    m["has_analysis"] = (d / "analysis" / "analysis.json").exists()
    return m


def get_validation(upload_id):
    return _read_json(_dir(upload_id) / "validation.json")


def get_job(upload_id):
    d = _dir(upload_id)
    p = d / "job.json"
    if not p.exists():
        return {"job_id": None, "upload_id": upload_id, "status": "not_started", "message": "No processing job has been requested for this upload.", "result": None}
    return _read_json(p)


def get_analysis(upload_id):
    p = _dir(upload_id) / "analysis" / "analysis.json"
    if not p.exists():
        raise ApiError(404, "analysis_not_found", "This upload has not been analysed yet.", {"upload_id": upload_id})
    return _read_json(p)


def get_analysis_reviews(upload_id):
    p = _dir(upload_id) / "analysis" / "reviews.json"
    if not p.exists():
        raise ApiError(404, "analysis_not_found", "This upload has not been analysed yet.", {"upload_id": upload_id})
    return _read_json(p)["reviews"]


def delete_upload(upload_id):
    d = _dir(upload_id)
    j = d / "job.json"
    if j.exists() and _read_json(j).get("status") in ("queued", "running"):
        raise ApiError(409, "job_running", "This upload is being analysed; wait for the job to finish.", {"upload_id": upload_id})
    shutil.rmtree(d)
    log.info("deleted upload %s", upload_id)


# ------------------------------------------------------------------------------------------------ jobs
def update_job(upload_id, **fields):
    d = _dir(upload_id)
    with _JOB_LOCK:
        p = d / "job.json"
        job = _read_json(p) if p.exists() else {}
        job.update(fields)
        job["updated_at"] = now()
        _write_json(p, job)
        return job


def _set_analysis_status(upload_id, job_status):
    d = _dir(upload_id)
    with _JOB_LOCK:
        meta = _read_json(d / "upload.json")
        meta["analysis_status"] = {"completed": "analysed", "not_configured": "not_analysed", "failed": "failed", "queued": "pending", "running": "pending"}.get(job_status, "pending")
        _write_json(d / "upload.json", meta)


def _read_rows(d):
    with open(d / "accepted.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _finish(upload_id, proc, outcome_fn):
    """Run the processor and write the final job state. Never raises."""
    try:
        outcome = outcome_fn()
        if outcome.status not in JOB_STATUSES:
            raise ValueError(f"processor returned unknown status '{outcome.status}'")
        fields = {"status": outcome.status, "message": outcome.message, "result": outcome.result, "details": outcome.extra, "finished_at": now()}
        if outcome.result and outcome.result.get("usage"):
            fields["usage"] = outcome.result["usage"]
        update_job(upload_id, **fields)
    except ApiError:
        raise
    except Exception as exc:                                   # a processor must never break the API
        log.exception("processor failed for %s", upload_id)
        update_job(upload_id, status="failed", message=f"Processor error: {type(exc).__name__}", finished_at=now())
    _set_analysis_status(upload_id, get_job(upload_id)["status"])


def _background(upload_id, proc, d, rows, ctx):
    def progress(phase, done, total, message=""):
        update_job(upload_id, progress={"phase": phase, "done": done, "total": total, "message": message})

    def outcome():
        with _RUN_LOCK:                                         # queued jobs wait here
            update_job(upload_id, status="running", started_at=now(), progress={"phase": "starting", "done": 0, "total": 0, "message": "Starting"})
            return proc.process(d, rows, progress=progress, context=ctx)
    _finish(upload_id, proc, outcome)


def run_job(upload_id, force=False):
    d = _dir(upload_id)
    meta = _read_json(d / "upload.json")
    proc = get_processor(settings.UPLOAD_PROCESSOR)
    prior = get_job(upload_id)
    if prior["status"] in ("queued", "running"):
        return prior                                            # already in progress
    if not force and getattr(proc, "reuses_saved_results", False) and (d / "analysis" / "analysis.json").exists() and prior.get("status") == "completed":
        return {**prior, "reused_saved_results": True, "message": prior.get("message", "") + " (saved results reused; no LLM calls were made)"}
    rows = _read_rows(d)
    job = {"job_id": f"JOB-{secrets.token_hex(4)}", "upload_id": upload_id, "status": "running", "provider": proc.name, "provider_configured": bool(proc.configured),
           "created_at": now(), "updated_at": now(), "message": "", "result": None, "rows_to_process": len(rows)}
    ctx = {"upload_id": upload_id, "filename": meta.get("filename"), "rows_in_file": meta["summary"].get("rows_in_file")}
    if getattr(proc, "long_running", False) and proc.configured:
        job["status"] = "queued"
        job["message"] = "Queued: the analysis runs in the background."
        with _JOB_LOCK:
            _write_json(d / "job.json", job)
        _set_analysis_status(upload_id, "queued")
        threading.Thread(target=_background, args=(upload_id, proc, d, rows, ctx), daemon=True, name=f"analysis-{upload_id}").start()
        return job
    with _JOB_LOCK:
        _write_json(d / "job.json", job)
    _finish(upload_id, proc, lambda: proc.process(d, rows))
    return get_job(upload_id)


def recover_interrupted_jobs():
    """Called at start-up: a job left 'queued' or 'running' by a stopped server can never finish, so mark it failed (cached batches make a re-run cheap)."""
    n = 0
    if settings.UPLOAD_DIR.is_dir():
        for d in settings.UPLOAD_DIR.iterdir():
            j = d / "job.json"
            if d.is_dir() and ID_RE.match(d.name) and j.exists():
                job = _read_json(j)
                if job.get("status") in ("queued", "running"):
                    update_job(d.name, status="failed", message="Interrupted by a server restart. Run the analysis again; batches already completed are cached.", finished_at=now())
                    _set_analysis_status(d.name, "failed")
                    n += 1
    if n:
        log.warning("marked %d interrupted analysis job(s) as failed", n)
    return n
