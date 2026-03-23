"""
Bind MCP primary BinaryView whenever Binary Ninja loads/finishes a BinaryView.

This fixes cases where PluginCommand context has no binaryView and UI APIs
(get_current_binary_view) return None from worker threads — the global
BinaryViewType callbacks run in the core when a view exists.
See Binary Ninja API: BinaryViewType.add_binaryview_finalized_event, etc.
"""
from __future__ import annotations

import logging

log = logging.getLogger("bn_mcp.bv_hooks")


def register_binary_view_hooks() -> None:
    """Register once at plugin load (main thread)."""
    try:
        import binaryninja.binaryview as bvmod

        from . import context as ctxmod

        def _bind(bv) -> None:
            if bv is None:
                return
            try:
                ctxmod.set_primary_binary_view(bv)
            except Exception:
                pass

        # Any new BinaryView finalized → remember for MCP tools
        if hasattr(bvmod.BinaryViewType, "add_binaryview_finalized_event"):
            bvmod.BinaryViewType.add_binaryview_finalized_event(_bind)
            log.debug("add_binaryview_finalized_event registered")
        # Analysis completed — refresh binding (optional on older BN)
        if hasattr(bvmod.BinaryViewType, "add_binaryview_initial_analysis_completion_event"):
            bvmod.BinaryViewType.add_binaryview_initial_analysis_completion_event(_bind)
            log.debug("add_binaryview_initial_analysis_completion_event registered")
    except Exception as ex:
        log.warning("BinaryView hooks not registered: %s", ex)
