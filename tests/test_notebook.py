"""The Colab notebook must give the same results as the website's analysis on the preloaded dataset, hold no credentials, and never mention the excluded scope."""
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
NB = ROOT / "notebook" / "Urban_Company_Discovery_Engine.ipynb"
pytestmark = pytest.mark.skipif(not NB.exists(), reason="run scripts/build_notebook.py first")


def cells():
    return [c for c in json.loads(NB.read_text(encoding="utf-8"))["cells"]]


def test_notebook_has_no_credentials_and_no_excluded_scope():
    for c in cells():
        s = "".join(c["source"])
        if "PRELOADED_CSV_B64 = (" in s:
            continue
        assert "CLOUDFLARE" not in s.upper() and "API_TOKEN" not in s.upper()
        assert not re.search(r"insta[\s_-]*help", s, re.I)


def test_notebook_reproduces_the_website_analysis(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ns = {"__name__": "__main__"}
    for i, c in enumerate(cells()):
        if c["cell_type"] == "code":
            exec(compile("".join(c["source"]), f"cell{i}", "exec"), ns)
    A = lambda n: json.loads((ROOT / "analysis" / f"{n}.json").read_text(encoding="utf-8"))
    beh, opps, themes = A("behaviour"), A("opportunities"), A("themes")
    df = ns["df"]
    assert len(df) == opps["dataset_reviews"]
    dist = {d["class"]: d["n"] for d in beh["distribution"]}
    assert {k: int(v) for k, v in df.return_class.value_counts().items()} == dist
    assert [(o["id"], o["score"], o["reviews"]) for o in ns["opps"]] == [(o["opportunity_id"], o["prioritisation"]["score"], o["evidence"]["reviews"]) for o in opps["opportunities"]]
    assert {k: int(v) for k, v in ns["th_n"].items()} == {t["theme_id"]: t["review_count"] for t in themes["themes"]}
    assert all((tmp_path / "discovery_output").glob("*_discovery_report.html"))
