"""Status bar indicator for MCP server state."""
from __future__ import annotations

from typing import Optional

_widget_id: Optional[str] = None


def set_running(port: int) -> None:
    try:
        import binaryninja.interaction as interaction

        if hasattr(interaction, "show_status_report"):
            global _widget_id
            _widget_id = interaction.show_status_report(
                f"MCP Server: Running on :{port}", 0
            )
    except Exception:
        pass


def set_stopped() -> None:
    try:
        import binaryninja.interaction as interaction

        if hasattr(interaction, "hide_status_report"):
            interaction.hide_status_report()
    except Exception:
        pass
