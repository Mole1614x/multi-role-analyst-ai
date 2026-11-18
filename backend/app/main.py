from contextlib import asynccontextmanager
from time import monotonic
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy.exc import SQLAlchemyError

from app.api import analysis, auth, datasets, projects
from app.core.config import settings
from app.core.observability import latency, log, requests
from app.core.queue_metrics import queue_metrics
from app.db.session import check_db
from app.services import jobs as job_service


@asynccontextmanager
async def lifespan(_app: FastAPI):
    with job_service.local_execution():
        yield


app = FastAPI(
    title="Analyst Workspace API",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)
for api in (auth.router, projects.router, datasets.router, analysis.router, analysis.public_router):
    app.include_router(api, prefix="/api")


@app.middleware("http")
async def request_policy(request: Request, call_next):
    request_id = str(uuid4())
    start = monotonic()
    config = settings()
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        browser_site = request.headers.get("sec-fetch-site")
        media = request.headers.get("content-type", "")
        length = request.headers.get("content-length")
        maximum = config.max_upload_bytes + 70_000 if media.startswith("multipart/") else 160_000
        if (
            origin is not None and origin.rstrip("/") != config.origin.rstrip("/")
        ) or browser_site == "cross-site":
            response = JSONResponse(
                {"detail": "Requests must come from the configured workspace origin."}, status_code=403
            )
        elif length is not None and (not length.isdigit() or int(length) > maximum):
            response = JSONResponse({"detail": "The request exceeds the allowed size."}, status_code=413)
        elif length is None and request.headers.get("transfer-encoding"):
            response = JSONResponse({"detail": "A request length is required."}, status_code=411)
        else:
            response = await call_next(request)
    else:
        response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    requests.labels(request.method, response.status_code).inc()
    latency.observe(monotonic() - start)
    log("http_request", request_id=request_id, method=request.method, status=response.status_code)
    return response


@app.exception_handler(RequestValidationError)
async def invalid_request(_request, error):
    fields = [str(item["loc"][-1]) for item in error.errors() if item["loc"]]
    return JSONResponse(
        {"detail": "Check the request fields: " + ", ".join(dict.fromkeys(fields))}, status_code=422
    )


@app.exception_handler(Exception)
async def internal_error(_request, error):
    log("internal_error", error_type=type(error).__name__)
    return JSONResponse({"detail": "The request could not be completed."}, status_code=500)


@app.get("/api/health/live", tags=["health"])
def live():
    return {"status": "alive"}


@app.get("/health", include_in_schema=False)
@app.get("/api/health/ready", tags=["health"])
def ready():
    try:
        check_db()
        config = settings()
        if config.task_backend == "celery" and not config.broker_url:
            raise HTTPException(503, "A Redis broker is required for background jobs.")
        redis_urls = [] if config.task_backend == "local" else [config.redis_url]
        if config.task_backend == "celery" and config.broker_url.startswith(
            ("redis://", "rediss://", "unix://")
        ):
            redis_urls.append(config.broker_url)
        for url in dict.fromkeys(filter(None, redis_urls)):
            with Redis.from_url(url, socket_connect_timeout=2, socket_timeout=2) as client:
                client.ping()
    except (SQLAlchemyError, RedisError) as exc:
        raise HTTPException(503, "A required service is unavailable.") from exc
    return {"status": "ready"}


@app.get("/docs", include_in_schema=False)
def docs():
    return RedirectResponse("/api/docs")


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(generate_latest() + queue_metrics(), media_type=CONTENT_TYPE_LATEST)
