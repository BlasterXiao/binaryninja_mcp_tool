"""Background task running uvicorn (MCP HTTP) inside Binary Ninja."""
from __future__ import annotations

from typing import Optional

from binaryninja.plugin import BackgroundTaskThread

_uvicorn_server: Optional[object] = None


def is_server_active() -> bool:
    """True while uvicorn Server.run() holds the HTTP listener (ground truth for MCP running)."""
    return _uvicorn_server is not None


class MCPServerTask(BackgroundTaskThread):
    def __init__(self):
        super().__init__("Binary Ninja MCP Server", can_cancel=True)

    def run(self):
        global _uvicorn_server
        from uvicorn import Config, Server

        from . import config as cfgmod
        from . import state
        from .server import build_asgi_app

        state.init_caches(cfgmod.get_hlil_cache_size())
        app = build_asgi_app()
        host = cfgmod.get_host()
        port = cfgmod.get_port()
        c = Config(app, host=host, port=port, log_level="info", access_log=False)
        server = Server(c)
        _uvicorn_server = server
        try:
            server.run()
        finally:
            _uvicorn_server = None

    def cancel(self):
        global _uvicorn_server
        try:
            if _uvicorn_server is not None:
                setattr(_uvicorn_server, "should_exit", True)
        except Exception:
            pass
        try:
            super().cancel()
        except Exception:
            pass


def shutdown_server() -> None:
    global _uvicorn_server
    try:
        if _uvicorn_server is not None:
            setattr(_uvicorn_server, "should_exit", True)
    except Exception:
        pass
