"""PLUMBING TEST ONLY. Uses a synthetic stand-in for the Cloudflare Workers AI HTTP transport to exercise batching, schema validation, quote verification,
evidence enforcement, rate-limit retry, resume and failure logging. Its outputs are throwaway test data written to analysis_test/ and are
NOT analysis results. Run:  python -m backend.test_plumbing"""
import json
import re
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace as NS

from . import config, data, pipeline as P
from . import llm as llm_mod
from .llm import CloudflareLLM, UsageTracker

TEST_DIR = config.ROOT / "analysis_test"


class FakeRateLimit(Exception):
    pass
FakeRateLimit.__name__ = "RateLimitError"


class FakeCompletions:
    def __init__(self):
        self.calls = 0
        self.fail_once = True

    def create(self, **kw):
        self.calls += 1
        if self.fail_once:                      # first call: simulate an HTTP 429
            self.fail_once = False
            raise FakeRateLimit("Rate limit reached. Please try again in 0.2s")
        msgs = kw["messages"]; system = msgs[0]["content"]; user = msgs[1]["content"]
        out = self.respond(system, user)
        return NS(choices=[NS(message=NS(content=json.dumps(out)), finish_reason="stop")], usage=NS(prompt_tokens=100, completion_tokens=50))

    def respond(self, system, user):
        if "extract structured evidence as JSON" in system:
            res = []
            for m in re.finditer(r"\[([A-Z]{2}-\d{4})\][^\n]*\nTEXT: (.*?)(?=\n\n\[|\Z)", user, re.S):
                rid, text = m.group(1), m.group(2).strip()
                again = re.search(r"(?i)book(?:ed)? again|will use|never use", text)
                res.append({"review_id": rid, "is_customer_experience": True,
                            "problem_phrase": "arrived late or cancelled" if re.search(r"(?i)late|cancel", text) else ("high prices" if re.search(r"(?i)expensive|price|high", text) else None),
                            "positive_phrase": "good professional work" if re.search(r"(?i)good|excellent|great", text) else None,
                            "expectation_summary": None, "expectation_quote": "THIS QUOTE IS FABRICATED AND MUST BE DROPPED" if rid.endswith("1") else None,
                            "return_class": "Explicit Return" if again else "Insufficient Evidence", "return_basis": "stated_intent_to_return" if again else "none",
                            "return_quote": again.group(0) if again and not rid.endswith("3") else None,   # id ending 3: explicit class WITHOUT quote -> must be downgraded
                            "unmet_need": "talk to a human" if re.search(r"(?i)customer care|support", text) else None,
                            "unmet_need_quote": re.search(r"(?i)customer care|support", text).group(0) if re.search(r"(?i)customer care|support", text) else None,
                            "alternatives": [{"name": "local technician", "type": "local_independent", "relation": "compares", "reason": "cheaper", "quote": re.search(r"(?i)local\w*", text).group(0)}] if re.search(r"(?i)local", text) else [],
                            "key_quote": text[:90]})
            return {"results": res}
        if "group short customer phrases" in system:
            ids = re.findall(r"^(\S+): (.*)$", user.split("\n", 1)[1], re.M)
            a = [i for i, p in ids if len(p) % 2 == 0]; b = [i for i, p in ids if len(p) % 2 == 1]
            cl = [{"label": "group A", "definition": "even phrases", "ids": a}, {"label": "group B", "definition": "odd phrases", "ids": b}]
            return {"clusters": [c for c in cl if c["ids"]]}
        if "merge overlapping issue-type labels" in system:
            labels = [l.split(" | ")[0] for l in user.split("\n")[1:] if l.strip()]
            return {"types": [{"name": "merged " + l, "definition": "d", "merged_from": [l]} for l in labels]}
        if "MAJOR customer themes" in system:
            names = [l.split(" | ")[0] for l in user.split("\n")[1:] if l.strip()]
            return {"themes": [{"theme_id": "T1", "name": "Test theme one", "description": "x", "issue_types": names[: len(names) // 2 + 1]},
                               {"theme_id": "T2", "name": "Test theme two", "description": "y", "issue_types": names[len(names) // 2 + 1:]}] if len(names) > 1 else
                              [{"theme_id": "T1", "name": "Only theme", "description": "x", "issue_types": names}]}
        if "For each theme you are given computed statistics" in system:
            out = []
            for blk in user.split("THEME ")[1:]:
                tid = blk.split(":")[0]; ids = re.findall(r"\[([A-Z]{2}-\d{4})\]", blk)
                out.append({"theme_id": tid, "description": "test", "main_customer_problems": ["p"], "representative_review_ids": ids[:2]})
            return {"narratives": out}
        if "answer ONE research question" in system:
            qid = re.search(r"QUESTION (Q\d)", user).group(1)
            lines = re.findall(r"\[([A-Z]{2}-\d{4})\][^\n]*?quote: ([^\n]+)", user)
            sup = [{"review_id": i, "quote": q[:60]} for i, q in lines[:2]] or [{"review_id": "GP-0001", "quote": "not in package fabricated"}]
            sup.append({"review_id": "GP-0001", "quote": "this quote was never in any review"})
            return {"question_id": qid, "summary": "test", "findings": [{"finding": "f", "supporting": sup}], "evidence_strength": "weak", "evidence_gaps": ["test"]}
        if "INSTEAD of Urban Company" in system:
            lines = re.findall(r"\[([A-Z]{2}-\d{4})\][^\n]*quote: ([^\n]+)", user)
            return {"alternatives": [{"name": "local technician", "type": "local_independent", "used_for": "x", "why_customers_prefer_it": ["cheaper"], "advantages": [], "disadvantages": [],
                                      "service_categories": [], "supporting": [{"review_id": i, "quote": q[:30]} for i, q in lines[:2]]}], "summary": "test"}
        if "product opportunities" in system:
            names = re.findall(r"CLUSTER: ([^|]+) \|", user)
            return {"opportunities": [{"name": "Test opp", "customer_problem": "p", "supporting_segment": None, "why_it_matters_to_customers": "w",
                                       "repeat_booking_link_hypothesis": "h", "suggested_improvement_hypothesis": "s", "impact_score_1_to_5": 3,
                                       "related_clusters": [n.strip() for n in names[:2]], "supporting": []}]}
        raise AssertionError("unrecognised prompt")


def unit_evidence_rules():
    """_postprocess: fabricated quote dropped; explicit class without verified quote downgraded; basis/class mismatch downgraded; valid evidence kept."""
    from . import schemas
    row = {"record_id": "ZZ-0001", "platform": "Test", "source_url": "http://x", "sentiment_label": "Negative", "rating": "1", "review_date": "2026-01-01",
           "service_category": "", "city": "", "text": "The technician never came and I will never use Urban Company again because support was useless for weeks."}
    def mk(**kw):
        base = dict(review_id="ZZ-0001", is_customer_experience=True, return_class="Insufficient Evidence", return_basis="none")
        base.update(kw); return schemas.ReviewExtraction(**base)
    ok = P._postprocess(mk(return_class="Explicit Non-Return", return_basis="stated_will_not_return", return_quote="I will never use Urban Company again"), row)
    assert ok["return_class"] == "Explicit Non-Return" and not ok["dropped_quotes"], ok
    fab = P._postprocess(mk(return_class="Explicit Non-Return", return_basis="stated_will_not_return", return_quote="I quit Urban Company for good"), row)
    assert fab["return_class"] != "Explicit Non-Return" and fab["downgrade_reason"] and fab["dropped_quotes"], fab
    mismatch = P._postprocess(mk(return_class="Explicit Return", return_basis="dissatisfaction", return_quote="support was useless"), row)
    assert mismatch["return_class"] != "Explicit Return" and mismatch["downgrade_reason"], mismatch
    ell = P._postprocess(mk(key_quote="technician never came ... support was useless"), row)
    assert ell["key_quote"] and not ell["dropped_quotes"], ell
    print("evidence-rule unit tests PASSED (fabricated quote dropped; explicit class without verified quote downgraded; basis mismatch downgraded; ellipsis quotes verified)")


def main():
    unit_evidence_rules()
    if TEST_DIR.exists():
        shutil.rmtree(TEST_DIR)
    TEST_DIR.mkdir()
    comp = FakeCompletions()

    def transport(url, headers, payload, timeout):          # fake Cloudflare REST endpoint
        try:
            r = comp.create(messages=payload["messages"])
        except FakeRateLimit:
            return 429, {}, {"success": False, "errors": [{"code": 2001, "message": "Rate limit"}], "result": None}
        return 200, {"cf-ai-neurons": "1.0"}, {"success": True, "errors": [], "result": {"choices": [{"message": {"content": r.choices[0].message.content}, "finish_reason": "stop"}],
                                                                                         "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150, "neurons": 1.0}}}
    llm_mod.time.sleep = lambda s: None                     # no real waiting in the test
    fake = NS(chat=NS(completions=comp))
    llm = CloudflareLLM(TEST_DIR / "cache", transport=transport, tracker=UsageTracker(TEST_DIR / "usage.jsonl"), account="test", token="test-token")
    df, full = data.load_reviews()
    sub = df.head(24)
    print("scope: master", len(full), "analysis base", len(df), "| Insta Help excluded:", int(full.insta_help.sum()))
    P.run_extraction(llm, df, TEST_DIR, limit=24, batch_size=8, progress=lambda s: None)
    recs = P.load_extractions(TEST_DIR)
    assert len(recs) == 24, len(recs)
    assert llm.stats["retries"] == 1, llm.stats
    # fabricated quote dropped, explicit-without-quote downgraded
    bad = [r for r in recs if r["review_id"].endswith("1") and r["dropped_quotes"]]
    assert bad, "fabricated expectation quote should have been dropped"
    down = [r for r in recs if r.get("downgrade_reason")]
    print("quote-verification: fabricated quotes dropped on", len(bad), "records | evidence-standard downgrades:", len(down))
    # resume: second call must not call the API again for finished reviews
    calls_before = fake.chat.completions.calls
    P.run_extraction(llm, df, TEST_DIR, limit=24, batch_size=8, progress=lambda s: None)
    assert fake.chat.completions.calls == calls_before, "resume should skip finished reviews"
    P.run_themes(llm, sub, TEST_DIR, progress=lambda s: None)
    P.run_unmet_needs(llm, sub, TEST_DIR, progress=lambda s: None)
    P.run_behaviour(sub, TEST_DIR)
    P.run_alternatives(llm, sub, TEST_DIR)
    P.run_segments(sub, TEST_DIR)
    qa = P.run_questions(llm, sub, TEST_DIR, progress=lambda s: None)
    P.run_opportunities(llm, sub, TEST_DIR)
    b = P.build_bundle(sub, full, TEST_DIR)
    dropped = sum(a.get("validation", {}).get("citations_dropped_unverifiable", 0) for a in qa["answers"].values())
    print("answers:", {k: v.get("status") for k, v in qa["answers"].items()}, "| unverifiable citations dropped:", dropped)
    assert dropped > 0
    for fn in ["review_extractions.jsonl", "themes.json", "unmet_needs.json", "behaviour.json", "alternatives.json", "segments.json", "question_answers.json", "opportunities.json", "discovery_engine_output.json", "run_manifest.json"]:
        if fn == "alternatives.json" and not (TEST_DIR / fn).exists():
            print("  (no alternatives in the first 24 reviews -> alternatives stage correctly produced nothing)"); continue
        assert (TEST_DIR / fn).exists(), "missing " + fn
    # reproducibility: identical inputs hit the cache, no new API calls
    c0 = fake.chat.completions.calls
    P.run_themes(llm, sub, TEST_DIR, progress=lambda s: None)
    assert fake.chat.completions.calls == c0, "rerun should be served from cache"
    print("plumbing test PASSED | api calls:", fake.chat.completions.calls, "| cache hits:", llm.stats["cache_hits"])
    shutil.rmtree(TEST_DIR)   # synthetic outputs are never kept
    print("synthetic test outputs deleted")


if __name__ == "__main__":
    sys.exit(main())
