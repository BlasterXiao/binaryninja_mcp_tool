"""Plugin command handlers: start/stop/status/settings."""
from __future__ import annotations

import threading
from typing import Optional

import binaryninja.interaction as interaction

from . import config
from . import context as ctxmod

_task: Optional[object] = None
_lock = threading.RLock()


def _resolve_binary_view_for_start(ctx) -> None:
    """
    PluginCommandContext.binaryView 在部分情况下为 None（例如从菜单触发时未带上当前标签页），
    此时应回退到 UI 当前 BinaryView（与 https://api.binary.ninja/ 中 GUI/交互 API 行为一致）。
    """
    bv = None
    try:
        if ctx is not None and getattr(ctx, "binaryView", None) is not None:
            bv = ctx.binaryView
    except Exception:
        pass
    if bv is None:
        bv = ctxmod.try_get_active_binary_view()
    if bv is not None:
        ctxmod.set_primary_binary_view(bv)


def is_server_running() -> bool:
    """
    MCP 是否在跑：以 uvicorn 实例为准；否则看后台线程是否仍存活。
    （Binary Ninja 的 BackgroundTaskThread.is_alive 在部分版本不可靠，故不能单靠它。）
    """
    from . import bg_task

    try:
        if bg_task.is_server_active():
            return True
    except Exception:
        pass
    with _lock:
        if _task is None:
            return False
        alive = getattr(_task, "is_alive", None)
        if callable(alive):
            return bool(alive())
        return False


def _clear_stale_task_if_any() -> None:
    """任务对象残留但线程已结束且 HTTP 未在跑时，允许再次 Start。"""
    global _task
    from . import bg_task

    if _task is None:
        return
    if bg_task.is_server_active():
        return
    alive = getattr(_task, "is_alive", None)
    if callable(alive) and alive():
        return
    _task = None


def start_from_context(ctx) -> None:
    global _task
    with _lock:
        _clear_stale_task_if_any()
        _resolve_binary_view_for_start(ctx)
        if is_server_running():
            interaction.show_message_box(
                "MCP Server",
                "Server already running.\nUse Stop before starting again.",
                interaction.MessageBoxButtonSet.OKButtonSet,
            )
            return
        from .bg_task import MCPServerTask

        _task = MCPServerTask()
        _task.start()
        try:
            from .ui import statusbar

            statusbar.set_running(config.get_port())
        except Exception:
            pass
        interaction.show_message_box(
            "MCP Server",
            f"Started at http://{config.get_host()}:{config.get_port()}/mcp\n"
            f"Token: {config.get_token()}",
            interaction.MessageBoxButtonSet.OKButtonSet,
        )


def stop_server() -> None:
    global _task
    with _lock:
        from .bg_task import shutdown_server

        shutdown_server()
        try:
            if _task is not None:
                t = _task
                if hasattr(t, "cancel"):
                    t.cancel()
        except Exception:
            pass
        _task = None
        try:
            from .ui import statusbar

            statusbar.set_stopped()
        except Exception:
            pass
        interaction.show_message_box(
            "MCP Server", "Stop requested.", interaction.MessageBoxButtonSet.OKButtonSet
        )


def show_status() -> None:
    tok = config.get_token()
    host = config.get_host()
    port = config.get_port()
    interaction.show_message_box(
        "MCP Server",
        f"URL: http://{host}:{port}/mcp\nBearer: {tok}\n",
        interaction.MessageBoxButtonSet.OKButtonSet,
    )


def open_settings() -> None:
    try:
        from .ui import settings as settings_ui

        settings_ui.show_settings()
    except Exception as ex:
        interaction.show_message_box(
            "MCP Server",
            f"Settings failed: {ex}",
            interaction.MessageBoxButtonSet.OKButtonSet,
        )
