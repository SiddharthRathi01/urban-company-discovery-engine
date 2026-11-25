"""Golden set: upload a hand-labelled CSV, run the engine on it, and see where engine and human agree."""
import json

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile

from .. import settings
from ..locks import writes_allowed
from ..golden import store
from ..golden.validator import ALIASES, FIELDS, propose_mapping
from ..responses import ApiError, envelope, paginate
from ..uploads.validator import UploadRejected

router = APIRouter(prefix="/golden", tags=["golden set"])


@router.get("", summary="List golden sets (newest first); the primary one is shown on the AI Evidence Log")
def list_sets():
    sets = store.list_sets()
    return envelope(sets, {"total": len(sets), "primary": next((s["golden_id"] for s in sets if s.get("primary")), None),
                           "columns_accepted": {f: ALIASES[f] for f in FIELDS}, "max_rows": settings.MAX_GOLDEN_ROWS})


@router.post("", status_code=201, summary="Upload a golden-set CSV (review text + your own labels)", dependencies=[Depends(writes_allowed)])
async def upload(file: UploadFile = File(...), mapping: str | None = Form(None, description="JSON: {field: column name}"), name: str | None = Form(None)):
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
        meta = store.create(raw, file.filename, file.content_type, mp, name)
    except UploadRejected as exc:
        raise ApiError(exc.status, "golden_rejected", "The golden-set file was rejected.", {"errors": exc.errors})
    return envelope(meta, {"next": f"/golden/{meta['golden_id']}/evaluate"})


@router.get("/{golden_id}", summary="One golden set: labels summary, job status and agreement summary")
def get_one(golden_id: str):
    return envelope(store.get(golden_id))


@router.post("/{golden_id}/evaluate", summary="Run the engine on the golden set (background job; reuses a saved evaluation unless force=true)", dependencies=[Depends(writes_allowed)])
def evaluate(golden_id: str, force: bool = False):
    return envelope(store.run(golden_id, force), {"poll": f"/golden/{golden_id}/job", "results": f"/golden/{golden_id}/evaluation"})


@router.get("/{golden_id}/job", summary="Evaluation job status and progress")
def job(golden_id: str):
    return envelope(store.get(golden_id)["job"])


@router.get("/{golden_id}/evaluation", summary="Agreement metrics (sentiment and Return/Non-Return) and per-row engine output")
def evaluation(golden_id: str):
    ev = store.evaluation(golden_id)
    return envelope({k: v for k, v in ev.items() if k != "rows"}, {"rows_url": f"/golden/{golden_id}/rows"})


@router.get("/{golden_id}/rows", summary="Per-row comparison of human labels and engine output")
def rows(golden_id: str, match: str | None = Query(None, description="Full match | Partial match | Non-match | Not analysed"), page: int = Query(1, ge=1),
         page_size: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE)):
    items = store.evaluation(golden_id)["rows"]
    if match:
        items = [r for r in items if r["match_status"].lower() == match.lower()]
    return paginate(items, page, page_size)


@router.post("/{golden_id}/primary", summary="Show this golden set on the AI Evidence Log", dependencies=[Depends(writes_allowed)])
def primary(golden_id: str):
    return envelope(store.set_primary(golden_id))


@router.delete("/{golden_id}", summary="Delete a golden set", dependencies=[Depends(writes_allowed)])
def delete(golden_id: str):
    store.delete(golden_id)
    return envelope({"golden_id": golden_id, "deleted": True})


@router.post("/preview-mapping", summary="Suggest a column mapping from a header row")
def preview(header: str = Form(..., description="JSON list of column names")):
    try:
        h = json.loads(header)
        assert isinstance(h, list)
    except (ValueError, AssertionError):
        raise ApiError(422, "invalid_header", "header must be a JSON list of column names.")
    return envelope(propose_mapping([str(x) for x in h]))
