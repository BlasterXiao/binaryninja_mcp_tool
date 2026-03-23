"""Blocking confirmation for destructive MCP writes (main thread)."""
from __future__ import annotations


def confirm_write(message: str) -> bool:
    try:
        import binaryninja.interaction as interaction

        if hasattr(interaction, "get_choice_input"):
            return (
                interaction.get_choice_input("BN MCP", message, ["Cancel", "OK"]) == "OK"
            )
        if hasattr(interaction, "show_message_box"):
            r = interaction.show_message_box(
                "BN MCP",
                message,
                interaction.MessageBoxButtonSet.OKCancel,
            )
            return r == interaction.MessageBoxButtonResult.OKButton
    except Exception:
        pass
    return True
