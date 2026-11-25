"""Endpoints that feed the website's charts and screens: trust/workflow data, sentiment breakdowns ("mood") and question search ("ask")."""
import re

from fastapi import APIRouter, Query

from ..responses import ApiError, bad_filter, envelope
from ..store import store
from .analysis import source_meta

router = APIRouter()

# ------------------------------------------------------------------------------------------------ trust / workflow
@router.get("/trust", tags=["evidence log"], summary="Workflow stages, collection funnel, validation, bias handling and golden-set status")
def trust():
    return envelope(store.get("trust"), source_meta())


# ------------------------------------------------------------------------------------------------ mood
MOOD_DIMENSIONS = ["source", "theme", "issue", "category", "city", "return_class"]
SENT_KEYS = ["Positive", "Neutral", "Negative", "Mixed", "Uncertain"]


def _labels(by):
    themes = store.get("themes")["themes"]
    if by == "theme":
        return {t["theme_id"]: t["name"] for t in themes}
    if by == "issue":
        return {x["subtheme_id"].split(".", 1)[1]: x["name"] for t in themes for x in t["subthemes"]}
    return {}


@router.get("/mood", tags=["dashboard"], summary="Sentiment mix per source, theme, issue, category, city or return class")
def mood(by: str = Query("source", description=", ".join(MOOD_DIMENSIONS)), min_n: int = Query(1, ge=1),
         sort: str = Query("negative_share", description="negative_share | n | key")):
    if by not in MOOD_DIMENSIONS:
        raise bad_filter("by", by, MOOD_DIMENSIONS)
    if sort not in ("negative_share", "n", "key"):
        raise bad_filter("sort", sort, ["key", "n", "negative_share"])
    labels, rows = _labels(by), {}
    for r in store.reviews():
        if by == "source":
            keys = [r["source"]]
        elif by == "theme":
            keys = r["themes"]
        elif by == "issue":
            keys = r["issues"]
        elif by == "category":
            keys = [r["service_category"]] if r["service_category"] else []
        elif by == "city":
            keys = [c.strip() for c in (r["city"] or "").split(";") if c.strip()]
        else:
            keys = [r["return_class"]]
        for k in keys:
            row = rows.setdefault(k, {s: 0 for s in SENT_KEYS})
            row[r["sentiment_label"]] += 1
    out = []
    for k, c in rows.items():
        n = sum(c.values())
        if n < min_n:
            continue
        out.append({"key": k, "label": labels.get(k, k), "n": n, **{s.lower(): c[s] for s in SENT_KEYS},
                    "negative_share": round(100 * (c["Negative"] + c["Mixed"]) / n, 1), "positive_share": round(100 * c["Positive"] / n, 1)})
    out.sort(key=(lambda x: x["key"]) if sort == "key" else (lambda x: -x[sort]))
    return envelope(out, {**source_meta(), "by": by, "total": len(out),
                          "note": "negative_share counts Negative and Mixed reviews. A review with several themes or issues is counted in each."})


# ------------------------------------------------------------------------------------------------ ask (keyword search, no LLM)
STOP = set("a an the and or of to in on for with is are was were be been it its this that these those i we you they he she my our your their do does did can could should "
           "would will what which who whom how why when where about from by at as not no but if so than then there any some more most very into out up down over under again also "
           "just have has had having me us them his her "
           "people say says said tell think feel feels feeling happen happens happened thing things many much make makes get gets give mention mentioned "
           "usually often generally really urban company urbanclap clap show customers service services problem problems issue issues".split())

# Plain-language expansions so a question reaches reviews that use different words for the same idea (stems). A direct word hit counts more than an expansion hit.
CONCEPTS = {
    "like": ["good", "great", "best", "love", "excellent", "satisfied", "happy", "recommend"], "love": ["like", "great", "best", "excellent", "happy"], "best": ["good", "great", "excellent", "love"],
    "good": ["great", "best", "excellent", "satisfied", "happy"], "bad": ["poor", "worst", "terrible", "pathetic", "horrible"],
    "refund": ["money", "paid", "payment", "deduct", "reimburse", "return"], "price": ["expensive", "cost", "charge", "overpriced", "rate", "fee", "costly"],
    "pricing": ["price", "expensive", "cost", "charge", "overpriced", "rate", "fee"], "expensive": ["price", "cost", "charge", "overpriced", "costly", "high"],
    "cheap": ["price", "affordable", "cost"], "competitor": ["pronto", "snabbit", "nobroker", "housejoy", "alternative", "switch", "instead", "local"],
    "alternative": ["pronto", "snabbit", "nobroker", "housejoy", "competitor", "instead", "local", "other"], "switch": ["pronto", "snabbit", "nobroker", "instead", "alternative", "another"],
    "late": ["delay", "delayed", "wait", "waiting", "hour", "punctual"], "delay": ["late", "wait", "waiting", "postpone"], "punctual": ["time", "late", "ontime"],
    "support": ["care", "executive", "helpline", "chatbot", "chat", "email", "complaint"], "help": ["support", "care", "executive"], "complaint": ["support", "care", "escalate", "grievance"],
    "cancel": ["cancelled", "reschedule", "rescheduled", "cancellation"], "add": ["request", "suggest", "option", "please", "wish", "introduce", "feature", "expand", "include"],
    "feature": ["option", "add", "request", "suggest", "should"], "stop": ["uninstall", "quit", "never", "again", "leave", "left", "switch"], "quit": ["uninstall", "stop", "never", "again"],
    "trust": ["safe", "safety", "scam", "fraud", "genuine", "verified", "reliable"], "safe": ["safety", "trust", "secure", "harass"], "scam": ["fraud", "cheat", "fake", "loot"],
    "quality": ["clean", "work", "poor", "good", "excellent", "workmanship"], "rude": ["behaviour", "behavior", "arrogant", "misbehave", "abuse", "attitude"], "behavior": ["behaviour", "polite", "rude", "attitude"],
    "behaviour": ["behavior", "polite", "rude", "attitude"], "easy": ["simple", "convenient", "smooth", "interface", "user"], "app": ["interface", "design", "bug", "login", "crash", "chatbot"],
    "ac": ["air", "conditioner", "gas", "cooling", "split", "servic"], "salon": ["beautician", "parlour", "parlor", "facial", "waxing", "hair", "makeup", "beauty"], "beautician": ["salon", "parlour", "parlor"],
    "cleaning": ["clean", "bathroom", "kitchen", "deep", "sofa"], "plumber": ["plumbing", "tap", "leak", "pipe"], "electrician": ["electric", "wiring", "switch", "fan"],
    "warranty": ["guarantee", "claim", "covered"], "booking": ["book", "booked", "slot", "schedule"], "subscription": ["plan", "membership", "package", "pass"], "package": ["subscription", "plan", "membership"],
}


def _tokens(text):
    return [w for w in re.findall(r"[a-z0-9']+", text.lower()) if (len(w) > 2 or w in ("ac", "tv")) and w not in STOP]


def _stem(w):
    for suf in ("ing", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)]
    return w


def _excerpt(r, hit):
    text = re.sub(r"\s+", " ", ((r["review_title"] + ". ") if r["review_title"] else "") + r["review_text"]).strip()
    low = text.lower()
    found = [low.find(h) for h in hit if low.find(h) >= 0]
    pos = min(found) if found else 0
    a, b = max(0, pos - 120), min(len(text), pos + 220)
    a = text.rfind(" ", 0, a) + 1 if a > 0 else 0
    b = text.find(" ", b) if text.find(" ", b) > 0 else len(text)
    return ("… " if a > 0 else "") + text[a:b] + (" …" if b < len(text) else "")


def _search(q):
    """Keyword retrieval over the approved reviews. Returns (search_words, scored) where scored items are (n_hits, has_evidence, density, review, hit_words), best first."""
    toks = list(dict.fromkeys(_stem(t) for t in _tokens(q)))
    groups = {t: ([_stem(x) for x in CONCEPTS.get(t, [])] if t in CONCEPTS else [_stem(x) for x in CONCEPTS.get(t + "s", [])]) for t in toks}
    if not toks:
        raise ApiError(422, "no_searchable_words", "Ask with a few specific words, for example 'refund delay' or 'warranty'.", {"query": q})
    evid = store.evidence_by_review()
    scored = []
    for r in store.reviews():
        text = ((r["review_title"] or "") + " " + r["review_text"]).lower()
        words = {_stem(w) for w in re.findall(r"[a-z0-9']+", text)}
        hit = [t for t in toks if t in words]
        via = [t for t in toks if t not in hit and any(x in words for x in groups[t])]
        if hit or via:
            score = len(hit) + 0.5 * len(via)
            shown = hit + [next(x for x in groups[t] if x in words) for t in via]
            scored.append((score, r["record_id"] in evid, score / (1 + len(text) / 2000), r, shown))
    scored.sort(key=lambda x: (-x[0], not x[1], -x[2], x[3]["record_id"]))
    return toks, scored


def _select(scored, n):
    """Top n matches, spread across sources where matches are equally good."""
    top, per_source = [], {}
    for item in scored:
        src = item[3]["source"]
        if per_source.get(src, 0) < max(2, n // 2):
            top.append(item); per_source[src] = per_source.get(src, 0) + 1
        if len(top) == n:
            break
    for item in scored:
        if len(top) == n:
            break
        if item not in top:
            top.append(item)
    return top


@router.get("/ask", tags=["ask"], summary="Match a question to an analysed answer and return three matching real reviews (keyword search, not an LLM)")
def ask(q: str = Query(..., min_length=3, max_length=200)):
    toks, scored = _search(q)
    best, best_score = None, 0
    for qu in store.get("questions")["questions"]:
        words = {_stem(t) for t in _tokens(qu["question"] + " " + qu["summary"])}
        score = sum(1 for t in toks if t in words)
        if score > best_score:
            best, best_score = qu, score
    top = _select(scored, 3)
    comments = [{"record_id": r["record_id"], "source": r["source"], "source_url": r["source_url"], "review_date": r["review_date"], "rating": r["rating"],
                 "sentiment_label": r["sentiment_label"], "themes": r["themes"], "excerpt": _excerpt(r, hit), "matched_words": hit} for _, _, _, r, hit in top]
    mq = {k: best[k] for k in ("question_id", "question", "summary", "evidence_strength")} if best and best_score >= 2 else None
    return envelope({"query": q, "search_words": toks, "matched_question": mq, "comments": comments, "total_matching_reviews": len(scored), "mode": "keyword_search",
                     "note": "Matched by words, not by an AI model. The answer text is the analysed answer to the closest of the eight discovery questions; the comments are real reviews containing your words."},
                    source_meta())
