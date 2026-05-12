"""Background task running uvicorn (MCP HTTP) inside Binary Ninja."""
from __future__ import annotations

import asyncio
import logging
import sys
import threading
import time
from typing import Any, Optional

from binaryninja.plugin import BackgroundTaskThread

log = logging.getLogger("bn_mcp.bg_task")

_uvicorn_server: Optional[object] = None
_shutdown_requested = threading.Event()


class _BinaryNinjaLogHandler(logging.Handler):
    """Route uvicorn warnings/errors through Binary Ninja logging instead of stderr."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            if record.levelno >= logging.ERROR:
                _bn_log("error", msg)
            elif record.levelno >= logging.WARNING:
                _bn_log("warn", msg)
            else:
                _bn_log("info", msg)
        except Exception:
            pass


def _bn_log(level: str, message: str) -> None:
    try:
        from binaryninja import log as bnlog

        func = getattr(bnlog, f"log_{level}", None)
        if callable(func):
            func(message, "BN MCP")
            return
    except Exception:
        pass
    try:
        print(f"[bn-mcp-server] {message}")
    except Exception:
        pass


def _configure_uvicorn_logging() -> None:
    """
    Uvicorn's default logger writes normal startup/shutdown messages to stderr,
    which Binary Ninja shows like an error. Keep routine server noise out of
    stderr and only surface real warnings/errors via Binary Ninja logging.
    """
    handler = _BinaryNinjaLogHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))

    error_logger = logging.getLogger("uvicorn.error")
    error_logger.handlers = [handler]
    error_logger.setLevel(logging.WARNING)
    error_logger.propagate = False

    access_logger = logging.getLogger("uvicorn.access")
    access_logger.handlers = []
    access_logger.propagate = False

    root_logger = logging.getLogger("uvicorn")
    root_logger.handlers = []
    root_logger.setLevel(logging.WARNING)
    root_logger.propagate = False


def is_server_active() -> bool:
    """True while uvicorn Server.run() holds the HTTP listener (ground truth for MCP running)."""
    return _uvicorn_server is not None


def clear_shutdown_request() -> None:
    _shutdown_requested.clear()


def shutdown_server(force: bool = False) -> None:
    global _uvicorn_server
    _shutdown_requested.set()
    try:
        if _uvicorn_server is not None:
            setattr(_uvicorn_server, "should_exit", True)
            if force:
                setattr(_uvicorn_server, "force_exit", True)
    except Exception:
        pass


def wait_for_server_shutdown(timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + max(timeout, 0.0)
    while time.monotonic() < deadline:
        if _uvicorn_server is None:
            return True
        time.sleep(0.05)
    return _uvicorn_server is None


def _is_expected_connection_close(exc: BaseException | None, handle: Any) -> bool:
    """Windows may report client disconnects while asyncio is closing a transport."""
    if exc is None:
        return False
    if not isinstance(exc, (ConnectionResetError, BrokenPipeError)):
        return False
    winerror = getattr(exc, "winerror", None)
    if winerror is not None and winerror not in (10053, 10054, 10058):
        return False
    return "_call_connection_lost" in str(handle)


def _loop_exception_handler(loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
    exc = context.get("exception")
    handle = context.get("handle")
    if _is_expected_connection_close(exc, handle):
        log.debug("Ignored reset while closing MCP client connection: %r", exc)
        return
    loop.default_exception_handler(context)


def _new_server_loop() -> asyncio.AbstractEventLoop:
    if sys.platform == "win32" and hasattr(asyncio, "SelectorEventLoop"):
        return asyncio.SelectorEventLoop()
    return asyncio.new_event_loop()


def _run_server(server: Any) -> None:
    """
    Run uvicorn on an event loop owned by this BN background task.

    Python 3.13 defaults to ProactorEventLoop on Windows. When MCP clients probe
    and close HTTP/SSE connections abruptly, that loop can surface benign
    ConnectionResetError callbacks in Binary Ninja's ScriptingProvider. A selector
    loop is sufficient for uvicorn's TCP server here and avoids the noisy proactor
    shutdown path.
    """
    loop = _new_server_loop()
    asyncio.set_event_loop(loop)
    loop.set_exception_handler(_loop_exception_handler)
    try:
        loop.run_until_complete(server.serve())
    finally:
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
        except Exception:
            pass
        shutdown_default_executor = getattr(loop, "shutdown_default_executor", None)
        if callable(shutdown_default_executor):
            try:
                loop.run_until_complete(shutdown_default_executor())
            except Exception:
                pass
        asyncio.set_event_loop(None)
        loop.close()


class MCPServerTask(BackgroundTaskThread):
    def __init__(self):
        super().__init__("🟢 MCP Server starting", can_cancel=True)

    def run(self):
        global _uvicorn_server
        from uvicorn import Config, Server

        from . import config as cfgmod
        from . import state
        from .server import build_asgi_app

        host = cfgmod.get_host()
        port = cfgmod.get_port()
        try:
            self.progress = f"🟢 MCP Server :{port}"
        except Exception:
            pass

        try:
            if _shutdown_requested.is_set():
                return
            state.init_caches(cfgmod.get_hlil_cache_size())
            if _shutdown_requested.is_set():
                return
            app = build_asgi_app()
            if _shutdown_requested.is_set():
                return

            _configure_uvicorn_logging()
            c = Config(
                app,
                host=host,
                port=port,
                log_level="warning",
                access_log=False,
                log_config=None,
            )
            server = Server(c)
            if _shutdown_requested.is_set():
                setattr(server, "should_exit", True)
            _uvicorn_server = server
            _bn_log("info", f"MCP server starting at http://{host}:{port}/mcp")
            _run_server(server)
        except Exception as ex:
            _bn_log("error", f"MCP server failed: {ex}")
            raise
        finally:
            _uvicorn_server = None
            try:
                from .ui import statusbar

                statusbar.set_stopped()
            except Exception:
                pass
            if _shutdown_requested.is_set():
                _bn_log("info", "MCP server stopped.")

    def cancel(self):
        try:
            self.progress = "🔴 MCP Server stopping"
        except Exception:
            pass
        try:
            shutdown_server()
        except Exception:
            pass
        try:
            super().cancel()
        except Exception:
            pass
