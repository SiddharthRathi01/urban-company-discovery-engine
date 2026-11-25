import hashlib
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["UPLOAD_DIR"] = tempfile.mkdtemp(prefix="discovery_uploads_")   # must be set before the API is imported
os.environ["LLM_DATA_DIR"] = tempfile.mkdtemp(prefix="discovery_llm_")        # tests never touch the real usage ledger or cache
os.environ["GOLDEN_DIR"] = tempfile.mkdtemp(prefix="discovery_golden_")
os.environ["UPLOAD_PROCESSOR"] = "none"                                       # offline tests must never call the real LLM
os.environ["PUBLIC_MODE"] = "0"                                               # the older stored-upload tests need the write endpoints; tests/test_public_site.py switches the lock on
os.environ.setdefault("LOG_LEVEL", "WARNING")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@pytest.fixture(scope="session")
def client():
    from backend.api.main import app
    with TestClient(app) as c:
        yield c


def analysis_fingerprint():
    h = hashlib.sha256()
    for p in sorted((ROOT / "analysis").glob("*.json")):
        h.update(p.name.encode()); h.update(p.read_bytes())
    return h.hexdigest()


@pytest.fixture(scope="session")
def fingerprint():
    return analysis_fingerprint
