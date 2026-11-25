"""Vercel entry point: the whole FastAPI app (the API, the file downloads and the temporary analysis) runs as one Python function."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.api.main import app  # noqa: E402,F401  (Vercel looks for `app`)
