"""API middleware for authentication, rate limiting, and logging."""

import time

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings
from app.utils.logger import logger


class APIKeyMiddleware(BaseHTTPMiddleware):
    """API Key authentication middleware."""

    EXEMPT_PATHS = {"/", "/health", "/docs", "/redoc", "/openapi.json"}

    async def dispatch(self, request: Request, call_next):
        # Skip authentication for exempt paths
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Skip authentication for static files
        if request.url.path.startswith("/static"):
            return await call_next(request)

        # Check API key
        api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")

        if not api_key:
            return JSONResponse(
                status_code=401,
                content={"code": "MISSING_API_KEY", "message": "请提供 API Key"},
            )

        if api_key != settings.API_KEY:
            return JSONResponse(
                status_code=401,
                content={"code": "INVALID_API_KEY", "message": "API Key 无效"},
            )

        return await call_next(request)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Request logging middleware with timing."""

    async def dispatch(self, request: Request, call_next):
        # Record start time
        start_time = time.time()

        # Generate request ID
        request_id = f"{int(start_time * 1000)}"

        # Log request
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={"request_id": request_id}
        )

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Log response
        logger.info(
            f"Request completed: {request.method} {request.url.path} "
            f"[{response.status_code}] {duration_ms:.1f}ms",
            extra={"request_id": request_id}
        )

        # Add timing header
        response.headers["X-Process-Time"] = f"{duration_ms:.1f}ms"

        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiting middleware.

    Limits based on:
    - IP address for unauthenticated requests
    - API key for authenticated requests
    """

    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self._requests: dict[str, list[float]] = {}

    def _get_client_id(self, request: Request) -> str:
        """Get client identifier for rate limiting."""
        # Use API key if provided
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"key:{api_key[:8]}"

        # Fall back to IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "unknown"

        return f"ip:{client_ip}"

    def _cleanup_old_requests(self, client_id: str, now: float) -> None:
        """Remove requests older than 1 minute."""
        if client_id in self._requests:
            cutoff = now - 60.0
            self._requests[client_id] = [
                t for t in self._requests[client_id] if t > cutoff
            ]

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path == "/health":
            return await call_next(request)

        client_id = self._get_client_id(request)
        now = time.time()

        # Cleanup old requests
        self._cleanup_old_requests(client_id, now)

        # Check rate limit
        if client_id not in self._requests:
            self._requests[client_id] = []

        if len(self._requests[client_id]) >= self.requests_per_minute:
            logger.warning(f"Rate limit exceeded for {client_id}")
            return JSONResponse(
                status_code=429,
                content={
                    "code": "RATE_LIMIT_EXCEEDED",
                    "message": "请求过于频繁，请稍后再试",
                },
                headers={"Retry-After": "60"},
            )

        # Record request
        self._requests[client_id].append(now)

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        remaining = max(0, self.requests_per_minute - len(self._requests[client_id]))
        response.headers["X-RateLimit-Limit"] = str(self.requests_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response
