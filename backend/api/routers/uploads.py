"""CSV upload foundation. Uploads are validated and stored separately from the approved dataset and are NOT analysed in Step 2."""
import logging

from fastapi import APIRouter, Depends, File, Query, UploadFile

from .. import settings
from ..locks import writes_allowed
from ..responses import ApiError, envelope, paginate
from ..store import store
from ..uploads import storage
from ..uploads.validator import UploadRejected, norm_text, validate

router = APIRouter(prefix="/uploads", tags=["uploads"])
log = logging.getLogger("discovery.uploads")
_approved = {"key": None, "texts": frozenset()}


def approved_texts():
    """Normalised texts of the approved dataset, for duplicate detection. Rebuilt if the analysis files change."""
    key = store.manifest().get("generated_at")
    if _approved["key"] != key:
        s = set()
        for r in store.reviews():
            s.add(norm_text(r["review_text"]))
            s.add(norm_text((r["review_title"] or "") + " " + r["review_text"]))
        _approved.update(key=key, texts=frozenset(s))
    return _approved["texts"]


async def read_limited(file):
    limit = int(settings.MAX_UPLOAD_MB * 1024 * 1024)
    chunks, size = [], 0
    while True:
        c = await file.read(1024 * 1024)
        if not c:
            break
        size += len(c)
        if size > limit:
            raise ApiError(413, "file_too_large", f"The file is larger than {settings.MAX_UPLOAD_MB:g} MB.", {"limit_mb": settings.MAX_UPLOAD_MB})
        chunks.append(c)
    return b"".join(chunks)


@router.post("", status_code=201, summary="Upload a CSV of reviews (validated and stored; not analysed)", dependencies=[Depends(writes_allowed)])
async def upload(file: UploadFile = File(..., description="CSV with a review-text column")):
    raw = await read_limited(file)
    try:
        report = validate(raw, file.filename, file.content_type, approved_texts())
    except UploadRejected as exc:
        raise ApiError(exc.status, "upload_rejected", "The file was rejected.", {"errors": exc.errors})
    meta = storage.create_upload(raw, file.filename, report)
    return envelope(meta, {"validation_url": f"/uploads/{meta['upload_id']}/validation", "analysed": False})


@router.get("", summary="List uploads")
def list_uploads(page: int = Query(1, ge=1), page_size: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE)):
    return paginate([] if settings.PUBLIC_MODE else storage.list_uploads(), page, page_size)   # public site: other visitors' files are never listed (and are never stored)


@router.get("/{upload_id}", summary="Upload metadata and status")
def get_upload(upload_id: str):
    return envelope(storage.get_upload(upload_id))


@router.get("/{upload_id}/validation", summary="Validation report: column mapping, row issues, duplicates")
def get_validation(upload_id: str):
    return envelope(storage.get_validation(upload_id))


@router.post("/{upload_id}/process", summary="Analyse the upload with Cloudflare Workers AI (background job; reuses saved results unless force=true)", dependencies=[Depends(writes_allowed)])
def process(upload_id: str, force: bool = False):
    job = storage.run_job(upload_id, force=force)
    return envelope(job, {"analysed": job.get("status") == "completed", "poll": f"/uploads/{upload_id}/job", "results": f"/uploads/{upload_id}/analysis"})


@router.get("/{upload_id}/analysis", summary="Saved LLM analysis of this upload: themes, sentiment, insights, opportunities, evidence, usage")
def get_analysis(upload_id: str):
    return envelope(storage.get_analysis(upload_id), {"source": "uploaded_file", "note": "AI-generated from the uploaded file only; separate from the approved Urban Company analysis."})


@router.get("/{upload_id}/analysis/reviews", summary="Per-review extractions for this upload (filter by theme or sentiment)")
def get_analysis_reviews(upload_id: str, theme: str | None = None, sentiment: str | None = None, page: int = Query(1, ge=1),
                         page_size: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE)):
    rows = storage.get_analysis_reviews(upload_id)
    if theme:
        rows = [r for r in rows if theme in r.get("theme_names", [])]
    if sentiment:
        rows = [r for r in rows if r["sentiment"].lower() == sentiment.lower()]
    return paginate(rows, page, page_size)


@router.get("/{upload_id}/job", summary="Latest processing job status and result")
def get_job(upload_id: str):
    return envelope(storage.get_job(upload_id))


@router.delete("/{upload_id}", summary="Delete an upload", dependencies=[Depends(writes_allowed)])
def delete(upload_id: str):
    storage.delete_upload(upload_id)
    return envelope({"upload_id": upload_id, "deleted": True})
