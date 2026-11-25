"""API settings, read from environment variables (optionally a git-ignored .env). No secrets are needed for the precomputed analysis."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
except ImportError:
    pass

ROOT = Path(__file__).resolve().parents[2]
ON_VERCEL = bool(os.environ.get("VERCEL"))
if ON_VERCEL:                                                              # the only writable place on Vercel is /tmp (cleared whenever the function restarts)
    os.environ.setdefault("LLM_DATA_DIR", "/tmp/llm_data")
    os.environ.setdefault("UPLOAD_DIR", "/tmp/uploads")
from backend import config as _bc  # noqa: E402  (also loads .env)

# Public site: the Urban Company analysis and the official golden set are read-only; a visitor's own files are analysed in a temporary session
# (see routers/temp.py) and never stored. Set PUBLIC_MODE=0 only for development, where the stored-upload endpoints are still available.
PUBLIC_MODE = os.environ.get("PUBLIC_MODE", "1") != "0"


def _path(name, default):
    return Path(os.environ.get(name) or default)


API_PREFIX = "/api/v1"
API_VERSION = "1.0"
ANALYSIS_DIR = _path("PRECOMPUTED_ANALYSIS_DIR", ROOT / "analysis")      # precomputed Urban Company analysis: read-only source of truth
UPLOAD_DIR = _path("UPLOAD_DIR", ROOT / "uploads")                        # uploaded CSVs: always separate from analysis/ and output/
GOLDEN_DIR = _path("GOLDEN_DIR", ROOT / "golden")                          # hand-labelled golden sets and their evaluations (a deliverable: not git-ignored)
MAX_GOLDEN_ROWS = int(os.environ.get("MAX_GOLDEN_ROWS", "500"))
MASTER_CSV = _path("MASTER_CSV", ROOT / "output" / "urban_company_reviews_master.csv")
FRONTEND_DIST = _path("FRONTEND_DIST", ROOT / "frontend" / "dist")        # built website, served by the API when present
LOG_LEVEL =os.environ.get("LOG_LEVEL", "INFO").upper()
CORS_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",") if o.strip()]
MAX_UPLOAD_MB = float(os.environ.get("MAX_UPLOAD_MB", "10"))
MAX_UPLOAD_ROWS = int(os.environ.get("MAX_UPLOAD_ROWS", "20000"))
MAX_REVIEW_CHARS = int(os.environ.get("MAX_UPLOAD_REVIEW_CHARS", "20000"))
MIN_REVIEW_CHARS = int(os.environ.get("MIN_UPLOAD_REVIEW_CHARS", "3"))
MAX_ISSUES_STORED = 200                                                    # per-upload cap on stored row issues (totals are always exact)
DEFAULT_PAGE_SIZE = 25
MAX_PAGE_SIZE = 200
UPLOAD_PROCESSOR = (os.environ.get("UPLOAD_PROCESSOR") or ("cloudflare" if _bc.is_configured() else "none")).lower()   # Cloudflare Workers AI whenever credentials are set
