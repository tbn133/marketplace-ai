"""API middleware — project isolation, request logging, timing."""

from __future__ import annotations

import time

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.infrastructure.logging import get_logger

logger = get_logger("api")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs every request with method, path, status, and duration."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = (time.monotonic() - start) * 1000

        logger.info(
            "%s %s → %d (%.1fms)",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        response.headers["X-Request-Duration-Ms"] = f"{duration_ms:.1f}"
        return response


class ProjectIsolationMiddleware(BaseHTTPMiddleware):
    """Ensures project_id is present on all mutating requests."""

    EXEMPT_PATHS = {"/health", "/docs", "/openapi.json", "/redoc"}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # For POST/PUT/PATCH, validate project_id in JSON body
        if request.method in ("POST", "PUT", "PATCH"):
            try:
                body = await request.json()
                if isinstance(body, dict) and "project_id" not in body:
                    from fastapi.responses import JSONResponse
                    return JSONResponse(
                        status_code=400,
                        content={"detail": "Missing required field: project_id"},
                    )
            except Exception:
                pass  # Let the route handler deal with malformed bodies

        # For GET/DELETE, project_id should be in query params (validated by routes)
        return await call_next(request)
