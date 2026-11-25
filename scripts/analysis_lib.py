"""Helpers for building the precomputed Step 2 analysis: verbatim quote extraction + evidence registry + JSON-safe conversion."""
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

import sys
sys.path.insert(0, "scripts")
from step2_common import ISSUE_RE
from step2_codes2 import NEED_RE

ROOT = Path(__file__).resolve().parent.parent
OUTDIR = ROOT / "analysis"
I = re.I | re.S
SENT_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def py(o):
    """Convert numpy/pandas scalars/containers to plain JSON types."""
    if isinstance(o, dict):
        return {str(k): py(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)):
        return [py(v) for v in o]
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if np.isnan(o) else round(float(o), 4)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, float):
        return None if o != o else round(o, 4)
    return o


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


def pct(n, d, nd=1):
    return round(100.0 * n / d, nd) if d else 0.0


class Evidence:
    """Registry of verbatim quotes. A quote is only registered if it is an exact substring of the review text (whitespace-normalised)."""

    def __init__(self, rows_by_id):
        self.rows = rows_by_id
        self.items = {}      # evidence_id -> dict
        self._index = {}     # (review_id, quote) -> evidence_id
        self.failures = []

    def _rx(self, pat):
        if pat in ISSUE_RE:
            return ISSUE_RE[pat]
        if pat in NEED_RE:
            return NEED_RE[pat]
        return re.compile(pat, I)

    def sentence(self, text, pat, lo=30, hi=270):
        rx = self._rx(pat)
        parts = [norm(p) for p in SENT_SPLIT.split(text) if norm(p)]
        for p in parts:
            if rx.search(p) and lo <= len(p) <= hi:
                return p
        for p in parts:                         # a long sentence: cut around the match without altering words
            m = rx.search(p)
            if m and len(p) > hi:
                a = max(0, m.start() - 110); z = min(len(p), m.end() + 110)
                a = p.rfind(" ", 0, a) + 1 if a > 0 else 0
                z = p.find(" ", z) if p.find(" ", z) > 0 else len(p)
                return ("… " if a > 0 else "") + p[a:z] + (" …" if z < len(p) else "")
        for p in parts:                         # matching sentence shorter than the preferred minimum (e.g. "Will definitely book again")
            if rx.search(p) and len(p) <= hi:
                return p
        full = norm(text)                       # match spans a sentence split (e.g. "Rs. 2,200"): window on the whole text
        m = rx.search(full)
        if m:
            a = max(0, m.start() - 100); z = min(len(full), m.end() + 100)
            a = full.rfind(" ", 0, a) + 1 if a > 0 else 0
            z = full.find(" ", z) if full.find(" ", z) > 0 else len(full)
            return ("… " if a > 0 else "") + full[a:z] + (" …" if z < len(full) else "")
        return None

    def add(self, rid, pat, supports, lo=30, hi=270):
        r = self.rows.get(rid)
        if r is None:
            self.failures.append((rid, str(pat)[:60], "review id not in analysis dataset")); return None
        q = self.sentence(r["text"], pat, lo, hi)
        if not q:
            self.failures.append((rid, str(pat)[:60], "pattern not found in review text")); return None
        core = q.replace("… ", "").replace(" …", "")
        if norm(core) not in norm(r["text"]):
            self.failures.append((rid, str(pat)[:60], "quote not verbatim")); return None
        key = (rid, q)
        if key not in self._index:
            eid = f"EV{len(self.items) + 1:03d}"
            self._index[key] = eid
            self.items[eid] = {"evidence_id": eid, "review_id": rid, "original_review_id": r["original_review_id"], "quote": q,
                               "source": r["platform"], "source_url": r["source_url"], "review_date": r["review_date"] or None,
                               "rating": r["rating"] or None, "sentiment_label": r["sentiment_label"],
                               "service_category": r["service_category"] or None, "city": r["city"] or None,
                               "review_text": r["text"], "supports": []}
        eid = self._index[key]
        for s in ([supports] if isinstance(supports, str) else supports):
            if s not in self.items[eid]["supports"]:
                self.items[eid]["supports"].append(s)
        return eid

    def many(self, specs, supports):
        return [e for e in (self.add(rid, pat, supports) for rid, pat in specs) if e]

    def auto(self, df, pat, supports, k=3, prefer=("Negative", "Mixed"), lo=70, hi=230, exclude=()):
        """Pick up to k illustrative quotes from df rows whose text matches pat; round-robin across sources; deterministic."""
        rx = self._rx(pat)
        out, used_ids = [], set(exclude)
        order = {p: i for i, p in enumerate(prefer)}
        cand = df.copy()
        cand["_pref"] = cand.sentiment_label.map(lambda s: order.get(s, 9))
        by = {}
        for r in cand.sort_values(["_pref", "record_id"]).itertuples():
            if r.record_id in used_ids:
                continue
            s = self.sentence(r.text, pat, lo, hi)
            if s and len(s) >= lo and not s.startswith("…"):
                by.setdefault(r.platform, []).append((r.record_id, s))
        i = 0
        plats = sorted(by, key=lambda p: -len(by[p]))
        while len(out) < k and any(i < len(by[p]) for p in plats):
            for p in plats:
                if i < len(by[p]) and len(out) < k:
                    rid, s = by[p][i]
                    e = self.add(rid, re.escape(s[:60]), supports, lo=0, hi=400)
                    if e:
                        out.append(e)
            i += 1
        return out


def _add_span(self, rid, supports, maxlen=300):
    """Register the opening of the review (verbatim, cut at a word boundary) as evidence."""
    r = self.rows.get(rid)
    if r is None:
        self.failures.append((rid, "<span>", "review id not in analysis dataset")); return None
    full = norm(r["text"])
    q = full if len(full) <= maxlen else full[:full.rfind(" ", 0, maxlen)] + " …"
    key = (rid, q)
    if key not in self._index:
        eid = f"EV{len(self.items) + 1:03d}"
        self._index[key] = eid
        self.items[eid] = {"evidence_id": eid, "review_id": rid, "original_review_id": r["original_review_id"], "quote": q,
                           "source": r["platform"], "source_url": r["source_url"], "review_date": r["review_date"] or None,
                           "rating": r["rating"] or None, "sentiment_label": r["sentiment_label"],
                           "service_category": r["service_category"] or None, "city": r["city"] or None,
                           "review_text": r["text"], "supports": []}
    eid = self._index[key]
    for s in ([supports] if isinstance(supports, str) else supports):
        if s not in self.items[eid]["supports"]:
            self.items[eid]["supports"].append(s)
    return eid


Evidence.add_span = _add_span
