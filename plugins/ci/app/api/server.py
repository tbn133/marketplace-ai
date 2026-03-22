"""FastAPI application — receives Container via factory."""

from __future__ import annotations

from fastapi import FastAPI

from app.api.middleware import ProjectIsolationMiddleware, RequestLoggingMiddleware
from app.api.routes import router
from app.container import Container, create_container


def create_app(container: Container | None = None) -> FastAPI:
    app = FastAPI(
        title="Code Intelligence System",
        description="Code indexing, search, and persistent memory API",
        version="0.1.0",
    )

    app.state.container = container or create_container()

    # Middleware (order matters — outermost first)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(ProjectIsolationMiddleware)

    app.include_router(router)
    return app


app = create_app()
