import logging
import os
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

# Configure structured logging before anything else emits a log line.
from .core.logging import configure_logging

configure_logging()

from .core.config import settings
from .core.context import set_request_id, get_request_id
from .core.database import Base, engine, SessionLocal
from .core.ratelimit import limiter
from .routers import (
    auth, users, shifts, operations, analytics, reports, audit,
    notifications, bi, ai, targets, admin,
)
from .services.seed import run_seed
from .services.audit import register_audit_listeners
from .services.scheduler import start_scheduler, shutdown_scheduler
from . import models  # noqa: F401  ensure models are registered on Base.metadata

# Wire the audit-trail session events before any DB session is opened (the
# startup seed below opens one). Capture is no-op-safe with no request context:
# audit_actor is empty during seed, so those writes record a null actor.
register_audit_listeners()

logger = logging.getLogger("app")
access_logger = logging.getLogger("app.access")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Alembic owns the Postgres schema (applied by entrypoint.sh before the app
    # starts). For the sqlite test path there is no migration runner, so create
    # the tables directly here.
    if settings.database_url.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        run_seed(db)
    finally:
        db.close()

    # Start the in-process background scheduler (alert scan + report email).
    # Single uvicorn worker -> exactly one scheduler. If you ever run multiple
    # workers/replicas, set SCHEDULER_ENABLED=false on all but one (see
    # services/scheduler.py) so daily jobs don't run multiple times.
    scheduler = start_scheduler()
    try:
        yield
    finally:
        # Stop the scheduler cleanly on app shutdown.
        if scheduler is not None:
            shutdown_scheduler()


app = FastAPI(title=settings.project_name, lifespan=lifespan)

# --- Rate limiting (slowapi) ---
# Register the shared limiter on app.state (slowapi reads it from there) and add
# the middleware that enforces per-route @limiter.limit(...) decorators. The
# RateLimitExceeded handler below returns a clean 429. In-memory storage is fine
# for this single-host deployment.
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# Origins come from settings (CORS_ORIGINS); default "*" keeps the LAN-open
# behaviour. The CORS spec forbids combining a "*" origin with credentialed
# requests (browsers reject it), so we only enable credentials when an explicit
# allow-list is configured. Auth here uses Authorization: Bearer headers, not
# cookies, so the wildcard path does not need credentials anyway.
_cors_origins = settings.cors_origin_list
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    request_id = uuid.uuid4().hex
    set_request_id(request_id)
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        # Let the global exception handler build the response; just log timing.
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        access_logger.exception(
            "request failed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": 500,
                "duration_ms": duration_ms,
                "request_id": request_id,
            },
        )
        raise
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    access_logger.info(
        "request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": duration_ms,
            "request_id": request_id,
        },
    )
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = get_request_id()
    logger.error(
        "unhandled exception",
        exc_info=exc,
        extra={"request_id": request_id, "path": request.url.path},
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "internal_error",
                "message": "Internal server error",
                "request_id": request_id,
            }
        },
    )


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    """Return a clean 429 (in our error envelope) when a route limit is hit.
    Replaces slowapi's default handler so the response shape matches the rest of
    the API and carries the request id."""
    request_id = get_request_id()
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "error": {
                "code": "rate_limited",
                "message": "Too many requests, please slow down and try again shortly.",
                "request_id": request_id,
            }
        },
    )


def _sanitize_validation_errors(exc: RequestValidationError) -> list[dict]:
    """Build a JSON-serializable details list from a RequestValidationError.

    A bare ``ValueError`` raised inside a Pydantic field_validator (e.g.
    UserCreate username "   " -> "username must not be blank") surfaces in
    ``exc.errors()`` with a ``ctx`` dict that carries the original ValueError
    OBJECT — which json.dumps cannot serialize, so naively embedding
    ``exc.errors()`` makes THIS handler 500. We therefore emit only the safe,
    stable fields (loc/msg/type) and, if present, a stringified ctx, so the
    response is always serializable and the client still gets a useful 422.
    """
    details: list[dict] = []
    for err in exc.errors():
        loc = err.get("loc", ())
        clean = {
            # loc may contain non-str items (ints for list indices) — all JSON-safe.
            "loc": list(loc),
            "msg": str(err.get("msg", "")),
            "type": str(err.get("type", "")),
        }
        ctx = err.get("ctx")
        if ctx is not None:
            # Stringify every ctx value; the offending one is usually the
            # ValueError instance itself.
            clean["ctx"] = {k: str(v) for k, v in ctx.items()}
        details.append(clean)
    return details


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = get_request_id()
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "validation_error",
                "message": "Request validation failed",
                "request_id": request_id,
                "details": _sanitize_validation_errors(exc),
            }
        },
    )


# --- API versioning ---
# All business/auth/analytics/report/audit/notifications/bi endpoints are served
# under /api/v1/... (each router carries its own /api/v1/* prefix). This is the
# v1 contract; future breaking changes go to a new /api/v2 set of routers rather
# than mutating these. /api/v1/ingest/* is reserved for the future machine-data
# collector. NOTE: GET /api/health and /api/health/ready below stay UNVERSIONED
# on purpose — they are infrastructure probes, not part of the versioned API.
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(shifts.router)
app.include_router(operations.router)
app.include_router(analytics.router)
app.include_router(reports.router)
app.include_router(audit.router)
app.include_router(notifications.router)
app.include_router(bi.router)
app.include_router(ai.router)
app.include_router(targets.router)
app.include_router(admin.router)


@app.get("/api/health")
def health():
    """Cheap liveness check — does not touch the database."""
    return {"status": "ok", "app": settings.project_name}


@app.get("/api/health/ready")
def health_ready():
    """Readiness check — verifies the database answers a trivial query."""
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as exc:  # pragma: no cover - exercised only on DB failure
        logger.warning(
            "readiness check failed",
            extra={"request_id": get_request_id(), "reason": str(exc)},
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "reason": "database unavailable"},
        )
    finally:
        db.close()


# ---- Serve the built frontend (single-server deployment) ----
STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        # Let API 404s behave normally
        if full_path.startswith("api/"):
            return {"detail": "Not Found"}
        index = os.path.join(STATIC_DIR, "index.html")
        if os.path.exists(index):
            return FileResponse(index)
        return {"detail": "Frontend not built"}
