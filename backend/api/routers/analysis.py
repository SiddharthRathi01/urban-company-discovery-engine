"""Read-only endpoints over the precomputed Step 2 analysis: dashboard, themes, findings, questions, behaviour, alternatives,
segments, unmet needs, opportunities, limitations, dataset metadata."""
from fastapi import APIRouter, Query

from .. import settings
from ..responses import ApiError, bad_filter, csv_list, envelope, not_found, paginate
from ..store import store

router = APIRouter()
HEAVY = ("review_ids",)


def source_meta():
    m = store.manifest()
    return {"source": "precomputed", "generated_at": m.get("generated_at"), "dataset_reviews": m["source_dataset"]["reviews"]}


def strip(obj, keys=HEAVY):
    """Copy of obj without bulky keys (used for list views; detail views keep them)."""
    if isinstance(obj, dict):
        return {k: strip(v, keys) for k, v in obj.items() if k not in keys}
    if isinstance(obj, list):
        return [strip(v, keys) for v in obj]
    return obj


def collect_evidence_ids(obj, out=None):
    out = [] if out is None else out
    if isinstance(obj, dict):
        for k, v in obj.items():
            if "evidence_ids" in k and isinstance(v, list):
                out.extend(i for i in v if isinstance(i, str))
            elif k == "evidence_id" and isinstance(v, str):
                out.append(v)
            else:
                collect_evidence_ids(v, out)
    elif isinstance(obj, list):
        for v in obj:
            collect_evidence_ids(v, out)
    return out


def detail(obj, expand=True, drop=()):
    data = strip(obj, tuple(drop)) if drop else dict(obj)
    if expand:
        ids = list(dict.fromkeys(collect_evidence_ids(obj)))
        data = dict(data)
        data["evidence_quotes"] = store.expand_evidence(ids)
    return envelope(data, source_meta())


def find(items, key, ident, kind):
    for x in items:
        if x[key].lower() == ident.lower():
            return x
    raise not_found(kind, ident)


# ------------------------------------------------------------------------------------------------ dataset / dashboard
@router.get("/meta", tags=["dataset"], summary="Dataset and analysis metadata")
def meta():
    m, o = store.manifest(), store.get("overview")
    return envelope({"api_version": settings.API_VERSION, "analysis_source": "precomputed", "manifest": m, "dataset": o["dataset"], "method": o["method"],
                     "id_scheme": m["id_scheme"], "uploads_affect_analysis": False}, source_meta())


@router.get("/overview", tags=["dashboard"], summary="Dashboard metrics")
def overview():
    o = store.get("overview")
    return envelope({k: o[k] for k in ("product", "business_metric", "dataset", "headline_metrics", "method")}, source_meta())


@router.get("/limitations", tags=["dataset"], summary="Dataset biases and method limitations")
def limitations():
    return envelope(store.get("limitations"), source_meta())


# ------------------------------------------------------------------------------------------------ themes
@router.get("/themes", tags=["themes"], summary="Theme summaries (at most five)")
def themes():
    t = store.get("themes")
    items = [strip(x) for x in t["themes"]]
    return envelope(items, {**source_meta(), "total": len(items), "counting_method": t["counting_method"], "emergence": t["emergence"],
                            "unique_reviews_with_at_least_one_theme": t["unique_reviews_with_at_least_one_theme"], "theme_overlap_matrix": t["theme_overlap_matrix"]})


@router.get("/themes/{theme_id}", tags=["themes"], summary="Theme detail with quotes, subthemes and review ids")
def theme_detail(theme_id: str, expand_evidence: bool = True):
    return detail(find(store.get("themes")["themes"], "theme_id", theme_id, "theme"), expand_evidence)


# ------------------------------------------------------------------------------------------------ findings / questions
@router.get("/findings", tags=["findings"], summary="Top three findings")
def findings():
    items = [strip(x) for x in store.get("findings")["findings"]]
    return envelope(items, {**source_meta(), "total": len(items)})


@router.get("/findings/{finding_id}", tags=["findings"], summary="Finding detail with evidence and review ids")
def finding_detail(finding_id: str, expand_evidence: bool = True):
    return detail(find(store.get("findings")["findings"], "finding_id", finding_id, "finding"), expand_evidence)


@router.get("/questions", tags=["questions"], summary="Answers to the eight discovery questions")
def questions():
    items = [strip(x, HEAVY + ("comparison",)) for x in store.get("questions")["questions"]]
    return envelope(items, {**source_meta(), "total": len(items)})


@router.get("/questions/{question_id}", tags=["questions"], summary="One discovery question with evidence")
def question_detail(question_id: str, expand_evidence: bool = True):
    return detail(find(store.get("questions")["questions"], "question_id", question_id, "question"), expand_evidence)


# ------------------------------------------------------------------------------------------------ behaviour
CLASS_SLUGS = {"return": "Return", "non-return": "Non-Return", "insufficient-evidence": "Insufficient Evidence"}


@router.get("/behaviour", tags=["behaviour"], summary="Return / non-return behaviour: distribution, patterns and comparison")
def behaviour():
    b = store.get("behaviour")
    classes = {k: strip(v, HEAVY + ("stated_records",)) for k, v in b["classes"].items()}
    return envelope({"summary": b["summary"], "definitions": b["definitions"], "basis_definitions": b["basis_definitions"], "caution": b["caution"], "distribution": b["distribution"], "patterns": b["patterns"],
                     "stated_returners_dissatisfied": b["stated_returners_dissatisfied"], "classes": classes, "comparison": b["comparison"]}, source_meta())


@router.get("/behaviour/classes/{slug}", tags=["behaviour"], summary="One behaviour class (stated cases are listed with their own words)")
def behaviour_class(slug: str, expand_evidence: bool = True):
    name = CLASS_SLUGS.get(slug.lower())
    if not name:
        raise not_found("behaviour_class", slug)
    obj = store.get("behaviour")["classes"][name]
    return detail(obj, expand_evidence, drop=HEAVY)


# ------------------------------------------------------------------------------------------------ alternatives
@router.get("/alternatives", tags=["alternatives"], summary="Alternatives customers use or consider (reported vs general separated)")
def alternatives():
    a = store.get("alternatives")
    items = [strip(x) for x in a["alternatives"]]
    return envelope(items, {**source_meta(), "total": len(items), "method": a["method"], "summary": a["summary"], "whatsapp_and_community_groups": a["whatsapp_and_community_groups"],
                            "rule_based_mentions_unvetted": a["rule_based_mentions_unvetted"], "limitations": a["limitations"]})


@router.get("/alternatives/{alternative_id}", tags=["alternatives"], summary="One alternative type with evidence and review ids")
def alternative_detail(alternative_id: str, expand_evidence: bool = True):
    return detail(find(store.get("alternatives")["alternatives"], "alternative_id", alternative_id, "alternative"), expand_evidence)


# ------------------------------------------------------------------------------------------------ segments
DIMENSIONS = ["service_category", "city", "source", "household_type", "discovery_channel", "booking_triggers"]


def dim_key(dimension):
    d = dimension.lower().replace("-", "_")
    if d not in DIMENSIONS:
        raise bad_filter("dimension", dimension, DIMENSIONS)
    return d


@router.get("/segments", tags=["segments"], summary="Segment dimensions with coverage")
def segments():
    s = store.get("segments")
    out = [{"dimension": d, "coverage": s[d].get("coverage"), "segments": len(s[d]["segments"]),
            "segment_ids": [x["segment_id"] for x in s[d]["segments"]]} for d in DIMENSIONS]
    return envelope(out, {**source_meta(), "total": len(out)})


@router.get("/segments/{dimension}", tags=["segments"], summary="Segments in one dimension with sample sizes")
def segment_list(dimension: str, min_n: int = Query(0, ge=0), page: int = Query(1, ge=1), page_size: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE)):
    d = dim_key(dimension)
    block = store.get("segments")[d]
    items = [strip(x) for x in block["segments"] if x["n" if "n" in x else "n_vetted_examples"] >= min_n]
    extra = {k: v for k, v in block.items() if k != "segments"}
    return paginate(items, page, page_size, {**source_meta(), "dimension": d, **extra})


@router.get("/segments/{dimension}/{segment_id}", tags=["segments"], summary="One segment with quotes and review ids")
def segment_detail(dimension: str, segment_id: str, expand_evidence: bool = True):
    d = dim_key(dimension)
    return detail(find(store.get("segments")[d]["segments"], "segment_id", segment_id, "segment"), expand_evidence)


# ------------------------------------------------------------------------------------------------ unmet needs / opportunities
@router.get("/unmet-needs", tags=["unmet needs"], summary="Unmet needs ranked by frequency")
def unmet_needs(min_reviews: int = Query(0, ge=0), linked_opportunity: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE)):
    u = store.get("unmet_needs")
    items = [x for x in u["unmet_needs"] if x["n_reviews"] >= min_reviews and (not linked_opportunity or x["linked_opportunity"].lower() == linked_opportunity.lower())]
    return paginate([strip(x) for x in items], page, page_size, {**source_meta(), "method": u["method"]})


@router.get("/unmet-needs/{need_id}", tags=["unmet needs"], summary="One unmet need with evidence and review ids")
def unmet_need_detail(need_id: str, expand_evidence: bool = True):
    return detail(find(store.get("unmet_needs")["unmet_needs"], "unmet_need_id", need_id, "unmet_need"), expand_evidence)


@router.get("/opportunities", tags=["opportunities"], summary="Prioritised product opportunities")
def opportunities(priority: str | None = Query(None, description="High, Medium or Low (comma separated)"), theme: str | None = None,
                  page: int = Query(1, ge=1), page_size: int = Query(settings.DEFAULT_PAGE_SIZE, ge=1, le=settings.MAX_PAGE_SIZE)):
    o = store.get("opportunities")
    items = o["opportunities"]
    pr = csv_list(priority)
    if pr:
        bad = [p for p in pr if p.title() not in ("High", "Medium", "Low")]
        if bad:
            raise bad_filter("priority", ",".join(bad), ["High", "Low", "Medium"])
        items = [x for x in items if x["priority"] in {p.title() for p in pr}]
    if theme:
        items = [x for x in items if x["evidence"]["related_theme"].lower() == theme.lower()]
    items = sorted(items, key=lambda x: x["priority_rank"])
    return paginate([strip(x) for x in items], page, page_size, {**source_meta(), "distinction": o["distinction"]})


@router.get("/opportunities/{opportunity_id}", tags=["opportunities"], summary="One opportunity with evidence and review ids")
def opportunity_detail(opportunity_id: str, expand_evidence: bool = True):
    return detail(find(store.get("opportunities")["opportunities"], "opportunity_id", opportunity_id, "opportunity"), expand_evidence)
