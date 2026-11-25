"""CSV Upload -> LLM analysis -> structured insights, using Cloudflare Workers AI.

Three LLM phases, with everything countable done in code (the model never produces a statistic):
  1. extraction   per review, in batches: sentiment, 1-2 theme labels, problem, positive, one verbatim quote
  2. consolidation  the model groups the theme labels into at most five themes; counts/percentages/sentiment are computed here
  3. insights     the model writes insights and product opportunities from computed stats + verbatim quotes

Evidence rules: original review ids and source URLs are preserved; every quote shown is verified to be verbatim in its review (a model quote that
is not verbatim is replaced by the start of the review itself); cited quotes that cannot be verified are dropped; model text containing digits is dropped.
Results are saved to disk so the dashboard never needs to call the LLM again."""
import json
import re
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from . import config, prompts, return_class as RCL
from .data import verify_quote
from .llm import DailyLimitReached, IncompleteResponse, LLMFailure, ServiceUnavailable, UsageTracker, get_tracker

SENTIMENTS = ["Positive", "Negative", "Mixed", "Neutral", "Unclear"]
SCHEMA_VERSION = "1.0"


def _n(s):
    return re.sub(r"\s+", " ", s or "").strip()


def _label(s):
    return re.sub(r"\s+", " ", re.sub(r"^[\W_]+|[\W_]+$", "", (s or "").lower())).strip()


def _full_text(r):
    return _n(((r.get("review_title") or "") + ". " if r.get("review_title") else "") + (r.get("review_text") or ""))


def _block(r):
    text = _full_text(r)
    if len(text) > config.MAX_REVIEW_CHARS:
        text = text[:config.MAX_REVIEW_CHARS] + " [text truncated]"
    meta = " | ".join(x for x in [f"rating: {r['rating']}" if r.get("rating") else "", f"source: {r['platform']}" if r.get("platform") else ""] if x)
    return f"[{r['row_id']}]{(' ' + meta) if meta else ''}\nTEXT: {text}"


def _validate_batch(ids):
    want = set(ids)

    def v(obj):
        res = obj.get("results") if isinstance(obj, dict) else None
        if not isinstance(res, list):
            raise ValueError('expected {"results": [...]}')
        out = {}
        for x in res:
            rid = re.sub(r"[\[\]\s]", "", str(x.get("review_id") or "")) if isinstance(x, dict) else None   # the model sometimes echoes "[ROW-00001]"
            if rid in want and rid not in out:
                out[rid] = x
        if not out and len(res) == len(ids) and all(isinstance(x, dict) for x in res):   # ids unusable but one result per review in order
            out = dict(zip(ids, res))
        if not out:
            raise ValueError("no result matched the review ids; return one result per review using the id in square brackets")
        return out          # partial results are accepted; _extract_batch re-asks only for the missing reviews
    return v


def _extract_batch(llm, batch, tag, depth=0):
    """Returns ({row_id: raw_result}, {row_id: error}). Splits a batch that comes back truncated or incomplete."""
    ids = [r["row_id"] for r in batch]
    user = f"Extract structured evidence for the following {len(batch)} reviews.\n\n" + "\n\n".join(_block(r) for r in batch)
    try:
        res, _ = llm.call_json(f"upl_{tag}_extract", prompts.UPLOAD_EXTRACT_SYSTEM, user, _validate_batch(ids), max_tokens=min(6000, 260 * len(batch) + 600))
        missing = [r for r in batch if r["row_id"] not in res]
        if missing and depth < 2:                                   # the model skipped some reviews: ask again for just those
            more, errs = _extract_batch(llm, missing, tag, depth + 1)
            return {**res, **more}, errs
        return res, {r["row_id"]: "the model returned no result for this review" for r in missing}
    except ServiceUnavailable as e:
        return {}, {i: f"{type(e).__name__}: {str(e)[:120]}" for i in ids}
    except (IncompleteResponse, LLMFailure) as e:
        if len(batch) > 1 and depth < 2:
            mid = len(batch) // 2
            a, ea = _extract_batch(llm, batch[:mid], tag, depth + 1)
            b, eb = _extract_batch(llm, batch[mid:], tag, depth + 1)
            return {**a, **b}, {**ea, **eb}
        return {}, {i: f"{type(e).__name__}: {str(e)[:120]}" for i in ids}


def _evidence_quote(raw_quote, row):
    """A verbatim quote for this review: the model's quote if it is verbatim, otherwise the start of the review itself."""
    text = _full_text(row)
    q = _n(raw_quote)
    if q and len(q) <= 260 and verify_quote(q, text):
        return q, "model_quote"
    cut = text[:200]
    if len(text) > 200:
        cut = cut.rsplit(" ", 1)[0] + " …"
    return cut, "review_start"


def _record(row, raw, error=None):
    base = {"row_id": row["row_id"], "review_id": row.get("review_id") or row["row_id"], "source": row.get("platform") or None, "source_url": row.get("source_url") or None,
            "review_date": row.get("review_date") or None, "rating": row.get("rating") or None}
    if raw is None:
        return {**base, "extraction_status": "failed", "error": error, "sentiment": "Unclear", "themes": [], "problem": None, "positive": None, "is_customer_experience": None,
                "evidence_quote": _evidence_quote(None, row)[0], "evidence_source": "review_start",
                "return_signal": "none", "return_class": "Insufficient Evidence", "return_basis": "None", "return_confidence": "Low", "return_reason": "not analysed"}
    s = str(raw.get("sentiment") or "").strip().title()
    themes = []
    for t in (raw.get("themes") or [])[:2]:
        lab = _label(t if isinstance(t, str) else "")
        if lab and lab not in themes:
            themes.append(lab[:60])
    quote, qsrc = _evidence_quote(raw.get("key_quote"), row)
    sent = s if s in SENTIMENTS else "Unclear"
    sig = str(raw.get("return_signal") or "none").strip().lower()
    sig = sig if sig in RCL.SIGNALS else "none"
    cls, basis, conf, reason = RCL.classify(sig, sent, row.get("rating"))
    return {**base, "extraction_status": "ok", "sentiment": sent, "themes": themes, "problem": _n(raw.get("problem")) or None,
            "positive": _n(raw.get("positive")) or None, "is_customer_experience": raw.get("is_customer_experience") is not False, "evidence_quote": quote, "evidence_source": qsrc,
            "return_signal": sig, "return_class": cls, "return_basis": basis, "return_confidence": conf, "return_reason": reason}


# ------------------------------------------------------------------------------------------------ consolidation
def _consolidate(llm, labels, tag):
    """labels: Counter label->n. Returns (themes [{name, description, labels}], notes). Every label ends up in exactly one theme."""
    top = labels.most_common(200)
    listed = [l for l, _ in top]
    if not listed:
        return [], {"themes_from_model": 0, "labels_unassigned": 0}
    user = "Theme labels (label | number of reviews):\n" + "\n".join(f"{l} | {n}" for l, n in top)
    max_themes = min(5, len(listed))

    def v(obj):
        ts = obj.get("themes") if isinstance(obj, dict) else None
        if not isinstance(ts, list) or not ts or len(ts) > 5:
            raise ValueError('expected {"themes": [1 to 5 items]}')
        seen, out = set(), []
        for t in ts:
            labs = [x for x in (t.get("labels") or []) if x in listed and x not in seen]
            seen.update(labs)
            if labs and _n(t.get("name")):
                out.append({"name": _n(t["name"])[:80], "description": _n(t.get("description"))[:300], "labels": labs})
        if not out:
            raise ValueError("no valid themes")
        return out

    themes, _ = llm.call_json(f"upl_{tag}_themes", prompts.UPLOAD_THEME_SYSTEM + f"\nCreate at most {max_themes} themes.", user, v, max_tokens=2500)
    assigned = {l for t in themes for l in t["labels"]}
    rest = [l for l in labels if l not in assigned]
    if rest:                                    # labels the model skipped (or beyond the top 200): kept honestly as 'Other'
        themes.append({"name": "Other", "description": "Labels that were not grouped into a main theme.", "labels": rest})
    return themes, {"themes_from_model": len(themes) - (1 if rest else 0), "labels_unassigned": len(rest)}


# ------------------------------------------------------------------------------------------------ insights
_DIGIT = re.compile(r"\d")


class _Evidence:
    def __init__(self, rows_by_uid, recs_by_uid):
        self.rows, self.recs, self.items, self._idx = rows_by_uid, recs_by_uid, [], {}

    def add(self, uid, quote, themes=None):
        key = (uid, quote)
        if key not in self._idx:
            r = self.recs[uid]
            self._idx[key] = f"EVU{len(self.items) + 1:03d}"
            self.items.append({"evidence_id": self._idx[key], "review_id": r["review_id"], "row_id": uid, "quote": quote, "source": r["source"], "source_url": r["source_url"],
                               "review_date": r["review_date"], "rating": r["rating"], "sentiment": r["sentiment"], "themes": themes if themes is not None else r["themes"]})
        return self._idx[key]

    def cite(self, cites):
        """Verified evidence ids from model citations; unverifiable ones are counted and dropped."""
        ids, dropped = [], 0
        for c in cites or []:
            uid, q = (c.get("review_id") if isinstance(c, dict) else None), _n(c.get("quote") if isinstance(c, dict) else "")
            if uid in self.rows and q and verify_quote(q, _full_text(self.rows[uid])):
                e = self.add(uid, q)
                if e not in ids:
                    ids.append(e)
            else:
                dropped += 1
        return ids, dropped


def _pick_evidence(recs, k=4):
    """Deterministic, balanced picks: negative/mixed first, then positive; prefer real model quotes of useful length."""
    def score(r):
        return (r["evidence_source"] != "model_quote", abs(len(r["evidence_quote"]) - 140), r["row_id"])
    neg = sorted([r for r in recs if r["sentiment"] in ("Negative", "Mixed")], key=score)
    pos = sorted([r for r in recs if r["sentiment"] == "Positive"], key=score)
    oth = sorted([r for r in recs if r["sentiment"] not in ("Negative", "Mixed", "Positive")], key=score)
    out = neg[:max(1, k - 2)] + pos[:2]
    out += [r for r in neg[max(1, k - 2):] + pos[2:] + oth if r not in out][:k - len(out)]
    return out[:k]


def _insight_package(themes, sentiment, n):
    lines = [f"DATASET: {n} reviews analysed. Sentiment counts: " + ", ".join(f"{k} {v}" for k, v in sentiment.items() if v)]
    for t in themes:
        lines.append(f"\nTHEME \"{t['name']}\" ({t['description']}): {t['review_count']} reviews; sentiment " + ", ".join(f"{k} {v}" for k, v in t["sentiment"].items() if v))
        for e in t["_evidence_recs"]:
            lines.append(f"  QUOTE [{e['row_id']}] ({e['sentiment']}): \"{e['evidence_quote']}\"")
    return "\n".join(lines)


def _validate_insights(obj):
    if not isinstance(obj, dict) or not isinstance(obj.get("insights"), list) or not obj["insights"]:
        raise ValueError('expected {"insights": [...], "opportunities": [...]}')
    return obj


# ------------------------------------------------------------------------------------------------ main entry
def merge_usage(parts):
    """Add up UsageTracker.summarise() dicts (used when one analysis is run as several separate requests)."""
    out = {"requests": 0, "successful_requests": 0, "failed_requests": 0, "input_tokens": 0, "output_tokens": 0, "neurons": 0.0, "seconds": 0.0, "by_purpose": {}}
    for u in parts or []:
        for k in ("requests", "successful_requests", "failed_requests", "input_tokens", "output_tokens", "neurons", "seconds"):
            out[k] += (u or {}).get(k) or 0
        for name, p in ((u or {}).get("by_purpose") or {}).items():
            q = out["by_purpose"].setdefault(name, {"requests": 0, "failed": 0, "input_tokens": 0, "output_tokens": 0, "neurons": 0.0, "seconds": 0.0})
            for k in q:
                q[k] += p.get(k) or 0
    out["neurons"], out["seconds"] = round(out["neurons"], 3), round(out["seconds"], 2)
    return out


def upload_tag(upload_id):
    return re.sub(r"[^A-Za-z0-9]", "", upload_id)[-8:] or "upload"


def extract_rows(llm, work, tag, progress=None):
    """Step 1: read every row (batches of UPLOAD_BATCH_SIZE, several in parallel). Returns one record per row."""
    progress = progress or (lambda phase, done, total, msg="": None)
    bs = max(1, config.UPLOAD_BATCH_SIZE)
    batches = [work[i:i + bs] for i in range(0, len(work), bs)]
    raw, errors, done = {}, {}, 0
    progress("extraction", 0, len(batches), f"Reading {len(work)} reviews in {len(batches)} batches")
    with ThreadPoolExecutor(max_workers=max(1, config.CONCURRENCY)) as ex:
        futs = [ex.submit(_extract_batch, llm, b, tag) for b in batches]
        try:
            for f in as_completed(futs):
                res, err = f.result()
                raw.update(res); errors.update(err); done += 1
                progress("extraction", done, len(batches), f"{len(raw)} of {len(work)} reviews read")
        except DailyLimitReached:
            for f in futs:
                f.cancel()
            raise
    return [_record(r, raw.get(r["row_id"]), errors.get(r["row_id"], "no result returned")) for r in work]


def analyse(llm, rows, out_dir, upload_id, source_filename=None, rows_in_file=None, progress=None, limit=None, tracker=None):
    """rows: validated upload rows (dicts with row_id, review_id, review_text, platform, source_url, ...). Writes out_dir/analysis.json and reviews.json."""
    progress = progress or (lambda phase, done, total, msg="": None)
    tracker = tracker or get_tracker()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    limit = limit or config.MAX_ANALYSIS_REVIEWS
    work = rows[:limit]
    tag = upload_tag(upload_id)
    ledger_before = len(tracker.entries())
    t_start = time.time()
    recs = extract_rows(llm, work, tag, progress)
    result, recs = build_result(llm, rows, work, recs, upload_id, source_filename, rows_in_file, limit, progress, tracker, ledger_before, t_start)
    (out_dir / "analysis.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    (out_dir / "reviews.json").write_text(json.dumps({"schema_version": SCHEMA_VERSION, "upload_id": upload_id, "reviews": recs}, ensure_ascii=False, indent=1), encoding="utf-8")
    progress("done", 1, 1, "Analysis saved")
    return result


def build_result(llm, rows, work, recs, upload_id, source_filename, rows_in_file, limit, progress=None, tracker=None, ledger_before=None, t_start=None, usage_extra=None):
    """Steps 2 and 3: group the labels into themes and write insights and opportunities; counts are computed here. Nothing is written to disk.
    usage_extra: UsageTracker summaries of earlier, separate requests (the extraction step) to add to this call's own usage."""
    progress = progress or (lambda phase, done, total, msg="": None)
    tracker = tracker or get_tracker()
    t_start = t_start or time.time()
    tag = upload_tag(upload_id)
    ledger_before = len(tracker.entries()) if ledger_before is None else ledger_before
    by_uid = {r["row_id"]: r for r in work}
    by_rec = {r["row_id"]: r for r in recs}
    ok = [r for r in recs if r["extraction_status"] == "ok" and r["is_customer_experience"]]
    if not ok:
        raise LLMFailure("No review could be analysed (every extraction failed or none is a customer experience).")

    # ---- 2. consolidation (model groups labels; code counts)
    progress("themes", 0, 1, "Grouping recurring topics into themes")
    labels = Counter(l for r in ok for l in r["themes"])
    theme_defs, cnotes = _consolidate(llm, labels, tag)
    label_to_theme = {l: t["name"] for t in theme_defs for l in t["labels"]}
    for r in recs:
        r["theme_names"] = sorted({label_to_theme[l] for l in r["themes"] if l in label_to_theme})
    themes = []
    for i, t in enumerate(theme_defs, 1):
        members = [r for r in ok if t["name"] in r["theme_names"]]
        if not members:
            continue
        sent = Counter(r["sentiment"] for r in members)
        themes.append({"theme_id": f"U{i}", "name": t["name"], "description": t["description"], "review_count": len(members), "pct_of_analysed": round(100 * len(members) / len(ok), 1),
                       "sentiment": {s: sent.get(s, 0) for s in SENTIMENTS if sent.get(s)}, "labels": sorted(t["labels"], key=lambda l: -labels[l])[:12],
                       "sources": dict(Counter(r["source"] or "not stated" for r in members)), "review_ids": [r["review_id"] for r in members], "_evidence_recs": _pick_evidence(members)})
    themes.sort(key=lambda t: -t["review_count"])
    for i, t in enumerate(themes, 1):
        t["rank"] = i

    # ---- 3. insights + opportunities
    progress("insights", 0, 1, "Writing insights and opportunities from the evidence")
    sentiment = Counter(r["sentiment"] for r in ok)
    package = _insight_package(themes, {s: sentiment.get(s, 0) for s in SENTIMENTS}, len(ok))
    insight_raw, _ = llm.call_json(f"upl_{tag}_insights", prompts.UPLOAD_INSIGHT_SYSTEM, package, _validate_insights, max_tokens=4000)
    ev = _Evidence(by_uid, by_rec)
    notes = {"citations_dropped_unverifiable": 0, "items_dropped_for_digits": 0, "items_dropped_without_evidence": 0}
    insights, opportunities = [], []
    for x in insight_raw.get("insights", [])[:6]:
        text = " ".join(str(x.get(k) or "") for k in ("title", "insight"))
        if _DIGIT.search(text):
            notes["items_dropped_for_digits"] += 1; continue
        ids, dropped = ev.cite(x.get("supporting"))
        notes["citations_dropped_unverifiable"] += dropped
        if not ids:
            notes["items_dropped_without_evidence"] += 1; continue
        insights.append({"insight_id": f"I{len(insights) + 1}", "title": _n(x.get("title")), "insight": _n(x.get("insight")), "evidence_ids": ids})
    theme_names = {t["name"] for t in themes}
    for x in (insight_raw.get("opportunities") or [])[:5]:
        text = " ".join(str(x.get(k) or "") for k in ("name", "customer_problem", "why_it_matters", "suggested_improvement_hypothesis", "repeat_booking_link_hypothesis"))
        if _DIGIT.search(text):
            notes["items_dropped_for_digits"] += 1; continue
        ids, dropped = ev.cite(x.get("supporting"))
        notes["citations_dropped_unverifiable"] += dropped
        if not ids:
            notes["items_dropped_without_evidence"] += 1; continue
        try:
            impact = min(5, max(1, int(x.get("impact_score_1_to_5"))))
        except (TypeError, ValueError):
            impact = None
        opportunities.append({"opportunity_id": f"UO{len(opportunities) + 1}", "name": _n(x.get("name")), "customer_problem": _n(x.get("customer_problem")),
                              "related_themes": [t for t in (x.get("related_themes") or []) if t in theme_names], "why_it_matters": _n(x.get("why_it_matters")),
                              "suggested_improvement_hypothesis": _n(x.get("suggested_improvement_hypothesis")), "repeat_booking_link_hypothesis": _n(x.get("repeat_booking_link_hypothesis")),
                              "impact_score_1_to_5_analyst_judgement": impact, "evidence_ids": ids})
    # theme evidence (verbatim excerpts)
    for t in themes:
        t["evidence_ids"] = [ev.add(e["row_id"], e["evidence_quote"], themes=[t["name"]]) for e in t.pop("_evidence_recs")]

    def experience(kind):
        mem = [r for r in ok if r["sentiment"] == kind]
        c = Counter(n for r in mem for n in r["theme_names"])
        phrases = Counter(_label(r["problem" if kind == "Negative" else "positive"]) for r in mem if r["problem" if kind == "Negative" else "positive"])
        return {"review_count": len(mem), "pct_of_analysed": round(100 * len(mem) / len(ok), 1), "top_themes": [{"theme": k, "review_count": v} for k, v in c.most_common(5)],
                "most_repeated_phrases": [{"phrase": k, "review_count": v} for k, v in phrases.most_common(6) if v > 1],
                "evidence_ids": [ev.add(r["row_id"], r["evidence_quote"]) for r in _pick_evidence(mem, 3)], "summary": _n(insight_raw.get(f"{'positive' if kind == 'Positive' else 'negative'}_experiences_summary")) if not _DIGIT.search(str(insight_raw.get(f"{'positive' if kind == 'Positive' else 'negative'}_experiences_summary") or "")) else None}

    pos_exp, neg_exp = experience("Positive"), experience("Negative")
    mixed = sum(1 for r in ok if r["sentiment"] == "Mixed")

    # ---- usage and result
    mine = [e for e in tracker.entries()[ledger_before:] if str(e.get("purpose", "")).startswith(f"upl_{tag}_")]
    usage = merge_usage([UsageTracker.summarise(mine)] + list(usage_extra or []))
    usage.update({"cache_hits": llm.stats.get("cache_hits"), "processing_seconds": round(time.time() - t_start, 1), "model": llm.model, "provider": "cloudflare_workers_ai"})
    result = {
        "schema_version": SCHEMA_VERSION, "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "upload_id": upload_id, "source_file": source_filename,
        "provider": "cloudflare_workers_ai", "model": llm.model, "prompt_version": config.PROMPT_VERSION,
        "method": ("AI-generated from the uploaded file only. Counts, percentages and sentiment totals are computed in code from per-review extractions; the model grouped theme labels and wrote "
                   "insights and hypotheses. Every quote is verified as verbatim in its review; unverifiable citations were dropped. Not human-validated and not mixed with the Urban Company dataset."),
        "dataset": {"rows_in_upload": rows_in_file if rows_in_file is not None else len(rows), "rows_submitted_to_analysis": len(work), "rows_not_analysed_due_to_limit": max(0, len(rows) - len(work)),
                    "analysis_row_limit": limit, "reviews_analysed": len(ok), "extraction_failed": sum(1 for r in recs if r["extraction_status"] == "failed"),
                    "not_a_customer_experience": sum(1 for r in recs if r["extraction_status"] == "ok" and not r["is_customer_experience"]), "sources": dict(Counter(r["source"] or "not stated" for r in ok))},
        "sentiment": {s: {"n": sentiment.get(s, 0), "pct": round(100 * sentiment.get(s, 0) / len(ok), 1)} for s in SENTIMENTS},
        "return_behaviour": {**RCL.summarise([r["return_class"] for r in ok], [r["return_basis"] for r in ok]),
                             "method": "Return / Non-Return is a prediction. The model reads what each review says about booking again; the class is then decided in code: stated or signalled behaviour first, otherwise sentiment and star rating. It is not an observed repeat-booking rate."},
        "themes": themes, "positive_experiences": pos_exp, "negative_experiences": neg_exp, "mixed_reviews": mixed,
        "insights": insights, "opportunities": opportunities, "evidence": ev.items,
        "quality": {**notes, **cnotes, "reviews_with_model_quote": sum(1 for r in ok if r["evidence_source"] == "model_quote"), "reviews_with_review_start_excerpt": sum(1 for r in ok if r["evidence_source"] == "review_start")},
        "usage": usage}
    return result, recs
