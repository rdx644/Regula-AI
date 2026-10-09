from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
import redis.asyncio as redis

from app.core.config import settings
from app.core.middleware import RateLimitMiddleware, RequestIDMiddleware, SecurityHeadersMiddleware, UploadSizeLimitMiddleware
from app.core.exceptions import register_exception_handlers
from app.core.monitoring import setup_logging, get_logger
from app.db.session import SessionLocal
from app.api.api import api_router

embedded_worker = None

# Setup structured logging
setup_logging()
logger = get_logger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=None if settings.ENVIRONMENT.lower() in {"demo", "staging", "production"} else f"{settings.API_V1_STR}/openapi.json",
    docs_url=None if settings.ENVIRONMENT.lower() in {"demo", "staging", "production"} else "/docs",
    redoc_url=None if settings.ENVIRONMENT.lower() in {"demo", "staging", "production"} else "/redoc",
    description="Agentic Regulatory Compliance & Control Intelligence Platform"
)

# Custom middleware (order matters - first added = outermost)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(UploadSizeLimitMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)
rate_limit_client = None
if settings.ENABLE_RATE_LIMITING and settings.REDIS_URL:
    rate_limit_client = redis.from_url(settings.REDIS_URL, encoding="utf-8", decode_responses=True)
app.add_middleware(
    RateLimitMiddleware,
    redis_client=rate_limit_client,
    fail_closed=settings.ENVIRONMENT.lower() in {"demo", "staging", "production"},
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
register_exception_handlers(app)

# Include API Router
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.on_event("startup")
async def startup_event():
    global embedded_worker
    if settings.RUN_EMBEDDED_WORKER:
        import platform
        import os
        from uuid import uuid4
        from app.services.queue import JobQueue, Worker
        from app.workers.handlers import get_handlers

        queue = JobQueue()
        embedded_worker = Worker(
            queue=queue,
            worker_id=f"regulaai-worker-{settings.ENVIRONMENT}-{platform.node()}-{os.getpid()}-{uuid4().hex[:8]}",
            handlers=get_handlers(),
            poll_interval=1.0,
            max_concurrent=settings.WORKER_MAX_CONCURRENT,
        )
        await embedded_worker.start()
        logger.info("Embedded demo worker started", extra={"event": "worker_started"})
    logger.info("Application starting up", extra={"event": "startup"})


@app.on_event("shutdown")
async def shutdown_event():
    if embedded_worker:
        await embedded_worker.stop()
    if rate_limit_client:
        await rate_limit_client.aclose()
    from app.services.queue import close_queue
    await close_queue()
    logger.info("Application shutting down", extra={"event": "shutdown"})


@app.get("/api/health/live")
async def health_live():
    """Liveness probe: verifies process is running."""
    return {"status": "ok"}


@app.get("/api/health")
async def health_check():
    """
    Readiness & Health probe: verifies database connectivity and platform state.
    """
    db_status = "unknown"
    error_msg = None
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            db_status = "connected"
        finally:
            db.close()
    except Exception:
        db_status = "disconnected"
        # Database exceptions may include the connection URL and credentials.
        logger.error("Database readiness check failed", extra={"event": "health_check_failed"})
        error_msg = "Database connection is unavailable."

    redis_status, storage_status, worker_status = "not_configured", "development_local", "not_verified"
    if settings.REDIS_URL:
        client = redis.from_url(settings.REDIS_URL)
        try:
            await client.ping()
            redis_status = "connected"
            async for _ in client.scan_iter(match="regulaai:worker:*", count=10):
                worker_status = "healthy"
                break
        except Exception:
            redis_status = "disconnected"
        finally:
            await client.aclose()
    if settings.STORAGE_BACKEND == "s3":
        from app.services.storage import get_private_storage
        from starlette.concurrency import run_in_threadpool
        try:
            await run_in_threadpool(get_private_storage().verify_configuration)
            storage_status = "private_encrypted_versioned"
        except Exception:
            storage_status = "unavailable_or_unsafe"
    environment = settings.ENVIRONMENT.lower()
    production = environment in {"staging", "production"}
    demo = environment == "demo"
    protected_services_ready = redis_status == "connected" and worker_status == "healthy"
    if production:
        protected_services_ready = protected_services_ready and storage_status == "private_encrypted_versioned"
    ready = db_status == "connected" and (not (production or demo) or protected_services_ready)
    overall_status = "ok" if ready else "degraded"
    status_code = status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content={
            "status": overall_status,
            "db": db_status,
            "redis": redis_status,
            "storage": storage_status,
            "worker": worker_status,
            "environment": settings.ENVIRONMENT,
            "project": settings.PROJECT_NAME,
            "error": error_msg,
        },
    )
