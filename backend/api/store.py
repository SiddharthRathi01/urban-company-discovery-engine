"""Read-only access to the precomputed analysis (analysis/*.json). Files are loaded once, cached by modification time, and never written."""
import json
import logging
import threading

from . import settings
from .responses import ApiError

log = logging.getLogger("discovery.store")

FILES = ["overview", "themes", "findings", "questions", "behaviour", "alternatives", "segments", "unmet_needs", "opportunities", "evidence", "limitations", "reviews", "trust", "manifest"]


class AnalysisStore:
    def __init__(self, directory=None):
        self.dir = directory or settings.ANALYSIS_DIR
        self._cache, self._lock = {}, threading.Lock()
        self._derived = {}

    def _load(self, name):
        path = self.dir / f"{name}.json"
        if not path.exists():
            raise ApiError(503, "analysis_unavailable", f"Precomputed analysis file '{name}.json' is missing.", {"file": name + ".json"})
        mtime = path.stat().st_mtime
        with self._lock:
            hit = self._cache.get(name)
            if hit and hit[0] == mtime:
                return hit[1]
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                log.error("cannot read %s: %s", path, exc)
                raise ApiError(503, "analysis_unreadable", f"Precomputed analysis file '{name}.json' cannot be read.", {"file": name + ".json"})
            self._cache[name] = (mtime, data)
            self._derived = {}
            log.info("loaded %s (%d bytes)", path.name, path.stat().st_size)
            return data

    def preload(self):
        ok = True
        for n in FILES:
            try:
                self._load(n)
            except ApiError as exc:
                ok = False
                log.error("preload failed: %s", exc.message)
        return ok

    def get(self, name):
        return self._load(name)

    # ---- derived indexes (rebuilt when any file changes) ------------------------------------------------
    def _idx(self, key, build):
        self._load("reviews"); self._load("evidence")
        if key not in self._derived:
            self._derived[key] = build()
        return self._derived[key]

    def reviews(self):
        return self._load("reviews")["reviews"]

    def review_by_id(self):
        return self._idx("review_by_id", lambda: {r["record_id"]: r for r in self.reviews()})

    def evidence(self):
        return self._load("evidence")["evidence"]

    def evidence_by_id(self):
        return self._idx("evidence_by_id", lambda: {e["evidence_id"]: e for e in self.evidence()})

    def evidence_by_review(self):
        def build():
            d = {}
            for e in self.evidence():
                d.setdefault(e["review_id"], []).append(e["evidence_id"])
            return d
        return self._idx("evidence_by_review", build)

    def expand_evidence(self, ids):
        by = self.evidence_by_id()
        return [by[i] for i in ids if i in by]

    def manifest(self):
        return self._load("manifest")


store = AnalysisStore()
