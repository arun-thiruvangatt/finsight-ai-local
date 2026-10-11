import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import redis as redis_lib
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app.api.v1 import api_router as api_v1
from app.core.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import request_id_ctx, setup_logging
from app.core.metrics import HTTP_LATENCY, HTTP_REQUESTS
from app.core.redis import get_redis
from app.db.engine import engine

settings = get_settings()
setup_logging(settings.DEBUG)
log = logging.getLogger("app.access")

TAGS = [
    {"name": "Authentication", "description": "Register, login, token refresh and logout."},
    {"name": "Users", "description": "Profile and (admin) user management."},
    {"name": "Accounts", "description": "Bank, card, cash and other accounts."},
    {"name": "Categories", "description": "Hierarchical income/expense categories."},
    {"name": "Transactions", "description": "Create, search, filter and edit transactions."},
    {"name": "Imports", "description": "CSV import pipeline (background processing)."},
    {"name": "Budgets", "description": "Budgets with usage, projections and warnings."},
    {"name": "Goals", "description": "Savings goals, progress and projections."},
    {"name": "Analytics", "description": "SQL-aggregated spending analytics."},
    {"name": "Insights", "description": "Recurring expenses, anomalies, generated insights and alerts."},
    {"name": "AI", "description": "Natural-language assistant (tool-calling) and document search."},
    {"name": "Documents", "description": "Upload personal finance documents for RAG."},
]


@asynccontextmanager
async def lifespan(_: FastAPI):
    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    log.info("startup", extra={"endpoint": settings.APP_ENV})
    yield
    engine.dispose()


app = FastAPI(
    title=settings.APP_NAME, version="1.0.0", openapi_tags=TAGS, lifespan=lifespan,
    description="AI personal finance intelligence platform. Financial figures are computed by backend "
                "services; the AI layer only selects tools and explains their results.",
    docs_url="/docs", redoc_url="/redoc",
)
register_exception_handlers(app)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins_list, allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Request-ID", "Retry-After"])


@app.middleware("http")
async def observability(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex
    token = request_id_ctx.set(rid)
    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = rid
        return response
    finally:
        duration = time.perf_counter() - started
        route = request.scope.get("route")
        path = getattr(route, "path", "unmatched")  # template -> low-cardinality metric labels
        HTTP_REQUESTS.labels(request.method, path, str(status)).inc()
        HTTP_LATENCY.labels(request.method, path).observe(duration)
        if path not in {"/health", "/metrics"}:
            log.info("request", extra={
                "user_id": getattr(request.state, "user_id", None), "endpoint": request.url.path,
                "method": request.method, "status_code": status, "duration_ms": round(duration * 1000, 1)})
        request_id_ctx.reset(token)


app.include_router(api_v1, prefix="/api/v1")


@app.get("/health", tags=["Health"], summary="Liveness: the process is up")
def health():
    return {"status": "ok"}


@app.get("/ready", tags=["Health"], summary="Readiness: PostgreSQL and Redis reachable")
def ready():
    checks: dict[str, str] = {}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception:  # noqa: BLE001
        checks["postgres"] = "unavailable"
    try:
        get_redis().ping()
        checks["redis"] = "ok"
    except redis_lib.RedisError:
        checks["redis"] = "unavailable"
    ok = all(v == "ok" for v in checks.values())
    return JSONResponse({"status": "ready" if ok else "not_ready", "checks": checks}, status_code=200 if ok else 503)


@app.get("/metrics", include_in_schema=False)
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
