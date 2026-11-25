"""Evidence and original-review endpoints (traceability): every quote and review links back to its source, URL and date."""
from fastapi import APIRouter, Query

from .. import settings
from ..responses import bad_filter, csv_list, envelope, not_found, paginate
from ..store import store
from .analysis import source_meta

router = APIRouter()
SOURCES = {"Google Play Store", "Reddit", "PissedConsumer", "ConsumerComplaints.in"}
SENTIMENTS = {"Positive", "Negative", "Neutral", "Mixed", "Uncertain"}
THEMES = {"T1", "T2", "T3", "T4", "T5"}
RETURN_CLASSES = {"Return", "Non-Return", "Insufficient Evidence"}
RETURN_BASES = {"Stated", "Signalled", "Inferred", "None"}
CONFIDENCES = {"High", "Medium", "Low"}
SORTS = {"record_id", "review_date", "rating"}


def check_set(name, values, allowed, fold=True):
    """Validate comma-separated filter values against an allowed set (case-insensitive); return canonical values."""
    if values is None:
        return None
    canon = {a.lower(): a for a in allowed}
    out = []
    for v in values:
        if v.lower() not in canon:
            raise bad_filter(name, v, allowed)
        out.append(canon[v.lower()])
    return set(out)


def preview(r, include_text):
    d = {k: v for k, v in r.items() if k != "review_text"}
    t = r["review_text"]
    d["review_text"] = t if include_text else (t if len(t) <= 300 else t[:300].rsplit(" ", 1)[0] + " …")
    d["review_text_truncated"] = (not include_text) and len(t) > 300
    return d


@router.get("/reviews", tags=["reviews"], summary="Original reviews (filter, search, sort, paginate)")
def reviews(source: str | None = Query(None, description="comma separated"), sentiment: str | None = None, theme: str | None = None, return_class: str | None = None, return_basis: str | None = None, return_confidence: str | None = None,
            category: str | None = None, city: str | None = None, issue: str | None = None, unmet_need: str | None = None, alternative: str | None = None, opportunity: str | None = None,
            rating_min: float | None = Query(None, ge=1, le=5), rating_max: float | None = Query(None, ge=1, le=5), date_from: str | None = None, date_to: str | None = None,
            q: str | None = Query(None, min_length=2, max_length=100), sort: str = "record_id", order: str = "asc", include_text: bool = False,
            page: int = Query(1, ge=1), page_size: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE)):
    src, sen = check_set("source", csv_list(source), SOURCES), check_set("sentiment", csv_list(sentiment), SENTIMENTS)
    th, rc = check_set("theme", csv_list(theme), THEMES), check_set("return_class", csv_list(return_class), RETURN_CLASSES)
    rb, rcf = check_set("return_basis", csv_list(return_basis), RETURN_BASES), check_set("return_confidence", csv_list(return_confidence), CONFIDENCES)
    if sort not in SORTS:
        raise bad_filter("sort", sort, SORTS)
    if order not in ("asc", "desc"):
        raise bad_filter("order", order, ["asc", "desc"])
    if rating_min is not None and rating_max is not None and rating_min > rating_max:
        raise bad_filter("rating_min", rating_min)
    for nm, v in (("date_from", date_from), ("date_to", date_to)):
        if v and (len(v) != 10 or v[4] != "-" or v[7] != "-"):
            raise bad_filter(nm, v, ["YYYY-MM-DD"])
    items = store.reviews()
    opp_ids = None
    if opportunity:
        opps = store.get("opportunities")["opportunities"]
        match = next((o for o in opps if o["opportunity_id"].lower() == opportunity.lower()), None)
        if not match:
            raise bad_filter("opportunity", opportunity, [o["opportunity_id"] for o in opps])
        opp_ids = set(match["evidence"]["review_ids"])
    ql = q.lower() if q else None
    def ok(r):
        if src and r["source"] not in src: return False
        if sen and r["sentiment_label"] not in sen: return False
        if th and not (th & set(r["themes"])): return False
        if rc and r["return_class"] not in rc: return False
        if rb and r["return_basis"] not in rb: return False
        if rcf and r["return_confidence"] not in rcf: return False
        if category and (r["service_category"] or "").lower() != category.lower(): return False
        if city and city.lower() not in (r["city"] or "").lower(): return False
        if issue and issue not in r["issues"]: return False
        if unmet_need and unmet_need.upper() not in r["unmet_needs"]: return False
        if alternative and alternative.upper() not in r["alternatives"]: return False
        if opp_ids is not None and r["record_id"] not in opp_ids: return False
        if rating_min is not None and (r["rating"] is None or float(r["rating"]) < rating_min): return False
        if rating_max is not None and (r["rating"] is None or float(r["rating"]) > rating_max): return False
        if date_from and (not r["review_date"] or r["review_date"] < date_from): return False
        if date_to and (not r["review_date"] or r["review_date"] > date_to): return False
        if ql and ql not in ((r["review_title"] or "") + " " + r["review_text"]).lower(): return False
        return True
    rows = [r for r in items if ok(r)]
    def key(r):
        v = r[sort]
        return (float(v) if sort == "rating" else v, r["record_id"])
    present = sorted([r for r in rows if r[sort] is not None], key=key, reverse=(order == "desc"))
    rows = present + [r for r in rows if r[sort] is None]          # reviews without the sort field always come last
    return paginate([preview(r, include_text) for r in rows], page, page_size, {**source_meta(), "filters_applied": {k: v for k, v in dict(
        source=source, sentiment=sentiment, theme=theme, return_class=return_class, return_basis=return_basis, return_confidence=return_confidence, category=category, city=city, issue=issue, unmet_need=unmet_need,
        alternative=alternative, opportunity=opportunity, rating_min=rating_min, rating_max=rating_max, date_from=date_from, date_to=date_to, q=q).items() if v is not None}, "sort": sort, "order": order})


@router.get("/reviews/{record_id}", tags=["reviews"], summary="One original review with every quote taken from it")
def review_detail(record_id: str):
    r = store.review_by_id().get(record_id) or store.review_by_id().get(record_id.upper())
    if not r:
        raise not_found("review", record_id)
    ev = store.expand_evidence(store.evidence_by_review().get(r["record_id"], []))
    opps = [{"opportunity_id": o["opportunity_id"], "title": o["title"], "priority": o["priority"], "priority_rank": o["priority_rank"]}
            for o in store.get("opportunities")["opportunities"] if r["record_id"] in set(o["evidence"]["review_ids"])]
    return envelope({**r, "opportunities": opps, "evidence": [{k: v for k, v in e.items() if k != "review_text"} for e in ev]}, source_meta())


@router.get("/evidence", tags=["evidence"], summary="Evidence quotes with review id, text, source, URL and date")
def evidence(theme: str | None = None, supports: str | None = Query(None, description="prefix, e.g. 'opportunity:O1', 'finding:F1', 'theme:T3', 'question:Q4'"), source: str | None = None,
             sentiment: str | None = None, review_id: str | None = None, q: str | None = Query(None, min_length=2, max_length=100), include_review_text: bool = False,
             page: int = Query(1, ge=1), page_size: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE)):
    src, sen, th = check_set("source", csv_list(source), SOURCES), check_set("sentiment", csv_list(sentiment), SENTIMENTS), check_set("theme", csv_list(theme), THEMES)
    ql = q.lower() if q else None
    rows = []
    for e in store.evidence():
        if src and e["source"] not in src: continue
        if sen and e["sentiment_label"] not in sen: continue
        if th and not (th & set(e.get("themes", []))): continue
        if review_id and e["review_id"].lower() != review_id.lower(): continue
        if supports and not any(s.lower().startswith(supports.lower()) for s in e["supports"]): continue
        if ql and ql not in e["quote"].lower(): continue
        rows.append(e if include_review_text else {k: v for k, v in e.items() if k != "review_text"})
    return paginate(rows, page, page_size, {**source_meta()})


@router.get("/evidence/{evidence_id}", tags=["evidence"], summary="One evidence item with the full original review text")
def evidence_detail(evidence_id: str):
    e = store.evidence_by_id().get(evidence_id.upper())
    if not e:
        raise not_found("evidence", evidence_id)
    return envelope(e, source_meta())
