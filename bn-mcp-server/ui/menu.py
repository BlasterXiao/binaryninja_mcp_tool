"""Register plugin menu commands."""
from __future__ import annotations

from binaryninja.plugin import PluginCommand

from .. import plugin_main


def _reg(name: str, desc: str, action, is_valid) -> None:
    try:
        if is_valid is not None:
            PluginCommand.register(name, desc, action, is_valid)
        else:
            PluginCommand.register(name, desc, action)
    except TypeError:
        # 旧版 BN 无 is_valid 参数时退回为仅注册动作（无法置灰菜单）
        PluginCommand.register(name, desc, action)


def register() -> None:
    # is_valid: False 时菜单项置灰（PluginCommand.register 第 4 参数）
    _reg(
        "MCP Server\\Start",
        "Start HTTP MCP server (Streamable HTTP)",
        lambda ctx: plugin_main.start_from_context(ctx),
        lambda ctx: not plugin_main.is_server_running(),
    )
    _reg(
        "MCP Server\\Stop",
        "Stop MCP server",
        lambda ctx: plugin_main.stop_server(),
        lambda ctx: plugin_main.is_server_running(),
    )
    _reg(
        "MCP Server\\Status",
        "Show MCP server status",
        lambda ctx: plugin_main.show_status(),
        None,
    )
    _reg(
        "MCP Server\\Settings",
        "Open MCP server settings",
        lambda ctx: plugin_main.open_settings(),
        None,
    )
