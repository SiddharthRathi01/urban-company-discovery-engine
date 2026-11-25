"""Temporary analysis for visitors: nothing a visitor uploads is stored on the server.

A visitor's file is checked, read by the engine and shown, with every result held only in the visitor's own browser tab. The work is split into short
requests (check the file, read a few comments at a time, then group and summarise) so it also fits the time limit of a serverless host. The official
Urban Company analysis and the official golden set are never touched by these endpoints."""
import json
import logging
from typing import Any

from fastapi import APIRouter, File, Form, UploadFile
from pydantic import BaseModel, Field

from backend import config, csv_analysis
from backend.api.golden import store as gstore
from backend.api.golden.validator import ALIASES, FIELDS, validate_golden
from backend.llm import UsageTracker, get_tracker

from .. import settings
from ..responses import ApiError, envelope
from ..uploads.validator import UploadRejected, validate
from . import uploads as upload_router
from .llm import llm_errors, need_llm

router = APIRouter(prefix="/temp", tags=["temporary session (nothing is stored)"])
log = logging.getLogger("discovery.temp")
EXTRACT_ROWS_PER_REQUEST = 12                     # two engine batches of six: about 30-40 seconds
TEMP_GOLDEN_MAX_ROWS = 100


class RowsIn(BaseModel):
    rows: list[dict[str, Any]] = Field(..., max_length=EXTRACT_ROWS_PER_REQUEST)
    session: str = Field("tmp", max_length=40)


class SummariseIn(BaseModel):
    rows: list[dict[str, Any]] = Field(..., max_length=config.MAX_ANALYSIS_REVIEWS)
    records: list[dict[str, Any]] = Field(..., max_length=config.MAX_ANALYSIS_REVIEWS)
    session: str = Field("tmp", max_length=40)
    filename: str | None = Field(None, max_length=200)
    rows_in_file: int | None = None
    usage_parts: list[dict[str, Any]] = Field(default_factory=list, max_length=60)


class GoldenIn(BaseModel):
    rows: list[dict[str, Any]] = Field(..., max_length=TEMP_GOLDEN_MAX_ROWS)
    name: str | None = Field(None, max_length=120)


def _clean_rows(rows):
    keep = ("row_id", "review_id", "review_title", "review_text", "platform", "source_url", "review_date", "rating")
    out = []
    for r in rows:
        if not isinstance(r.get("row_id"), str) or not isinstance(r.get("review_text"), str) or not r["review_text"].strip():
            raise ApiError(422, "invalid_rows", "Each row needs a row_id and review_text.")
        out.append({k: (str(r.get(k)) if r.get(k) is not None else "") for k in keep} | {"review_text": r["review_text"][: settings.MAX_REVIEW_CHARS]})
    return out


@router.post("/uploads/validate", summary="Check a CSV and return its rows. Nothing is stored.")
async def validate_upload(file: UploadFile = File(...)):
    raw = await upload_router.read_limited(file)
    try:
        report = validate(raw, file.filename, file.content_type, upload_router.approved_texts())
    except UploadRejected as exc:
        raise ApiError(exc.status, "upload_rejected", "The file was rejected.", {"errors": exc.errors})
    rows = report.pop("accepted_rows")
    limit = config.MAX_ANALYSIS_REVIEWS
    return envelope({"filename": file.filename, "summary": report["summary"], "validation": report, "rows": rows[:limit], "rows_not_analysed_due_to_limit": max(0, len(rows) - limit),
                     "analysis_row_limit": limit, "rows_per_request": EXTRACT_ROWS_PER_REQUEST},
                    {"note": "Nothing was stored. The rows stay in your browser tab."})


@router.post("/uploads/extract", summary="Read a few comments with the engine (sentiment, problem, return signal, quote). Nothing is stored.")
def extract(body: RowsIn):
    if not body.rows:
        raise ApiError(422, "no_rows", "Send at least one row.")
    llm = need_llm()
    rows = _clean_rows(body.rows)
    tag = csv_analysis.upload_tag(body.session)
    tracker = get_tracker()
    before = len(tracker.entries())
    recs = llm_errors(lambda: csv_analysis.extract_rows(llm, rows, tag))
    mine = [e for e in tracker.entries()[before:] if str(e.get("purpose", "")).startswith(f"upl_{tag}_")]
    return envelope({"records": recs, "usage": UsageTracker.summarise(mine)})


@router.post("/uploads/summarise", summary="Group the comments into themes and write insights and opportunities. Nothing is stored.")
def summarise(body: SummariseIn):
    llm = need_llm()
    rows = _clean_rows(body.rows)
    by_id = {r["row_id"] for r in rows}
    recs = [r for r in body.records if r.get("row_id") in by_id]
    if not recs:
        raise ApiError(422, "no_records", "Send the records returned by the extract step.")
    limit = config.MAX_ANALYSIS_REVIEWS
    result, recs = llm_errors(lambda: csv_analysis.build_result(llm, rows, rows, recs, body.session, body.filename, body.rows_in_file, limit, usage_extra=body.usage_parts))
    return envelope({"analysis": result, "reviews": recs})


@router.post("/golden/validate", summary="Check a hand-labelled CSV and return its rows. Nothing is stored.")
async def golden_validate(file: UploadFile = File(...), mapping: str | None = Form(None)):
    limit = int(settings.MAX_UPLOAD_MB * 1024 * 1024)
    raw = await file.read(limit + 1)
    if len(raw) > limit:
        raise ApiError(413, "file_too_large", f"The file is larger than {settings.MAX_UPLOAD_MB:g} MB.")
    try:
        mp = json.loads(mapping) if mapping else None
        if mp is not None and not isinstance(mp, dict):
            raise ValueError
    except ValueError:
        raise ApiError(422, "invalid_mapping", "mapping must be a JSON object like {\"text\": \"Comment\", \"human_sentiment\": \"My sentiment\"}.")
    try:
        rep = validate_golden(raw, file.filename, file.content_type, mp)
    except UploadRejected as exc:
        raise ApiError(exc.status, "golden_rejected", "The golden-set file was rejected.", {"errors": exc.errors})
    if len(rep["rows"]) > TEMP_GOLDEN_MAX_ROWS:
        raise ApiError(413, "too_many_rows", f"A temporary golden set can have at most {TEMP_GOLDEN_MAX_ROWS} labelled rows.", {"limit": TEMP_GOLDEN_MAX_ROWS})
    return envelope({"filename": file.filename, "summary": rep["summary"], "column_mapping": rep["column_mapping"], "issues": rep["issues"][:50], "rows": rep["rows"]},
                    {"columns_accepted": {f: ALIASES[f] for f in FIELDS}, "note": "Nothing was stored."})


@router.post("/golden/evaluate", summary="Run the engine on the labelled rows and compare. Nothing is stored.")
def golden_evaluate(body: GoldenIn):
    if not body.rows:
        raise ApiError(422, "no_rows", "Send at least one labelled row.")
    llm = need_llm()
    keep = ("row_id", "review_id", "review_text", "human_sentiment", "human_return", "human_theme", "rating", "source_url", "source")
    rows = [{k: (r.get(k) or "") for k in keep} for r in body.rows]
    for r in rows:
        if not r["row_id"] or not r["review_text"]:
            raise ApiError(422, "invalid_rows", "Each row needs a row_id and review_text.")
        r["human_sentiment"], r["human_return"] = r["human_sentiment"] or None, r["human_return"] or None
    tracker = get_tracker()
    before = len(tracker.entries())
    tag = "gtmp" + str(abs(hash(rows[0]["review_text"])) % 10**6)
    ev = llm_errors(lambda: gstore.evaluate_rows(llm, rows, lambda *a, **k: None, tag))
    mine = [e for e in tracker.entries()[before:] if str(e.get("purpose", "")).startswith(f"upl_{tag}_")]
    ev["usage"] = UsageTracker.summarise(mine)
    ev["model"] = llm.model
    return envelope(ev)
