"""Cloudflare Workers AI endpoints: provider status, usage tracking, single-review analysis and grounded answers for Ask Questions."""
import json
import logging
import os
import re

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from backend import csv_analysis, prompts
from backend.data import verify_quote
from backend.llm import DailyLimitReached, LLMFailure, LLMFatal, get_tracker

from .. import llm_service, settings
from ..responses import ApiError, envelope
from ..store import store
from .analysis import source_meta
from .insights import _excerpt, _search, _select

router = APIRouter()
log = logging.getLogger("discovery.llm")


def need_llm():
    if not llm_service.is_configured():
        raise ApiError(503, "llm_not_configured", "Cloudflare Workers AI is not configured (set CLOUDFLARE_ACCOUNT_ID and CLOUDFLARE_API_TOKEN on the backend).")
    return llm_service.get_llm()


def llm_errors(fn):
    """Run fn(); map LLM failures to clear API errors. The token never appears in messages."""
    try:
        return fn()
    except DailyLimitReached as e:
        raise ApiError(429, "llm_daily_limit", "The daily Cloudflare neuron allowance is used up. Try again after 00:00 UTC.", {"detail": str(e)[:200]})
    except LLMFatal as e:
        raise ApiError(502, "llm_error", str(e)[:300])
    except LLMFailure as e:
        raise ApiError(502, "llm_failure", str(e)[:300])


@router.get("/llm/status", tags=["llm"], summary="LLM provider configuration (no secrets)")
def llm_status():
    return envelope(llm_service.status(), {"note": "Cloudflare Workers AI is the only LLM provider. The API token lives only on the backend."})


@router.get("/llm/usage", tags=["llm"], summary="Tracked LLM usage: requests, failures, input/output tokens, neurons, time")
def llm_usage(since: str | None = Query(None, description="ISO timestamp; only requests after it")):
    s = get_tracker().summary(since)
    s["neurons_today"] = get_tracker().today_neurons()
    s["daily_neuron_budget"] = llm_service.status()["daily_neuron_budget"]
    return envelope(s, {"ledger": "llm_data/usage.jsonl", "note": "Neurons are reported by Cloudflare per request; tokens are input (prompt) and output (completion)."})


class ReviewIn(BaseModel):
    text: str = Field(min_length=3, max_length=5000)
    rating: float | None = Field(None, ge=1, le=5)
    source: str | None = Field(None, max_length=60)


@router.post("/llm/analyse-review", tags=["llm"], summary="Analyse a single review with the LLM (sentiment, themes, problem, verbatim quote)")
def analyse_review(body: ReviewIn):
    llm = need_llm()
    row = {"row_id": "ROW-00001", "review_id": "ROW-00001", "review_title": "", "review_text": body.text, "platform": body.source or "", "source_url": "", "review_date": "", "rating": "" if body.rating is None else str(body.rating)}
    raw, errors = llm_errors(lambda: csv_analysis._extract_batch(llm, [row], "single"))
    if errors:
        raise ApiError(502, "llm_failure", "The model did not return a valid analysis.", {"errors": errors})
    rec = csv_analysis._record(row, raw.get(row["row_id"]))
    return envelope(rec, {"model": llm.model, "provider": "cloudflare_workers_ai", "note": "AI-generated; the evidence quote is verified to be verbatim."})


# ------------------------------------------------------------------------------------------------ grounded answers
def _validate_answer(obj):
    if not isinstance(obj, dict):
        raise ValueError("expected a JSON object")
    if obj.get("in_scope") is False:
        return obj
    if not isinstance(obj.get("answer"), str) or not obj["answer"].strip():
        raise ValueError('expected {"headline": "...", "answer": "...", "citations": [...]}')
    return obj


def _clean(text, limit):
    """One tidy line: no review ids, no stray quotes, trimmed at a word boundary if the model ran long."""
    t = re.sub(r"\s*\[(?:GP|RD|PC|CC)-\d+\]", "", " ".join(str(text or "").split())).strip()
    if len(t.split()) > limit:
        t = " ".join(t.split()[:limit]).rstrip(",;:") + "…"
    return t


# ------------------------------------------------------------------------------------------------ ready answers
# The suggested questions on the Ask page and the eight discovery questions are answered ahead of time (scripts/build_ask_ready.py), so they open
# instantly instead of waiting for the model. Typed questions still go to the model.
_READY = {"loaded": False, "data": {}}


def _norm_q(q):
    return re.sub(r"[^a-z0-9 ]+", "", " ".join(str(q).lower().split())).strip()


def _ready(kind, key):
    if os.environ.get("ASK_READY_DISABLED") == "1":
        return None
    if not _READY["loaded"]:
        path = settings.ANALYSIS_DIR / "ask_ready.json"
        try:
            _READY["data"] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        except (OSError, ValueError):
            _READY["data"] = {}
        _READY["loaded"] = True
    hit = (_READY["data"].get(kind) or {}).get(key)
    return dict(hit, cached=True, prepared=True) if hit else None


@router.get("/ask/answer", tags=["ask"], summary="Short grounded answer written by Cloudflare Workers AI from the retrieved real reviews, with verified citations")
def ask_answer(q: str = Query(..., min_length=3, max_length=200)):
    ready = _ready("answers", _norm_q(q))
    if ready:
        return envelope(dict(ready, query=q), {**source_meta(), "note": "Prepared answer: written by the AI from the reviews ahead of time; every quote was checked to be verbatim."})
    llm = need_llm()
    toks, scored = _search(q)
    if not scored:
        return envelope({"query": q, "answer": None, "headline": None, "evidence_strength": "insufficient", "citations": [], "reviews_considered": 0, "reviews_matching": 0, "reason": "no_match"}, source_meta())
    top = _select(scored, 8)
    reviews = {r["record_id"]: r for _, _, _, r, _ in top}
    blocks = [f"[{r['record_id']}] ({r['source']}, {r['sentiment_label']})\n{_excerpt(r, hit)}" for _, _, _, r, hit in top]
    user = f"Question: {q}\n\nReviews:\n\n" + "\n\n".join(blocks)
    parsed, meta = llm_errors(lambda: llm.call_json("ask_answer", prompts.ASK_SYSTEM, user, _validate_answer, max_tokens=450))
    if parsed.get("in_scope") is False:
        return envelope({"query": q, "answer": None, "headline": None, "evidence_strength": "insufficient", "citations": [], "reviews_considered": 0, "reviews_matching": 0, "reason": "out_of_scope"}, source_meta())
    citations, dropped = [], 0
    for c in parsed.get("citations") or []:
        rid, quote = (c.get("review_id") if isinstance(c, dict) else None), " ".join(str(c.get("quote") if isinstance(c, dict) else "").split())
        r = reviews.get(rid)
        full = (((r["review_title"] or "") + ". ") if r and r["review_title"] else "") + (r["review_text"] if r else "")
        if r and quote and (verify_quote(quote, full) or verify_quote(quote, r["review_text"])):
            if not any(x["review_id"] == rid and x["quote"] == quote for x in citations):
                citations.append({"review_id": rid, "quote": quote, "source": r["source"], "source_url": r["source_url"], "review_date": r["review_date"], "sentiment_label": r["sentiment_label"]})
        else:
            dropped += 1
    answer, headline = _clean(parsed["answer"], 45), _clean(parsed.get("headline"), 14)
    strength = parsed.get("evidence_strength") if parsed.get("evidence_strength") in ("strong", "moderate", "weak", "insufficient") else "weak"
    if strength == "strong" and len(citations) < 3:
        strength = "moderate"
    if not citations:
        headline, answer, strength = "Not enough evidence to answer", "The retrieved reviews do not give enough verifiable evidence to answer this confidently.", "insufficient"
    usage = meta.get("usage") or {}
    return envelope({"query": q, "headline": headline or None, "answer": answer, "evidence_strength": strength, "citations": citations[:3], "reviews_considered": len(top), "reviews_matching": len(scored),
                     "citations_dropped_unverifiable": dropped, "model": meta.get("model"), "provider": "cloudflare_workers_ai", "cached": bool(meta.get("cached")),
                     "usage": {"input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"), "neurons": 0.0 if meta.get("cached") else meta.get("neurons"),
                               "seconds": None if meta.get("cached") else meta.get("seconds")}},
                    {**source_meta(), "note": "AI-written from the reviews listed in citations; every quote is checked to be verbatim. Retrieval is keyword-based."})


_NUM = re.compile(r"\d[\d,]*(?:\.\d+)?")


@router.get("/questions/{question_id}/brief", tags=["ask"], summary="Two-sentence brief of an analysed discovery question, written by Cloudflare Workers AI; written without numbers; the full analysed answer carries them")
def question_brief(question_id: str):
    q = next((x for x in store.get("questions")["questions"] if x["question_id"] == question_id), None)
    if not q:
        raise ApiError(404, "question_not_found", f"No discovery question {question_id}.", {"question_id": question_id})
    ready = _ready("briefs", question_id)
    if ready:
        return envelope(ready, {**source_meta(), "note": "Prepared summary written by the AI ahead of time; numbers stay in the full analysed answer."})
    llm = need_llm()
    source_text = q["summary"]
    quotes = store.expand_evidence(q.get("evidence_ids") or [])[:5]
    user = f"Question: {q['question']}\n\nAnalysed answer:\n{source_text}\n\nQuotes:\n" + "\n".join(f"- {e['quote']}" for e in quotes)
    allowed = set()  # the brief carries no numbers; the full analysed answer shows them

    def validate(obj):
        if not isinstance(obj, dict) or not isinstance(obj.get("answer"), str) or not obj["answer"].strip():
            raise ValueError('expected {"headline": "...", "answer": "..."}')
        bad = [n for n in _NUM.findall(str(obj.get("headline", "")) + " " + obj["answer"]) if n.rstrip(".,") not in allowed]
        if bad:
            raise ValueError(f"write no numbers: {bad}")
        return obj

    parsed, meta = llm_errors(lambda: llm.call_json("question_brief", prompts.PRESET_BRIEF_SYSTEM, user, validate, max_tokens=500))
    return envelope({"question_id": question_id, "headline": _clean(parsed.get("headline"), 16), "answer": _clean(parsed["answer"], 50), "cached": bool(meta.get("cached")), "model": meta.get("model")},
                    {**source_meta(), "note": "Short brief written by AI from the analysed answer; numbers stay in the full analysed answer."})
