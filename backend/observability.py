"""Structured logging, request IDs, security headers and a small in-memory
rate limiter.

These are intentionally dependency-free so the service stays easy to deploy.
The rate limiter is per process; for a multi-instance deployment use the
platform's edge limiter or Redis (documented in docs/DEPLOYMENT.md).
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections import defaultdict, deque
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id_ctx.get(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    for noisy in ("uvicorn.access",):
        logging.getLogger(noisy).handlers = [handler]


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
        token = request_id_ctx.set(request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        finally:
            request_id_ctx.reset(token)
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.1f}"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        if request.url.path.startswith("/api"):
            logging.getLogger("request").info(
                "%s %s -> %s (%.1f ms)",
                request.method, request.url.path, response.status_code, elapsed_ms,
            )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding-window limit for state-changing / expensive endpoints."""

    def __init__(self, app, per_minute: int = 120):
        super().__init__(app)
        self.per_minute = per_minute
        self.hits: dict[str, deque] = defaultdict(deque)

    async def dispatch(self, request, call_next):
        if request.method == "POST" and request.url.path.startswith("/api"):
            client = request.client.host if request.client else "unknown"
            now = time.time()
            window = self.hits[client]
            while window and now - window[0] > 60:
                window.popleft()
            if len(window) >= self.per_minute:
                from starlette.responses import JSONResponse
                return JSONResponse(
                    {"detail": "Rate limit exceeded. Try again in a minute."},
                    status_code=429,
                    headers={"Retry-After": "60"},
                )
            window.append(now)
        return await call_next(request)
