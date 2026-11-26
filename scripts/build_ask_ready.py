"""Prepares the Ask page's ready answers: the suggested questions shown on the page and the short summaries of the eight discovery questions.
They are written by the AI once, here, and saved to analysis/ask_ready.json, so on the website they open instantly. Typed questions still go to the AI live.
Needs the Cloudflare keys in .env. Run:  .python/python.exe scripts/build_ask_ready.py   (about 15 AI requests)"""
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["ASK_READY_DISABLED"] = "1"            # always ask the AI here, never the previous ready file
os.environ.setdefault("PUBLIC_MODE", "1")

from fastapi.testclient import TestClient  # noqa: E402

from backend.api.main import app  # noqa: E402
from backend.api.routers.llm import _norm_q  # noqa: E402

ask_page = (ROOT / "frontend" / "src" / "pages" / "AskPage.tsx").read_text(encoding="utf-8")
TRY = json.loads(re.search(r"const TRY = (\[.*?\]);", ask_page, re.S).group(1))   # the suggested questions exactly as the page shows them

out = {"note": "Written by the AI ahead of time from the reviews; every quote checked to be verbatim. Rebuild with scripts/build_ask_ready.py after the analysis or prompts change.",
       "answers": {}, "briefs": {}}
with TestClient(app) as c:
    for q in TRY:
        r = c.get("/api/v1/ask/answer", params={"q": q})
        r.raise_for_status()
        d = r.json()["data"]
        if not d.get("answer"):
            sys.exit(f"no answer for suggested question: {q}")
        d.pop("usage", None)
        out["answers"][_norm_q(q)] = d
        print("answer:", q, "->", d["headline"])
    for qid in [x["question_id"] for x in c.get("/api/v1/questions").json()["data"]]:
        r = c.get(f"/api/v1/questions/{qid}/brief")
        r.raise_for_status()
        out["briefs"][qid] = r.json()["data"]
        print("brief:", qid, "->", out["briefs"][qid]["headline"])
(ROOT / "analysis" / "ask_ready.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("written analysis/ask_ready.json:", len(out["answers"]), "answers,", len(out["briefs"]), "briefs")
