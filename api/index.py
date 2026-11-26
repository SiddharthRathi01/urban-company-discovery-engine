"""Vercel entry point: the whole FastAPI app (the API, the file downloads and the temporary analysis) runs as one Python function."""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from backend.api.main import app as _api
    _err = None
except Exception:  # pragma: no cover - only reached when the deployment itself is broken
    _api, _err = None, traceback.format_exc()[-3000:]


async def _startup_error(scope, receive, send):
    """Shows why the API could not start (a traceback of the import; it contains no secrets)."""
    if scope["type"] != "http":
        return
    await send({"type": "http.response.start", "status": 500, "headers": [(b"content-type", b"text/plain; charset=utf-8")]})
    await send({"type": "http.response.body", "body": ("The API could not start:\n\n" + str(_err)).encode()})


app = _api if _api is not None else _startup_error   # Vercel looks for a top-level `app`
