"""FastAPI application for the Customer Discovery Engine. Run:  python -m uvicorn backend.api.main:app --port 8000
Interactive docs: /docs. The precomputed Urban Company analysis (analysis/*.json) is the default source of truth and is read-only."""
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import settings
from .responses import ApiError
from .golden import store as golden_store
from .routers import analysis, golden, insights, llm, reviews, temp, uploads
from .uploads import storage as upload_storage
from .store import store

log = logging.getLogger("discovery.api")


def error_body(code, message, details=None):
    return {"error": {"code": code, "message": message, "details": details}}


@asynccontextmanager
async def lifespan(app):
    ok = store.preload()
    log.info("precomputed analysis preloaded from %s (%s)", settings.ANALYSIS_DIR, "ok" if ok else "INCOMPLETE")
    # On a serverless host the project folder is read-only; none of these housekeeping steps may stop the site from starting.
    for step in (lambda: settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True), upload_storage.recover_interrupted_jobs,
                 lambda: settings.GOLDEN_DIR.mkdir(parents=True, exist_ok=True), golden_store.recover_interrupted):
        try:
            step()
        except OSError as exc:
            log.warning("start-up step skipped: %s", exc)
    yield


def create_app():
    logging.basicConfig(level=settings.LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    app = FastAPI(title="Customer Discovery Engine API", version=settings.API_VERSION, lifespan=lifespan,
                  description="Precomputed Urban Company customer-discovery analysis (Step 2), evidence traceability and a CSV upload foundation. "
                              "Responses: {data, meta}; errors: {error:{code,message,details}}.")
    app.add_middleware(CORSMiddleware, allow_origins=settings.CORS_ORIGINS, allow_methods=["GET", "POST", "DELETE"], allow_headers=["*"])

    @app.middleware("http")
    async def access_log(request: Request, call_next):
        rid, t0 = uuid.uuid4().hex[:8], time.perf_counter()
        try:
            resp = await call_next(request)
        except Exception:
            log.exception("unhandled error rid=%s %s %s", rid, request.method, request.url.path)
            resp = JSONResponse(error_body("internal_error", "Unexpected server error.", {"request_id": rid}), status_code=500)
        resp.headers["X-Request-ID"] = rid
        log.info("rid=%s %s %s -> %s %.0fms", rid, request.method, request.url.path, resp.status_code, 1000 * (time.perf_counter() - t0))
        return resp

    @app.exception_handler(ApiError)
    async def api_error(_, exc: ApiError):
        return JSONResponse(error_body(exc.code, exc.message, exc.details), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_, exc: RequestValidationError):
        details = [{"location": ".".join(str(p) for p in e["loc"]), "message": e["msg"], "type": e["type"]} for e in exc.errors()]
        return JSONResponse(error_body("invalid_request", "The request has invalid parameters.", details), status_code=422)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_, exc: StarletteHTTPException):
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return JSONResponse(error_body(code, str(exc.detail)), status_code=exc.status_code)

    @app.get("/health", tags=["system"], summary="Liveness and analysis availability")
    def health():
        missing = [n for n in ("overview", "themes", "reviews", "evidence", "manifest") if not (settings.ANALYSIS_DIR / f"{n}.json").exists()]
        return {"status": "ok" if not missing else "degraded", "analysis_source": "precomputed", "missing_files": missing, "api_version": settings.API_VERSION}

    for r in (analysis.router, reviews.router, insights.router, llm.router, uploads.router, golden.router, temp.router):
        app.include_router(r, prefix=settings.API_PREFIX)

    # Project files that the website and the AI Evidence Log link to. A fixed list, so no other file can be requested.
    root = settings.ROOT
    downloads = {
        "dataset": (settings.MASTER_CSV, "urban_company_reviews_master.csv", "text/csv"),
        "golden-set": (settings.GOLDEN_DIR / "golden_data_set.csv", "golden_data_set.csv", "text/csv"),
        "notebook": (root / "notebook" / "Urban_Company_Discovery_Engine.ipynb", "Urban_Company_Discovery_Engine.ipynb", "application/x-ipynb+json"),
        "evidence-log.pdf": (root / "docs" / "Urban_Company_AI_Evidence_Log.pdf", "Urban_Company_AI_Evidence_Log.pdf", "application/pdf"),
    }

    @app.get("/downloads/{key}", include_in_schema=False)
    def download(key: str, download: bool = False):
        item = downloads.get(key)
        if not item or not item[0].is_file():
            raise ApiError(404, "file_not_found", "That file is not available.", {"available": list(downloads)})
        path, name, media = item
        inline = key.endswith(".pdf") and not download
        return FileResponse(path, media_type=media, filename=name, content_disposition_type="inline" if inline else "attachment")

    # Serve the built website (frontend/dist) from the same server when it exists, so one command runs the whole product.
    dist = settings.FRONTEND_DIST
    if (dist / "index.html").exists():
        if (dist / "assets").is_dir():
            app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def website(path: str):
            if path.startswith(("api/", "docs", "openapi", "redoc", "health")):
                raise ApiError(404, "not_found", f"No route '/{path}'.")
            target = (dist / path).resolve()
            if path and target.is_file() and dist.resolve() in target.parents:
                return FileResponse(target)
            return FileResponse(dist / "index.html")
        log.info("serving website from %s", dist)
    return app


app = create_app()
