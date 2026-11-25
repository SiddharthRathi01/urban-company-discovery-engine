"""Golden sets: a hand-labelled CSV that the engine is run on, with agreement metrics (engine vs human).

golden/<GS-id>/golden.csv       accepted rows (text + human labels)
               meta.json        name, counts, column mapping, flags (primary)
               job.json         evaluation job (queued/running/completed/failed/not_configured) with progress
               evaluation.json  engine output per row + agreement metrics + usage
"""
import csv
import hashlib
import json
import logging
import secrets
import shutil
import threading
import time
from collections import Counter
from datetime import datetime, timezone

from backend import csv_analysis, return_class as RCL
from backend.llm import DailyLimitReached, LLMFailure, LLMFatal, UsageTracker, get_tracker

from .. import llm_service, settings
from ..responses import ApiError, not_found
from ..uploads import storage as ustore
from .validator import validate_golden

log = logging.getLogger("discovery.golden")
COLS = ["row_id", "source_line", "review_id", "review_text", "human_sentiment", "human_return", "human_theme", "rating", "source_url", "source"]
_LOCK = threading.Lock()
SENTS = ["Positive", "Negative", "Neutral", "Mixed"]


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _dir(gid):
    import re
    if not re.match(r"^GS-\d{14}-[0-9a-f]{6}$", gid or ""):
        raise not_found("golden_set", gid)
    d = settings.GOLDEN_DIR / gid
    if not d.is_dir():
        raise not_found("golden_set", gid)
    return d


def _w(path, obj):
    ustore._write_json(path, obj)


def _r(path):
    return ustore._read_json(path)


def list_sets():
    out = []
    if settings.GOLDEN_DIR.is_dir():
        for d in sorted(settings.GOLDEN_DIR.iterdir(), reverse=True):
            if d.is_dir() and (d / "meta.json").exists():
                m = _r(d / "meta.json")
                m["evaluated"] = (d / "evaluation.json").exists()
                j = d / "job.json"
                m["job_status"] = _r(j).get("status") if j.exists() else "not_started"
                if m["evaluated"]:
                    m["evaluation_summary"] = _r(d / "evaluation.json")["summary"]
                out.append(m)
    return out


def create(raw, filename, content_type, mapping=None, name=None):
    rep = validate_golden(raw, filename, content_type, mapping)
    sha = hashlib.sha256(raw + json.dumps(mapping or {}, sort_keys=True).encode()).hexdigest()
    prior = next((m for m in list_sets() if m.get("sha256") == sha), None)
    if prior:
        raise ApiError(409, "duplicate_golden_set", "This file was already uploaded as a golden set.", {"golden_id": prior["golden_id"]})
    gid = f"GS-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{secrets.token_hex(3)}"
    d = settings.GOLDEN_DIR / gid
    d.mkdir(parents=True, exist_ok=False)
    with open(d / "golden.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows({k: r.get(k, "") if r.get(k) is not None else "" for k in COLS} for r in rep["rows"])
    meta = {"golden_id": gid, "name": (name or filename or "golden set")[:120], "filename": ustore.safe_name(filename), "created_at": now(), "sha256": sha, "primary": False,
            "summary": rep["summary"], "column_mapping": rep["column_mapping"], "issues": rep["issues"], "issue_counts": rep["issue_counts"]}
    _w(d / "meta.json", meta)
    log.info("stored golden set %s (%d rows)", gid, rep["summary"]["accepted"])
    return meta


def get(gid):
    d = _dir(gid)
    m = _r(d / "meta.json")
    m["evaluated"] = (d / "evaluation.json").exists()
    m["job"] = _r(d / "job.json") if (d / "job.json").exists() else {"status": "not_started"}
    if m["evaluated"]:
        ev = _r(d / "evaluation.json")
        m["evaluation_summary"] = ev["summary"]
        m["usage"] = ev.get("usage")
    return m


def evaluation(gid):
    p = _dir(gid) / "evaluation.json"
    if not p.exists():
        raise ApiError(404, "evaluation_not_found", "This golden set has not been evaluated yet.", {"golden_id": gid})
    return _r(p)


def set_primary(gid):
    _dir(gid)
    with _LOCK:
        for m in list_sets():
            md = settings.GOLDEN_DIR / m["golden_id"] / "meta.json"
            meta = _r(md)
            meta["primary"] = (m["golden_id"] == gid)
            _w(md, meta)
    return get(gid)


def delete(gid):
    d = _dir(gid)
    if (d / "job.json").exists() and _r(d / "job.json").get("status") in ("queued", "running"):
        raise ApiError(409, "job_running", "This golden set is being evaluated.", {"golden_id": gid})
    shutil.rmtree(d)


def _update_job(gid, **f):
    d = _dir(gid)
    with _LOCK:
        j = _r(d / "job.json") if (d / "job.json").exists() else {}
        j.update(f)
        j["updated_at"] = now()
        _w(d / "job.json", j)
        return j


# ------------------------------------------------------------------------------------------------ metrics
def kappa(pairs, labels):
    """Cohen's kappa for (human, engine) pairs over the given label set."""
    n = len(pairs)
    if n == 0:
        return None
    po = sum(1 for h, e in pairs if h == e) / n
    ch, ce = Counter(h for h, _ in pairs), Counter(e for _, e in pairs)
    pe = sum((ch[l] / n) * (ce[l] / n) for l in labels)
    return None if pe == 1 else round((po - pe) / (1 - pe), 3)


def confusion(pairs, labels):
    return {h: {e: sum(1 for a, b in pairs if a == h and b == e) for e in labels} for h in labels}


def evaluate_rows(llm, rows, progress, tag):
    """Run the engine over the golden rows. Returns the evaluation dict (without usage)."""
    work = [{"row_id": r["row_id"], "review_id": r["review_id"], "review_title": "", "review_text": r["review_text"], "platform": r.get("source") or "", "source_url": r.get("source_url") or "",
             "review_date": "", "rating": r.get("rating") or ""} for r in rows]
    bs = max(1, __import__("backend.config", fromlist=["config"]).UPLOAD_BATCH_SIZE)
    batches = [work[i:i + bs] for i in range(0, len(work), bs)]
    raw, errs, done = {}, {}, 0
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from backend import config
    progress("engine", 0, len(batches), f"Running the engine on {len(work)} reviews")
    with ThreadPoolExecutor(max_workers=max(1, config.CONCURRENCY)) as ex:
        futs = [ex.submit(csv_analysis._extract_batch, llm, b, tag) for b in batches]
        for f in as_completed(futs):
            res, er = f.result()
            raw.update(res); errs.update(er); done += 1
            progress("engine", done, len(batches), f"{len(raw)} of {len(work)} reviews read")
    out, by_work = [], {w["row_id"]: w for w in work}
    for r in rows:
        rec = csv_analysis._record(by_work[r["row_id"]], raw.get(r["row_id"]), errs.get(r["row_id"], "no result returned"))
        ok = rec["extraction_status"] == "ok"
        e_s, e_r = (rec["sentiment"], rec["return_class"]) if ok else (None, None)
        sm = None if (not r["human_sentiment"] or not ok) else (r["human_sentiment"] == e_s)
        rm = None if (not r["human_return"] or not ok) else (r["human_return"] == e_r)
        flags = [x for x in (sm, rm) if x is not None]
        status = "Not analysed" if not ok else ("Full match" if flags and all(flags) else "Partial match" if any(flags) else "Non-match")
        out.append({**{k: r[k] for k in ("row_id", "review_id", "review_text", "human_sentiment", "human_return", "human_theme", "rating", "source_url", "source")},
                    "engine_sentiment": e_s, "engine_return": e_r, "engine_return_basis": rec["return_basis"] if ok else None, "engine_return_confidence": rec["return_confidence"] if ok else None,
                    "engine_themes": rec["themes"] if ok else [], "engine_problem": rec["problem"] if ok else None, "engine_evidence_quote": rec["evidence_quote"],
                    "sentiment_match": sm, "return_match": rm, "match_status": status, "error": errs.get(r["row_id"])})
    sp = [(x["human_sentiment"], x["engine_sentiment"]) for x in out if x["sentiment_match"] is not None]
    sp_nomix = [(h, e) for h, e in sp if h != "Mixed"]
    rp = [(x["human_return"], x["engine_return"]) for x in out if x["return_match"] is not None]
    rp_cls = [(h, e) for h, e in rp if h != "Insufficient Evidence" and e != "Insufficient Evidence"]
    pct = lambda a, n: round(100 * a / n, 1) if n else None
    summary = {"rows": len(out), "analysed": sum(1 for x in out if x["match_status"] != "Not analysed"),
               "match_counts": {k: sum(1 for x in out if x["match_status"] == k) for k in ("Full match", "Partial match", "Non-match", "Not analysed")},
               "sentiment": {"compared": len(sp), "agree": sum(1 for h, e in sp if h == e), "agreement_pct": pct(sum(1 for h, e in sp if h == e), len(sp)),
                             "agreement_pct_excluding_mixed": pct(sum(1 for h, e in sp_nomix if h == e), len(sp_nomix)), "kappa": kappa(sp, SENTS + ["Unclear"]),
                             "confusion": confusion(sp, SENTS + ["Unclear"]) if sp else {}},
               "return": {"compared": len(rp), "agree": sum(1 for h, e in rp if h == e), "agreement_pct": pct(sum(1 for h, e in rp if h == e), len(rp)),
                          "agreement_pct_when_both_classified": pct(sum(1 for h, e in rp_cls if h == e), len(rp_cls)), "both_classified": len(rp_cls), "kappa": kappa(rp, RCL.CLASSES),
                          "confusion": confusion(rp, RCL.CLASSES) if rp else {}},
               "caution": "Agreement with these labels measures how often the engine and the labeller agree. It is an accuracy estimate only if the golden set is a representative sample labelled independently of the engine."}
    return {"summary": summary, "rows": out}


def run(gid, force=False):
    d = _dir(gid)
    j = _r(d / "job.json") if (d / "job.json").exists() else None
    if j and j.get("status") in ("queued", "running"):
        return j
    if j and j.get("status") == "completed" and (d / "evaluation.json").exists() and not force:
        return {**j, "reused_saved_results": True, "message": (j.get("message") or "") + " (saved results reused; no AI calls were made)"}
    if not llm_service.is_configured():
        job = {"golden_id": gid, "status": "not_configured", "message": "Cloudflare Workers AI is not configured on the backend, so the golden set cannot be run through the engine.", "created_at": now()}
        _w(d / "job.json", job)
        return job
    with open(d / "golden.csv", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    job = {"golden_id": gid, "job_id": f"JOB-{secrets.token_hex(4)}", "status": "queued", "created_at": now(), "message": "Queued: the engine runs in the background.", "rows": len(rows)}
    _w(d / "job.json", job)

    def work():
        def prog(phase, done, total, message=""):
            _update_job(gid, progress={"phase": phase, "done": done, "total": total, "message": message})
        try:
            with ustore._RUN_LOCK:
                _update_job(gid, status="running", started_at=now())
                tracker, t0 = get_tracker(), time.time()
                before = len(tracker.entries())
                tag = "gold" + gid[-6:]
                ev = evaluate_rows(llm_service.get_llm(), [dict(r, rating=r.get("rating")) for r in rows], prog, tag)
                mine = [e for e in tracker.entries()[before:] if str(e.get("purpose", "")).startswith(f"upl_{tag}_")]
                usage = UsageTracker.summarise(mine)
                usage["processing_seconds"] = round(time.time() - t0, 1)
                ev.update({"golden_id": gid, "generated_at": now(), "usage": usage, "model": llm_service.get_llm().model})
                _w(d / "evaluation.json", ev)
                s = ev["summary"]
                _update_job(gid, status="completed", finished_at=now(), usage=usage, message=f"Engine run on {s['analysed']} of {s['rows']} reviews: {s['match_counts']['Full match']} full matches, {s['match_counts']['Partial match']} partial, {s['match_counts']['Non-match']} non-matches.")
        except DailyLimitReached as e:
            _update_job(gid, status="failed", message=f"Cloudflare daily neuron allowance reached. Finished batches are cached, so re-running later resumes cheaply. {str(e)[:120]}")
        except (LLMFatal, LLMFailure) as e:
            _update_job(gid, status="failed", message=f"Engine run failed: {str(e)[:200]}")
        except Exception as e:  # noqa: BLE001
            log.exception("golden evaluation failed")
            _update_job(gid, status="failed", message=f"Engine run failed: {type(e).__name__}")
    threading.Thread(target=work, daemon=True, name=f"golden-{gid}").start()
    return job


def recover_interrupted():
    n = 0
    if settings.GOLDEN_DIR.is_dir():
        for d in settings.GOLDEN_DIR.iterdir():
            j = d / "job.json"
            if d.is_dir() and j.exists() and _r(j).get("status") in ("queued", "running"):
                _update_job(d.name, status="failed", message="Interrupted by a server restart. Run it again; finished batches are cached.")
                n += 1
    return n
