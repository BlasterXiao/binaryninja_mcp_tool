"""Plugin settings UI (Binary Ninja interaction APIs)."""
from __future__ import annotations

import binaryninja.interaction as interaction

from .. import config


def show_settings() -> None:
    """
    使用官方 API：get_int_input / get_text_line_input。
    注意：不存在 get_text_input；旧代码会 AttributeError 并被吞掉，表现为「点了没反应」。
    """
    cfg = config.load_config()
    port = cfg.get("port", 9090)
    cache = cfg.get("hlil_cache_size", 500)

    try:
        p = interaction.get_int_input(
            f"Listen port for MCP HTTP (current: {port})",
            "MCP Server — Settings",
        )
        if p is not None and p > 0 and p < 65536:
            cfg["port"] = int(p)

        c = interaction.get_int_input(
            f"HLIL cache size (current: {cache})",
            "MCP Server — Settings",
        )
        if c is not None and c > 0:
            cfg["hlil_cache_size"] = int(c)

        config.save_config(cfg)
        interaction.show_message_box(
            "MCP Server",
            f"Settings saved.\nport={cfg['port']}, hlil_cache_size={cfg['hlil_cache_size']}\n\n"
            "Change port: Stop MCP, then Start again.",
            interaction.MessageBoxButtonSet.OKButtonSet,
        )
    except (ValueError, TypeError) as ex:
        interaction.show_message_box(
            "MCP Server",
            f"Invalid value: {ex}",
            interaction.MessageBoxButtonSet.OKButtonSet,
        )
    except Exception as ex:
        interaction.show_message_box(
            "MCP Server",
            f"Settings error: {ex}",
            interaction.MessageBoxButtonSet.OKButtonSet,
        )
