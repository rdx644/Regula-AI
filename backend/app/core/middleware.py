import contextvars
import time
import re
from typing import Callable
from uuid import uuid4

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.monitoring import get_logger


# Context variable for request ID (used in exception handlers)
request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        if not re.fullmatch(r"[A-Za-z0-9-]{1,64}", request_id):
            request_id = str(uuid4())
        request.state.request_id = request_id
        request_id_ctx.set(request_id)
        
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        from app.core.metrics import observe
        observe(getattr(request.scope.get("route"), "path", "unmatched"), request.method, response.status_code, process_time)
        
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{process_time:.4f}"
        get_logger(__name__).info("HTTP request completed", extra={"request_id": request_id,
            "route": getattr(request.scope.get("route"), "path", "unmatched"), "method": request.method,
            "status_code": response.status_code, "latency_ms": round(process_time * 1000, 2)})
        
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, redis_client=None, fail_closed: bool = False):
        super().__init__(app)
        self.redis_client = redis_client
        self.fail_closed = fail_closed
        self.default_limit = settings.RATE_LIMIT_REQUESTS_PER_MINUTE
        self.window = 60

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self.redis_client:
            if self.fail_closed:
                return JSONResponse(
                    status_code=503,
                    content={"detail": "Request protection is temporarily unavailable."},
                    headers={"Retry-After": str(self.window)},
                )
            return await call_next(request)

        client_ip = request.client.host if request.client else "unknown"
        limits = [(f"regulaai:rate:{client_ip}:all", self.default_limit)]
        if request.url.path == f"{settings.API_V1_STR}/auth/login/access-token":
            limits.append((f"regulaai:rate:{client_ip}:login", settings.LOGIN_RATE_LIMIT_PER_MINUTE))
        if request.method == "POST" and any(marker in request.url.path for marker in ("/process", "/run", "/analyze", "/detect", "/extract-", "/validate", "/retry", "/cross-regulation", "/contradiction")):
            limits.append((f"regulaai:rate:{client_ip}:agent", settings.AGENT_RATE_LIMIT_PER_MINUTE))

        try:
            current_values = []
            for key, limit in limits:
                current = await self.redis_client.incr(key)
                if current == 1:
                    await self.redis_client.expire(key, self.window)
                current_values.append((current, limit))
        except Exception:
            logger = get_logger(__name__)
            logger.error("Rate-limit store unavailable", extra={"event": "rate_limit_store_unavailable"})
            if self.fail_closed:
                return JSONResponse(
                    status_code=503,
                    content={"detail": "Request protection is temporarily unavailable."},
                    headers={"Retry-After": str(self.window)},
                )
            return await call_next(request)

        blocked = next(((current, limit) for current, limit in current_values if current > limit), None)
        if blocked:
            _, limit = blocked
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Try again later."},
                headers={
                    "Retry-After": str(self.window),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(self.window),
                },
            )

        current, limit = current_values[0]
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(max(0, limit - current))
        response.headers["X-RateLimit-Reset"] = str(self.window)
        return response


class UploadSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversized/missing-length uploads before multipart parsing buffers them."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method == "POST" and request.url.path.endswith("/file"):
            content_length = request.headers.get("content-length")
            if content_length is None:
                return JSONResponse(status_code=411, content={"detail": "Content-Length is required for document uploads."})
            try:
                request_size = int(content_length)
            except ValueError:
                return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length."})
            # Multipart framing and filename metadata are not part of the source-byte limit.
            if request_size > settings.MAX_UPLOAD_BYTES + 1024 * 1024:
                return JSONResponse(status_code=413, content={"detail": "Document exceeds the upload size limit."})
        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' https:; "
            "frame-ancestors 'none';"
        )
        
        if settings.ENVIRONMENT.lower() in {"production", "staging"}:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response


class AuditLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.time()
        request_id = getattr(request.state, "request_id", str(uuid4()))
        
        # Skip audit for health checks
        if request.url.path in ["/api/health", "/api/health/live"]:
            return await call_next(request)
        
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # In production, this would write to audit log
        # For now, we just add timing headers
        response.headers["X-Response-Time"] = f"{process_time:.4f}"
        
        return response
