"""Step 2 LLM pipeline. LLM outputs are validated, quote-verified against the original review text, and all COUNTS are computed in code
(never taken from the model). Failures are logged, never filled in."""
import json
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import config, data, prompts, schemas
from .llm import DailyLimitReached, IncompleteResponse, LLMFailure, ServiceUnavailable

SIGNAL_BASES = {"advice_to_others", "switching_intent", "trust_or_satisfaction", "dissatisfaction"}
EXPLICIT_BASES = {"Explicit Return": {"reported_repeat_use", "stated_intent_to_return"},
                  "Explicit Non-Return": {"stated_will_not_return", "switched_or_stopped"}}
QUOTE_FIELDS = ["expectation_quote", "return_quote", "trigger_quote", "household_quote", "discovery_quote", "unmet_need_quote", "key_quote"]


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def jdump(obj, path):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def jload(path, default=None):
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else default


def log_failure(out, stage, ids, err):
    Path(out).mkdir(parents=True, exist_ok=True)
    with open(Path(out) / "failures.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps({"time": now(), "stage": stage, "ids": ids, "error": str(err)[:500]}, ensure_ascii=False) + "\n")


def update_manifest(out, **kw):
    p = Path(out) / "run_manifest.json"
    m = jload(p, {})
    m.update(kw)
    m["updated_at"] = now()
    jdump(m, p)


# =====================================================================================================================
# STAGE 1: per-review structured extraction (batched, resumable)
# =====================================================================================================================
def _review_block(r):
    t = r["text"]
    if len(t) > config.MAX_REVIEW_CHARS:
        t = t[:config.MAX_REVIEW_CHARS] + " [text truncated]"
    rt = r["rating"] if r["rating"] else "none"
    return f"[{r['record_id']}] source={r['platform']} | rating={rt} | sentiment={r['sentiment_label']}\nTEXT: {t}"


def _validate_batch(ids):
    def v(obj):
        b = schemas.ExtractionBatch.model_validate(obj)
        got = [x.review_id for x in b.results]
        if sorted(got) != sorted(ids) or len(got) != len(ids):
            missing = sorted(set(ids) - set(got)); extra = sorted(set(got) - set(ids))
            raise ValueError(f"results must contain exactly these review ids once each. missing={missing} unexpected={extra}")
        return b
    return v


def _postprocess(x, row):
    """Verify quotes against the full original text and enforce the evidence standard. Returns a storable record."""
    d = x.model_dump()
    text = row["text"]
    dropped = []
    for f in QUOTE_FIELDS:
        if d.get(f) and not data.verify_quote(d[f], text):
            dropped.append({"field": f, "quote": d[f]}); d[f] = None
    for a in d["alternatives"]:
        if a.get("quote") and not data.verify_quote(a["quote"], text):
            dropped.append({"field": "alternative.quote", "quote": a["quote"]}); a["quote"] = None
    # supported-field consistency: a descriptive field whose supporting quote was rejected is not trusted
    for fld, q in (("household_cue", "household_quote"), ("booking_trigger", "trigger_quote"), ("expectation_summary", "expectation_quote"),
                   ("unmet_need", "unmet_need_quote")):
        if d.get(fld) and d.get(q) is None:
            if any(dd["field"] == q for dd in dropped):
                dropped.append({"field": fld + " (unsupported)", "quote": d[fld]}); d[fld] = None
    if d.get("discovery_channel") and d.get("discovery_quote") is None and any(dd["field"] == "discovery_quote" for dd in dropped):
        dropped.append({"field": "discovery_channel (unsupported)", "quote": d["discovery_channel"]}); d["discovery_channel"] = None
    # evidence standard for return classes
    orig = d["return_class"]; reason = None
    basis_ok = d["return_basis"] in EXPLICIT_BASES.get(orig, SIGNAL_BASES if orig == "Behavioural Signal" else {"none"})
    if orig in EXPLICIT_BASES and (not d.get("return_quote")):
        reason = "explicit class without a verified verbatim quote"
    elif not basis_ok:
        reason = "return_basis inconsistent with return_class"
    if reason:
        wc = len(re.findall(r"\w+", text))
        d["return_class"] = "Behavioural Signal" if (wc >= 8 and d["return_basis"] in SIGNAL_BASES) else "Insufficient Evidence"
        if d["return_class"] == "Insufficient Evidence":
            d["return_basis"] = "none"
        d["return_class_original"] = orig
        d["downgrade_reason"] = reason
    d["dropped_quotes"] = dropped
    d.update({"record_id": row["record_id"], "platform": row["platform"], "source_url": row["source_url"], "sentiment_label": row["sentiment_label"],
              "rating": row["rating"], "review_date": row["review_date"], "service_category": row["service_category"], "city": row["city"],
              "model": config.MODEL, "prompt_version": config.PROMPT_VERSION})
    return d


def _extract_rows(llm, rows, out, depth=0):
    ids = [r["record_id"] for r in rows]
    user = prompts.EXTRACT_USER.format(n=len(rows), reviews="\n\n".join(_review_block(r) for r in rows))
    try:
        batch, meta = llm.call_json("extract", prompts.EXTRACT_SYSTEM, user, _validate_batch(ids), max_tokens=min(6000, 700 * len(rows) + 600))
    except DailyLimitReached:
        raise
    except ServiceUnavailable as e:   # provider busy: splitting cannot help; log and let a later resume retry these ids
        log_failure(out, "extract", ids, e)
        return []
    except LLMFailure as e:   # includes IncompleteResponse / invalid output -> split the batch, down to single reviews
        if len(rows) > 1:
            mid = len(rows) // 2
            return _extract_rows(llm, rows[:mid], out, depth + 1) + _extract_rows(llm, rows[mid:], out, depth + 1)
        log_failure(out, "extract", ids, e)
        return []
    byid = {r["record_id"]: r for r in rows}
    return [_postprocess(x, byid[x.review_id]) for x in batch.results]


def run_extraction(llm, df, out, limit=None, batch_size=None, progress=print):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    path = out / "review_extractions.jsonl"
    done = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line); done[rec["review_id"]] = rec
    todo = df[~df.record_id.isin(done)]
    if limit:
        todo = df.head(limit)
        todo = todo[~todo.record_id.isin(done)]
    rows = todo.to_dict("records")
    bs = batch_size or config.BATCH_SIZE
    t0 = time.time(); n_new = 0
    try:
        for i in range(0, len(rows), bs):
            chunk = rows[i:i + bs]
            recs = _extract_rows(llm, chunk, out)
            with open(path, "a", encoding="utf-8") as f:
                for rec in recs:
                    f.write(json.dumps(rec, ensure_ascii=False) + "\n"); done[rec["review_id"]] = rec
            n_new += len(recs)
            progress(f"  extracted {len(done)}/{len(df) if not limit else min(limit, len(df))} reviews  (batch {i // bs + 1}/{-(-len(rows) // bs)}, {time.time() - t0:.0f}s, api_calls={llm.stats['api_calls']}, cache_hits={llm.stats['cache_hits']})")
    except DailyLimitReached as e:
        update_manifest(out, stage_extract={"status": "paused_daily_limit", "processed": len(done), "note": str(e)[:200]})
        raise
    failed = []
    fp = out / "failures.jsonl"
    if fp.exists():
        for l in fp.read_text(encoding="utf-8").splitlines():
            j = json.loads(l)
            if j["stage"] == "extract":
                failed += j["ids"]
    target = set(df.head(limit).record_id) if limit else set(df.record_id)
    failed_open = sorted((set(failed) & target) - set(done))
    update_manifest(out, stage_extract={"status": "complete" if not failed_open and target <= set(done) else "incomplete",
                                        "reviews_in_scope": len(target), "reviews_processed": len(target & set(done)),
                                        "reviews_failed": len(failed_open), "failed_ids": failed_open[:200]})
    return done


def load_extractions(out):
    p = Path(out) / "review_extractions.jsonl"
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []


# =====================================================================================================================
# generic phrase clustering (map -> merge) used for issues, positives, unmet needs
# =====================================================================================================================
def _chunk_validate(ids):
    def v(obj):
        c = schemas.ClusterChunk.model_validate(obj)
        seen = Counter(i for cl in c.clusters for i in cl.ids)
        miss = [i for i in ids if seen[i] == 0]; dup = [i for i, n in seen.items() if n > 1]; ext = [i for i in seen if i not in set(ids)]
        if miss or dup or ext:
            raise ValueError(f"every id must be assigned exactly once. missing={miss[:15]} duplicated={dup[:15]} unknown={ext[:15]}")
        return c
    return v


def _merge_validate(labels):
    def v(obj):
        m = schemas.MergeResult.model_validate(obj)
        seen = Counter(x for t in m.types for x in t.merged_from)
        miss = [l for l in labels if seen[l] == 0]; dup = [l for l, n in seen.items() if n > 1]; ext = [l for l in seen if l not in set(labels)]
        if miss or dup or ext:
            raise ValueError(f"every input label must appear in exactly one merged_from. missing={miss[:15]} duplicated={dup[:15]} unknown={ext[:15]}")
        return m
    return v


def cluster_phrases(llm, task, items, out, chunk=160, max_labels=12, max_types=18):
    """items: [(id, phrase)]. Returns (id->type_name, types=[{name, definition, ids}], status)."""
    if not items:
        return {}, [], "no_items"
    label_of, defs = {}, {}
    try:
        for i in range(0, len(items), chunk):
            part = items[i:i + chunk]
            ids = [x[0] for x in part]
            user = "Phrases (id: phrase)\n" + "\n".join(f"{a}: {b}" for a, b in part)
            res, _ = llm.call_json(f"cluster_{task}", prompts.CLUSTER_SYSTEM.format(max_labels=max_labels), user, _chunk_validate(ids), max_tokens=4000)
            for cl in res.clusters:
                lab = f"{cl.label.strip()}"
                defs[lab] = cl.definition
                for rid in cl.ids:
                    label_of[rid] = lab
        labels = sorted(set(label_of.values()))
        counts = Counter(label_of.values())
        user = "Labels (label | definition | count)\n" + "\n".join(f"{l} | {defs[l]} | {counts[l]}" for l in labels)
        merged, _ = llm.call_json(f"merge_{task}", prompts.MERGE_SYSTEM.format(max_types=max_types), user, _merge_validate(labels), max_tokens=4000)
    except DailyLimitReached:
        raise
    except LLMFailure as e:
        log_failure(out, f"cluster_{task}", [], e)
        return {}, [], f"failed: {str(e)[:120]}"
    to_type, tdef = {}, {}
    for t in merged.types:
        tdef[t.name] = t.definition
        for l in t.merged_from:
            to_type[l] = t.name
    id_type = {rid: to_type[l] for rid, l in label_of.items() if l in to_type}
    types = []
    for name in tdef:
        ids = sorted(r for r, tn in id_type.items() if tn == name)
        if ids:
            types.append({"name": name, "definition": tdef[name], "review_ids": ids, "n": len(ids)})
    types.sort(key=lambda x: -x["n"])
    return id_type, types, "ok"


# =====================================================================================================================
# helpers over extraction records
# =====================================================================================================================
def relevant(recs):
    return [r for r in recs if r["is_customer_experience"]]


def info(df):
    return {r["record_id"]: r for r in df.to_dict("records")}


def cite_ok(cite, recs_by_id, master_by_id):
    rid = cite.review_id
    if rid not in master_by_id:
        return False
    return data.verify_quote(cite.quote, master_by_id[rid]["text"])


def cited(cites, master_by_id):
    out, dropped = [], 0
    for c in cites:
        if cite_ok(c, None, master_by_id):
            m = master_by_id[c.review_id]
            out.append({"review_id": c.review_id, "quote": c.quote, "source_url": m["source_url"], "platform": m["platform"],
                        "sentiment_label": m["sentiment_label"], "rating": m["rating"]})
        else:
            dropped += 1
    return out, dropped


def ask_question(llm, qid, title, guidance, evidence, master_by_id, out):
    user = f"QUESTION {qid}: {title}\nGuidance: {guidance}\n\nEVIDENCE PACKAGE\n{evidence}"
    def v(obj):
        a = schemas.QuestionAnswer.model_validate(obj)
        return a
    try:
        ans, meta = llm.call_json(f"answer_{qid}", prompts.ANSWER_SYSTEM, user, v, max_tokens=3500)
    except DailyLimitReached:
        raise
    except LLMFailure as e:
        log_failure(out, f"answer_{qid}", [], e)
        return {"question_id": qid, "question": title, "status": f"failed: {str(e)[:150]}"}
    findings, dropped_total = [], 0
    for f in ans.findings:
        cs, d = cited(f.supporting, master_by_id); dropped_total += d
        if cs:
            findings.append({"finding": f.finding, "supporting": cs, "n_supporting_reviews": len({c["review_id"] for c in cs})})
        else:
            dropped_total += 1
    return {"question_id": qid, "question": title, "status": "ok", "summary": ans.summary, "findings": findings,
            "evidence_strength": ans.evidence_strength, "evidence_gaps": ans.evidence_gaps,
            "validation": {"citations_dropped_unverifiable": dropped_total, "model": llm.model, "prompt_version": config.PROMPT_VERSION}}


def pkg_lines(recs, fn, cap=120, per_platform_floor=12):
    """Evidence lines with diversity across platforms (round-robin), capped."""
    by = defaultdict(list)
    for r in recs:
        s = fn(r)
        if s:
            by[r["platform"]].append(f"[{r['record_id']}] ({r['platform']}, {r['sentiment_label']}) {s}")
    lines, i = [], 0
    plats = sorted(by)
    while len(lines) < cap and any(i < len(by[p]) for p in plats):
        for p in plats:
            if i < len(by[p]) and len(lines) < cap:
                lines.append(by[p][i])
        i += 1
    return lines


# =====================================================================================================================
# STAGE 2: emergent themes
# =====================================================================================================================
def run_themes(llm, df, out, progress=print):
    out = Path(out)
    recs = relevant(load_extractions(out))
    master = info(df)
    prob = [(r["record_id"], r["problem_phrase"]) for r in recs if r.get("problem_phrase")]
    pos = [(r["record_id"], r["positive_phrase"]) for r in recs if r.get("positive_phrase")]
    progress(f"  clustering {len(prob)} problem phrases and {len(pos)} positive phrases")
    ptype, ptypes, s1 = cluster_phrases(llm, "problems", prob, out)
    qtype, qtypes, s2 = cluster_phrases(llm, "positives", pos, out)
    if s1 != "ok" or not ptypes:
        update_manifest(out, stage_themes={"status": f"incomplete: problems clustering {s1}"})
        return None
    all_types = [dict(t, kind="problem") for t in ptypes] + [dict(t, kind="positive") for t in qtypes]
    names = [t["name"] for t in all_types]
    user = "Issue types (name | kind | definition | supporting reviews)\n" + "\n".join(f"{t['name']} | {t['kind']} | {t['definition']} | {t['n']}" for t in all_types)

    def vt(obj):
        th = schemas.ThemeResult.model_validate(obj)
        seen = Counter(x for t in th.themes for x in t.issue_types)
        miss = [n for n in names if seen[n] == 0]; dup = [n for n, c in seen.items() if c > 1]; ext = [n for n in seen if n not in set(names)]
        if miss or dup or ext:
            raise ValueError(f"every issue type must be in exactly one theme, using exact names. missing={miss[:10]} duplicated={dup[:10]} unknown={ext[:10]}")
        return th
    try:
        themes, _ = llm.call_json("themes", prompts.THEME_SYSTEM.format(), user, vt, max_tokens=3000)
    except DailyLimitReached:
        raise
    except LLMFailure as e:
        log_failure(out, "themes", [], e)
        update_manifest(out, stage_themes={"status": f"failed: {str(e)[:120]}"})
        return None
    type_theme = {n: t.theme_id for t in themes.themes for n in t.issue_types}
    rid_themes = defaultdict(set)
    for rid, tn in list(ptype.items()) + list(qtype.items()):
        rid_themes[rid].add(type_theme[tn])
    base_n = len(df); rec_by = {r["record_id"]: r for r in recs}
    stats = []
    for th in themes.themes:
        ids = sorted(rid for rid, ts in rid_themes.items() if th.theme_id in ts)
        sub = [rec_by[i] for i in ids]
        sent = Counter(r["sentiment_label"] for r in sub)
        plat = Counter(r["platform"] for r in sub)
        base_by_plat = Counter(df.platform)
        prev = {p: round(100 * plat[p] / base_by_plat[p], 1) for p in base_by_plat}
        cand = [(r["record_id"], r["key_quote"]) for r in sub if r.get("key_quote")]
        stats.append({"theme_id": th.theme_id, "name": th.name, "description_initial": th.description,
                      "issue_types": [{"name": n, "kind": next(t["kind"] for t in all_types if t["name"] == n), "n": next(t["n"] for t in all_types if t["name"] == n)} for n in th.issue_types],
                      "n_reviews": len(ids), "pct_of_analysis_base": round(100 * len(ids) / base_n, 1),
                      "sentiment_counts": {k: sent.get(k, 0) for k in ["Positive", "Negative", "Neutral", "Mixed", "Uncertain"]},
                      "prevalence_pct_within_each_source": prev, "n_by_source": dict(plat),
                      "explicit_return": sum(r["return_class"] == "Explicit Return" for r in sub),
                      "explicit_non_return": sum(r["return_class"] == "Explicit Non-Return" for r in sub),
                      "review_ids": ids, "_cand": cand})
    # narrative from the model, grounded on computed stats + candidate quotes
    ev = []
    for s in stats:
        cands = s["_cand"][:14]
        ev.append(f"THEME {s['theme_id']}: {s['name']}\n computed: n_reviews={s['n_reviews']}, sentiment={s['sentiment_counts']}, issue_types={[t['name'] for t in s['issue_types']]}\n candidate quotes:\n" +
                  "\n".join(f"  [{i}] {q}" for i, q in cands))
    try:
        narr, _ = llm.call_json("theme_narratives", prompts.NARRATIVE_SYSTEM, "\n\n".join(ev), lambda o: schemas.ThemeNarrativeResult.model_validate(o), max_tokens=3500)
        nmap = {n.theme_id: n for n in narr.narratives}
    except DailyLimitReached:
        raise
    except LLMFailure as e:
        log_failure(out, "theme_narratives", [], e); nmap = {}
    # importance ranking (computed): reach 40%, severity 30%, source breadth 15%, return-link 15%
    maxn = max(s["n_reviews"] for s in stats) or 1
    for s in stats:
        negshare = (s["sentiment_counts"]["Negative"] + s["sentiment_counts"]["Mixed"]) / max(1, s["n_reviews"])
        breadth = sum(1 for p, v in s["prevalence_pct_within_each_source"].items() if v >= 5) / max(1, len(s["prevalence_pct_within_each_source"]))
        rl = (s["explicit_return"] + s["explicit_non_return"]) / max(1, s["n_reviews"])
        s["importance"] = {"reach": round(s["n_reviews"] / maxn, 3), "severity": round(negshare, 3), "source_breadth": round(breadth, 3),
                           "return_link": round(min(1.0, rl * 10), 3),
                           "score": round(0.4 * s["n_reviews"] / maxn + 0.3 * negshare + 0.15 * breadth + 0.15 * min(1.0, rl * 10), 3),
                           "formula": "0.40*reach(n/max n) + 0.30*severity(share Negative+Mixed) + 0.15*source_breadth(share of sources with >=5% prevalence) + 0.15*return_link(10*share with explicit return/non-return, capped at 1)"}
        n = nmap.get(s["theme_id"])
        rep_ids = [i for i in (n.representative_review_ids if n else []) if i in set(s["review_ids"])][:5]
        if not rep_ids:
            rep_ids = [i for i, _ in s["_cand"][:3]]
        quotes = []
        for i in rep_ids:
            q = rec_by[i].get("key_quote")
            if q and data.verify_quote(q, master[i]["text"]):
                quotes.append({"review_id": i, "quote": q, "source_url": master[i]["source_url"], "platform": master[i]["platform"], "sentiment_label": master[i]["sentiment_label"]})
        s["description"] = n.description if n else s["description_initial"]
        s["main_customer_problems"] = n.main_customer_problems if n else []
        s["representative_quotes"] = quotes
        s.pop("_cand"); s.pop("description_initial")
    stats.sort(key=lambda s: -s["importance"]["score"])
    for rank, s in enumerate(stats, 1):
        s["importance_rank"] = rank
    result = {"generated_at": now(), "model": llm.model, "analysis_base_reviews": base_n,
              "themes": stats, "top_three_theme_ids": [s["theme_id"] for s in stats[:3]],
              "problem_issue_types": ptypes, "positive_driver_types": qtypes,
              "note": "Themes were proposed by the LLM from clustered customer phrases (max 5). Counts are computed in code."}
    jdump(result, out / "themes.json")
    update_manifest(out, stage_themes={"status": "complete", "themes": len(stats)})
    # per-review theme assignment goes back into a reusable file
    jdump({rid: sorted(ts) for rid, ts in rid_themes.items()}, out / "review_theme_assignments.json")
    return result


# =====================================================================================================================
# STAGE 3: unmet needs and booking triggers (clusters)
# =====================================================================================================================
def run_unmet_needs(llm, df, out, progress=print):
    out = Path(out)
    recs = relevant(load_extractions(out)); master = info(df)
    items = [(r["record_id"], r["unmet_need"]) for r in recs if r.get("unmet_need")]
    progress(f"  clustering {len(items)} unmet-need phrases")
    id_type, types, status = cluster_phrases(llm, "unmet_needs", items, out, max_types=15)
    if status != "ok":
        update_manifest(out, stage_unmet_needs={"status": status}); return None
    rec_by = {r["record_id"]: r for r in recs}
    clusters = []
    for t in types:
        sub = [rec_by[i] for i in t["review_ids"]]
        quotes = [{"review_id": r["record_id"], "quote": r["unmet_need_quote"], "source_url": r["source_url"], "platform": r["platform"]}
                  for r in sub if r.get("unmet_need_quote")][:8]
        clusters.append({"name": t["name"], "definition": t["definition"], "n_reviews": t["n"], "pct_of_analysis_base": round(100 * t["n"] / len(df), 1),
                         "n_by_source": dict(Counter(r["platform"] for r in sub)), "sentiment_counts": dict(Counter(r["sentiment_label"] for r in sub)),
                         "review_ids": t["review_ids"], "source_urls": [rec_by[i]["source_url"] for i in t["review_ids"]], "quotes": quotes})
    res = {"generated_at": now(), "model": llm.model, "clusters": clusters, "reviews_with_unmet_need": len(items)}
    jdump(res, out / "unmet_needs.json")
    update_manifest(out, stage_unmet_needs={"status": "complete", "clusters": len(clusters), "reviews_with_unmet_need": len(items)})
    return res


# =====================================================================================================================
# STAGE 4: behaviour (code aggregation of validated per-review classes) and alternatives
# =====================================================================================================================
def run_behaviour(df, out):
    out = Path(out)
    recs = relevant(load_extractions(out)); master = info(df)
    th = jload(out / "review_theme_assignments.json", {})
    def row(r):
        m = master[r["record_id"]]
        return {"review_id": r["record_id"], "source_url": m["source_url"], "platform": m["platform"], "sentiment_label": m["sentiment_label"], "rating": m["rating"],
                "return_class": r["return_class"], "return_basis": r["return_basis"], "evidence_quote": r.get("return_quote"), "review_text": m["text"],
                "theme_ids": th.get(r["record_id"], []), "downgraded": r.get("downgrade_reason")}
    groups = defaultdict(list)
    for r in recs:
        groups[r["return_class"]].append(row(r))
    summary = {c: len(v) for c, v in groups.items()}
    by_platform = {c: dict(Counter(x["platform"] for x in v)) for c, v in groups.items()}
    by_basis = Counter((r["return_class"], r["return_basis"]) for r in recs)
    theme_by_class = {}
    for c in ("Explicit Return", "Explicit Non-Return"):
        n = max(1, len(groups[c]))
        cnt = Counter(t for x in groups[c] for t in x["theme_ids"])
        theme_by_class[c] = {t: {"n": k, "share": round(k / n, 3)} for t, k in sorted(cnt.items())}
    res = {"generated_at": now(), "reviews_classified": len(recs), "class_counts": summary, "class_counts_by_source": by_platform,
           "basis_counts": {f"{k[0]} | {k[1]}": v for k, v in by_basis.items()},
           "theme_prevalence_among_explicit_groups": theme_by_class,
           "downgraded_for_missing_evidence": sum(1 for r in recs if r.get("downgrade_reason")),
           "definitions": {"Explicit Return": "reports repeat/ongoing use or states they will book again (verbatim quote required)",
                           "Explicit Non-Return": "first-person statement of not using again / stopped / switched (verbatim quote required)",
                           "Behavioural Signal": "satisfaction, dissatisfaction, trust or switching cue without established repeat behaviour",
                           "Insufficient Evidence": "not enough information"},
           "records": {c: groups[c] for c in ("Explicit Return", "Explicit Non-Return")},
           "behavioural_signal_review_ids": [x["review_id"] for x in groups["Behavioural Signal"]],
           "insufficient_evidence_review_ids": [x["review_id"] for x in groups["Insufficient Evidence"]]}
    jdump(res, out / "behaviour.json")
    update_manifest(out, stage_behaviour={"status": "complete", "class_counts": summary})
    return res


def run_alternatives(llm, df, out):
    out = Path(out)
    recs = relevant(load_extractions(out)); master = info(df)
    rows = []
    for r in recs:
        for a in r.get("alternatives", []):
            rows.append({"review_id": r["record_id"], "name": a["name"].strip(), "type": a["type"], "relation": a["relation"], "reason": a.get("reason"),
                         "quote": a.get("quote"), "platform": r["platform"], "service_category": r.get("service_category") or "", "sentiment": r["sentiment_label"]})
    if not rows:
        update_manifest(out, stage_alternatives={"status": "no_alternatives_found"}); return None
    tcount = Counter(x["type"] for x in rows)
    ncount = Counter((x["type"], re.sub(r"[^a-z0-9]", "", x["name"].lower())) for x in rows)
    lines = [f"COUNTS (computed): mentions by type = {dict(tcount)}"]
    for t in tcount:
        lines.append(f"\nTYPE {t}: {tcount[t]} mentions in {len({x['review_id'] for x in rows if x['type'] == t})} reviews")
        sub = [x for x in rows if x["type"] == t]
        for x in sub[:40]:
            if x["quote"] or x["reason"]:
                lines.append(f"  [{x['review_id']}] ({x['platform']}, cat={x['service_category'] or 'n/a'}, {x['relation']}) name={x['name']} | reason={x['reason']} | quote: {x['quote']}")
    try:
        ans, _ = llm.call_json("alternatives", prompts.ALT_SYSTEM, "\n".join(lines)[:24000], lambda o: schemas.AlternativesAnswer.model_validate(o), max_tokens=4500)
    except DailyLimitReached:
        raise
    except LLMFailure as e:
        log_failure(out, "alternatives", [], e); update_manifest(out, stage_alternatives={"status": f"failed: {str(e)[:100]}"}); return None
    alts = []
    for a in ans.alternatives:
        cs, dropped = cited(a.supporting, master)
        names = {re.sub(r"[^a-z0-9]", "", a.name.lower())}
        n_mentions = sum(1 for x in rows if x["type"] == a.type and (re.sub(r"[^a-z0-9]", "", x["name"].lower()) in names or a.name.lower() in x["name"].lower()))
        alts.append({**a.model_dump(exclude={"supporting"}), "supporting": cs, "citations_dropped_unverifiable": dropped,
                     "mentions_matching_name_or_type_computed": n_mentions or tcount.get(a.type, 0)})
    res = {"generated_at": now(), "model": llm.model, "mentions_by_type": dict(tcount), "top_named": [{"type": k[0], "name_key": k[1], "n": v} for k, v in ncount.most_common(25)],
           "summary": ans.summary, "alternatives": alts, "all_mentions": rows}
    jdump(res, out / "alternatives.json")
    update_manifest(out, stage_alternatives={"status": "complete", "types": dict(tcount)})
    return res


# =====================================================================================================================
# STAGE 5: segments (computed) and the eight cited answers
# =====================================================================================================================
def run_segments(df, out):
    out = Path(out)
    recs = relevant(load_extractions(out)); master = info(df)
    th = jload(out / "review_theme_assignments.json", {})
    d = pd.DataFrame([{"id": r["record_id"], "platform": r["platform"], "sentiment": r["sentiment_label"], "category": r.get("service_category") or "(not stated)",
                       "city": r.get("city") or "", "ret": r["return_class"], "themes": th.get(r["record_id"], []), "disc": r.get("discovery_channel"), "hh": r.get("household_cue")} for r in recs])
    def table(col, minn):
        o = []
        for k, g in d.groupby(col):
            if not k or len(g) < minn: continue
            tc = Counter(t for ts in g.themes for t in ts)
            o.append({col: k, "n": int(len(g)), "sentiment_pct": {s: round(100 * (g.sentiment == s).mean(), 1) for s in ["Positive", "Negative", "Neutral", "Mixed"]},
                      "theme_prevalence_pct": {t: round(100 * c / len(g), 1) for t, c in sorted(tc.items())},
                      "explicit_return": int((g.ret == "Explicit Return").sum()), "explicit_non_return": int((g.ret == "Explicit Non-Return").sum()),
                      "review_ids": list(g.id)})
        return sorted(o, key=lambda x: -x["n"])
    hh = defaultdict(list)
    for r in recs:
        if r.get("household_cue") and r.get("household_quote"):
            hh[r["household_cue"].strip().lower()].append({"review_id": r["record_id"], "quote": r["household_quote"], "source_url": r["source_url"], "platform": r["platform"]})
    dc = defaultdict(list)
    for r in recs:
        if r.get("discovery_channel") and r.get("discovery_quote"):
            dc[r["discovery_channel"]].append({"review_id": r["record_id"], "quote": r["discovery_quote"], "source_url": r["source_url"], "platform": r["platform"]})
    res = {"generated_at": now(), "min_group_sizes": {"service_category": 15, "city": 8, "platform": 1},
           "by_platform": table("platform", 1), "by_service_category": table("category", 15), "by_city": table("city", 8),
           "household_cues": {k: {"n": len(v), "examples": v[:6]} for k, v in sorted(hh.items(), key=lambda kv: -len(kv[1]))[:40]},
           "discovery_channels": {k: {"n": len(v), "examples": v[:8]} for k, v in sorted(dc.items(), key=lambda kv: -len(kv[1]))},
           "note": "Household and discovery evidence exists only where the review states it; counts are of stated cues, not prevalence in the customer base."}
    jdump(res, out / "segments.json")
    update_manifest(out, stage_segments={"status": "complete"})
    return res


def run_questions(llm, df, out, progress=print):
    out = Path(out)
    recs = relevant(load_extractions(out)); master = info(df)
    themes = jload(out / "themes.json", {}); behaviour = jload(out / "behaviour.json", {}); unmet = jload(out / "unmet_needs.json", {})
    segs = jload(out / "segments.json", {}); alts = jload(out / "alternatives.json", {})
    answers = {}
    def pk(title, computed, lines):
        return f"COMPUTED FACTS (do not change): {computed}\n\nVERBATIM EVIDENCE (id, source, sentiment, text):\n" + "\n".join(lines)
    n_rel = len(recs)
    ev = {}
    ev["Q1"] = pk("Q1", {"relevant_reviews": n_rel, "reviews_with_stated_expectation": sum(1 for r in recs if r.get("expectation_quote"))},
                  pkg_lines(recs, lambda r: (f"expectation: {r['expectation_summary']} | quote: {r['expectation_quote']}" if r.get("expectation_quote") else None), 130))
    ev["Q2"] = pk("Q2", {"relevant_reviews": n_rel, "reviews_with_stated_trigger": sum(1 for r in recs if r.get("trigger_quote")),
                         "urgency_counts": dict(Counter(r["urgency"] for r in recs))},
                  pkg_lines(recs, lambda r: (f"trigger: {r['booking_trigger']} | urgency={r['urgency']} | quote: {r['trigger_quote']}" if r.get("trigger_quote") else None), 130))
    altrows = [(r, a) for r in recs for a in r.get("alternatives", [])]
    ev["Q3"] = pk("Q3", {"reviews_mentioning_alternatives": len({r['record_id'] for r, _ in altrows}), "mentions_by_type": dict(Counter(a['type'] for _, a in altrows)),
                         "class_counts": behaviour.get("class_counts")},
                  pkg_lines(recs, lambda r: ("; ".join(f"{a['name']} [{a['type']}, {a['relation']}] reason={a.get('reason')} quote={a.get('quote')}" for a in r.get("alternatives", [])) if r.get("alternatives") else None), 130))
    ex = [r for r in recs if r["return_class"].startswith("Explicit")]
    ev["Q4"] = pk("Q4", {"class_counts": behaviour.get("class_counts"), "basis_counts": behaviour.get("basis_counts")},
                  pkg_lines(ex, lambda r: f"{r['return_class']} ({r['return_basis']}) | quote: {r.get('return_quote')}", 140))
    off = [(r, a) for r, a in altrows if a["type"] in ("local_independent", "friends_family_neighbours", "community_group_or_whatsapp", "brand_service_centre", "directory_or_search")]
    ev["Q5"] = pk("Q5", {"offline_or_informal_mentions_by_type": dict(Counter(a['type'] for _, a in off)), "reviews": len({r['record_id'] for r, _ in off})},
                  pkg_lines([r for r, _ in off], lambda r: "; ".join(f"{a['name']} [{a['type']}, {a['relation']}] reason={a.get('reason')} quote={a.get('quote')}" for a in r["alternatives"] if a["type"] in ("local_independent", "friends_family_neighbours", "community_group_or_whatsapp", "brand_service_centre", "directory_or_search")), 120))
    ev["Q6"] = pk("Q6", {"class_counts": behaviour.get("class_counts"), "theme_prevalence_among_explicit_groups": behaviour.get("theme_prevalence_among_explicit_groups"),
                         "theme_names": {t["theme_id"]: t["name"] for t in themes.get("themes", [])},
                         "caution": "explicit groups are small; compare descriptively, not statistically"},
                  pkg_lines([r for r in recs if r["return_class"].startswith("Explicit")], lambda r: f"{r['return_class']} | problem={r.get('problem_phrase')} | valued={r.get('positive_phrase')} | quote: {r.get('return_quote')}", 140))
    segc = {k: [{kk: vv for kk, vv in g.items() if kk != "review_ids"} for g in segs.get(k, [])] for k in ("by_platform", "by_service_category", "by_city")}
    hhl = [f"household [{v['examples'][0]['review_id']}] {k}: n={v['n']} quote: {v['examples'][0]['quote']}" for k, v in list(segs.get("household_cues", {}).items())[:25]]
    dcl = [f"discovery [{v['examples'][0]['review_id']}] {k}: n={v['n']} quote: {v['examples'][0]['quote']}" for k, v in segs.get("discovery_channels", {}).items()]
    ev["Q7"] = pk("Q7", json.dumps(segc, ensure_ascii=False)[:14000], hhl + dcl)
    ev["Q8"] = pk("Q8", {"clusters": [{"name": c["name"], "n": c["n_reviews"], "by_source": c["n_by_source"]} for c in unmet.get("clusters", [])]},
                  [f"[{q['review_id']}] cluster={c['name']} quote: {q['quote']}" for c in unmet.get("clusters", []) for q in c["quotes"][:4]])
    for qid, (title, guide) in prompts.QUESTIONS.items():
        progress(f"  answering {qid}")
        answers[qid] = ask_question(llm, qid, title, guide, ev[qid][:30000], master, out)
    res = {"generated_at": now(), "model": llm.model, "answers": answers}
    jdump(res, out / "question_answers.json")
    update_manifest(out, stage_questions={"status": "complete" if all(a.get("status") == "ok" for a in answers.values()) else "partial",
                                          "answered": [q for q, a in answers.items() if a.get("status") == "ok"],
                                          "failed": [q for q, a in answers.items() if a.get("status") != "ok"]})
    return res


# =====================================================================================================================
# STAGE 6: opportunities (LLM proposes; code scores)
# =====================================================================================================================
def run_opportunities(llm, df, out):
    out = Path(out)
    recs = relevant(load_extractions(out)); master = info(df); rec_by = {r["record_id"]: r for r in recs}
    themes = jload(out / "themes.json", {}); unmet = jload(out / "unmet_needs.json", {})
    clusters = {}
    for t in themes.get("problem_issue_types", []):
        clusters["problem: " + t["name"]] = t["review_ids"]
    for c in unmet.get("clusters", []):
        clusters["unmet need: " + c["name"]] = c["review_ids"]
    if not clusters:
        update_manifest(out, stage_opportunities={"status": "needs_themes_and_unmet_needs"}); return None
    def metrics(ids):
        sub = [rec_by[i] for i in ids if i in rec_by]
        if not sub: return {}
        neg = sum(1 for r in sub if r["sentiment_label"] in ("Negative",) or (r["rating"] and float(r["rating"]) <= 2)) / len(sub)
        sw = sum(1 for r in sub if r["return_class"] == "Explicit Non-Return" or r["return_basis"] in ("switching_intent", "advice_to_others", "switched_or_stopped", "stated_will_not_return")) / len(sub)
        plats = Counter(r["platform"] for r in sub)
        return {"n": len(sub), "pct_of_base": round(100 * len(sub) / len(df), 1), "negative_share": round(neg, 3), "switch_or_warn_share": round(sw, 3),
                "sources_with_3plus": sum(1 for v in plats.values() if v >= 3), "n_by_source": dict(plats)}
    cm = {k: metrics(v) for k, v in clusters.items() if len(v) >= 5}
    top = sorted(cm.items(), key=lambda kv: -kv[1]["n"])[:22]
    lines = []
    for k, m in top:
        lines.append(f"CLUSTER: {k} | n={m['n']} ({m['pct_of_base']}% of base) | negative_share={m['negative_share']} | switch_or_warn_share={m['switch_or_warn_share']} | by_source={m['n_by_source']}")
        for i in clusters[k][:60]:
            r = rec_by.get(i)
            q = r and (r.get("key_quote") or r.get("unmet_need_quote"))
            if q:
                lines.append(f"   [{i}] ({r['platform']}) {q}")
                if sum(1 for l in lines[-6:] if l.startswith('   [')) >= 4: break
    try:
        res, _ = llm.call_json("opportunities", prompts.OPP_SYSTEM, "\n".join(lines)[:28000], lambda o: schemas.OpportunityResult.model_validate(o), max_tokens=6000)
    except DailyLimitReached:
        raise
    except LLMFailure as e:
        log_failure(out, "opportunities", [], e); update_manifest(out, stage_opportunities={"status": f"failed: {str(e)[:100]}"}); return None
    opps = []
    for o in res.opportunities[:8]:
        ids = sorted({i for c in o.related_clusters for i in clusters.get(c, [])})
        valid_clusters = [c for c in o.related_clusters if c in clusters]
        m = metrics(ids)
        cs, dropped = cited(o.supporting, master)
        if not m:
            continue
        freq = min(1.0, m["pct_of_base"] / 15.0)
        evid = min(1.0, (m["sources_with_3plus"] / 4.0) * 0.6 + min(1.0, m["n"] / 80.0) * 0.4)
        score = 0.25 * freq + 0.20 * m["negative_share"] + 0.20 * evid + 0.20 * min(1.0, m["switch_or_warn_share"] * 4) + 0.15 * (o.impact_score_1_to_5 / 5.0)
        opps.append({**o.model_dump(exclude={"supporting", "related_clusters"}), "related_clusters": valid_clusters, "customer_evidence": {"supporting": cs, "citations_dropped_unverifiable": dropped},
                     "metrics_computed": m, "review_ids": ids, "source_urls": [master[i]["source_url"] for i in ids if i in master],
                     "priority_score": round(score, 3),
                     "score_formula": "0.25*frequency(pct_of_base/15, cap 1) + 0.20*severity(negative share) + 0.20*evidence(source breadth & volume) + 0.20*repeat_relevance(4*switch/warn share, cap 1) + 0.15*impact(LLM 1-5 /5; a hypothesis)"})
    opps.sort(key=lambda x: -x["priority_score"])
    for rk, o in enumerate(opps, 1):
        o["priority_rank"] = rk
    jdump({"generated_at": now(), "model": llm.model, "opportunities": opps,
           "note": "customer_evidence is verbatim from reviews; *_hypothesis fields and impact_score are model hypotheses, not findings."}, out / "opportunities.json")
    update_manifest(out, stage_opportunities={"status": "complete", "opportunities": len(opps)})
    return opps


# =====================================================================================================================
# bundle for the future frontend
# =====================================================================================================================
def build_bundle(df, full, out):
    out = Path(out)
    m = jload(out / "run_manifest.json", {})
    bundle = {"schema_version": "1.0", "generated_at": now(), "manifest": m,
              "dataset": {"master_reviews": len(full), "analysis_base_reviews": len(df), "excluded_from_analysis_insta_help": int(full.insta_help.sum())}}
    for key, fn in [("themes", "themes.json"), ("question_answers", "question_answers.json"), ("behaviour", "behaviour.json"), ("alternatives", "alternatives.json"),
                    ("segments", "segments.json"), ("unmet_needs", "unmet_needs.json"), ("opportunities", "opportunities.json")]:
        bundle[key] = jload(out / fn)
    jdump(bundle, out / "discovery_engine_output.json")
    return bundle
