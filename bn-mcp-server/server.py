"""Build FastMCP app + middleware + uvicorn entry."""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("bn_mcp.server")


def _get_bv_factory():
    from . import context

    def get_bv(view_id: Optional[str] = None):
        return context.get_binary_view(view_id)

    return get_bv


def build_mcp():
    """No auth — plain FastMCP server, no token / OAuth verification."""
    from fastmcp import FastMCP

    mcp = FastMCP("Binary Ninja MCP")

    get_bv = _get_bv_factory()

    from .tools import (
        advanced,
        analysis,
        binary_view,
        cfg,
        edit,
        functions,
        patch,
        strings,
        symbols,
        types,
        xrefs,
    )

    binary_view.register(mcp, get_bv)
    functions.register(mcp, get_bv)
    xrefs.register(mcp, get_bv)
    symbols.register(mcp, get_bv)
    strings.register(mcp, get_bv)
    types.register(mcp, get_bv)
    edit.register(mcp, get_bv)
    cfg.register(mcp, get_bv)
    patch.register(mcp, get_bv)
    analysis.register(mcp, get_bv)
    advanced.register(mcp, get_bv)

    try:
        from . import prompts, resources

        resources.register(mcp, get_bv)
        prompts.register(mcp, get_bv)
    except Exception as ex:
        log.warning("optional resources/prompts: %s", ex)

    return mcp


def build_asgi_app():
    """No auth middleware — open access on localhost."""
    from starlette.middleware import Middleware

    from .middleware import RateLimitMiddleware, RequestLogMiddleware

    mcp = build_mcp()
    mw = [
        Middleware(RequestLogMiddleware),
        Middleware(RateLimitMiddleware, max_requests=30, window_seconds=1.0),
    ]
    return mcp.http_app(path="/mcp", middleware=mw)


def run_uvicorn_blocking(host: str, port: int) -> None:
    import uvicorn

    app = build_asgi_app()
    uvicorn.run(app, host=host, port=port, log_level="info", access_log=False)
