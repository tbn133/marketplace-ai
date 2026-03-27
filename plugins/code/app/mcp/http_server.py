"""HTTP MCP server — streamable HTTP transport + REST API + Web Dashboard.

Run as a central daemon so multiple Claude instances can connect:

    python -m cmd.cli serve-mcp --port 8100 --data-dir ~/.code-intelligence/data

Endpoints:
    /        — Web Dashboard
    /api/    — REST API (search, graph, memory, projects)
    /mcp     — MCP protocol (for Claude instances)
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import HTMLResponse
from starlette.routing import Mount, Route

from app.config import load_config
from app.container import Container, create_container
from app.mcp.server import create_mcp_server

STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"


async def serve_dashboard(request: Request) -> HTMLResponse:
    """Serve the single-page web dashboard."""
    html_path = STATIC_DIR / "index.html"
    if not html_path.exists():
        return HTMLResponse("<h1>Dashboard not found</h1><p>Missing static/index.html</p>", status_code=404)
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


def create_http_app(container: Container | None = None) -> Starlette:
    """Create a Starlette ASGI app with MCP + REST API + Web Dashboard."""
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

    from app.api.server import create_app as create_fastapi_app

    c = container or create_container()

    # MCP server
    mcp_server = create_mcp_server(c)
    session_manager = StreamableHTTPSessionManager(
        app=mcp_server,
        stateless=True,
        json_response=False,
    )

    # REST API (reuse existing FastAPI app, share container)
    fastapi_app = create_fastapi_app(container=c)

    @asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            yield

    return Starlette(
        routes=[
            Route("/", endpoint=serve_dashboard),
            Mount("/api", app=fastapi_app),
            Mount("/mcp", app=session_manager.handle_request),
        ],
        lifespan=lifespan,
    )


def run_http_mcp_server(
    host: str = "127.0.0.1",
    port: int = 8100,
    data_dir: str | None = None,
    log_level: str = "INFO",
) -> None:
    """Start the HTTP MCP server with optional custom data directory."""
    import os

    if data_dir:
        resolved = str(Path(data_dir).expanduser().resolve())
        os.environ["DATA_DIR"] = resolved
        Path(resolved).mkdir(parents=True, exist_ok=True)

    if log_level:
        os.environ["LOG_LEVEL"] = log_level

    config = load_config()
    container = create_container(config)
    app = create_http_app(container)

    uvicorn.run(app, host=host, port=port, log_level=log_level.lower())
