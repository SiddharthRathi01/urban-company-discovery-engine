"""Vercel entry point: the whole FastAPI app (the API, the file downloads and the temporary analysis) runs as one Python function."""
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from backend.api.main import app  # noqa: E402,F401  (Vercel looks for `app`)
except Exception:  # pragma: no cover - only reached when the deployment itself is broken
    _err = traceback.format_exc()[-3000:]

    async def app(scope, receive, send):  # minimal ASGI app that shows why start-up failed (no secrets: a traceback of the import)
        if scope["type"] != "http":
            return
        await send({"type": "http.response.start", "status": 500, "headers": [(b"content-type", b"text/plain; charset=utf-8")]})
        await send({"type": "http.response.body", "body": ("The API could not start:\n\n" + _err).encode()})
