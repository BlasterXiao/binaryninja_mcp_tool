"""
BinaryView resolution and global plugin state (active view for MCP tools).
"""
from __future__ import annotations

import threading
from typing import Dict, List, Optional, Tuple

_lock = threading.RLock()
_primary_bv = None  # type: ignore
_view_registry: Dict[str, object] = {}


def set_primary_binary_view(bv) -> None:
    global _primary_bv
    with _lock:
        _primary_bv = bv
        if bv is not None:
            vid = _view_id_for(bv)
            _view_registry[vid] = bv


def _view_id_for(bv) -> str:
    try:
        return str(id(bv))
    except Exception:
        return "0"


def _fetch_ui_binary_view():
    """
    Read current BinaryView from BN UI APIs.
    Per Binary Ninja docs / GUI behavior, these calls must run on the **main thread**
    (see binaryninja.mainthread). MCP HTTP handlers run on worker threads.
    """
    try:
        import binaryninja.interaction as interaction

        if hasattr(interaction, "get_current_binary_view"):
            bv = interaction.get_current_binary_view()
            if bv is not None:
                return bv
    except Exception:
        pass
    try:
        import binaryninja.binaryview as bvmod

        if hasattr(bvmod.BinaryView, "get_active_view"):
            return bvmod.BinaryView.get_active_view()  # type: ignore
    except Exception:
        pass
    return None


def try_get_active_binary_view():
    """Best-effort: current BinaryView from Binary Ninja UI, then cached primary."""

    def _inner():
        bv = _fetch_ui_binary_view()
        if bv is not None:
            return bv
        with _lock:
            return _primary_bv

    try:
        import binaryninja.mainthread as mainthread

        if hasattr(mainthread, "is_main_thread") and not mainthread.is_main_thread():
            return mainthread.execute_on_main_thread_and_wait(_inner)
    except Exception:
        pass
    return _inner()


def get_binary_view(view_id: Optional[str] = None):
    """
    Return BinaryView for MCP tools.
    If view_id is set, use registry; else prefer active UI view, then primary from plugin start.
    """
    with _lock:
        if view_id and view_id in _view_registry:
            return _view_registry[view_id]
    bv = try_get_active_binary_view()
    if bv is not None:
        # 从 UI 拿到视图时写回 primary，避免下次仅依赖 UI API（工作线程上可能仍为 None）
        set_primary_binary_view(bv)
        return bv
    with _lock:
        if _primary_bv is not None:
            return _primary_bv
    raise RuntimeError(
        "No BinaryView available. Open a binary in Binary Ninja and use Plugins → MCP Server → Start from a loaded file."
    )


def list_open_views() -> List[Tuple[str, str]]:
    """Return [(view_id, label), ...]."""
    with _lock:
        out: List[Tuple[str, str]] = []
        for vid, bv in _view_registry.items():
            try:
                name = getattr(bv.file, "filename", None) or str(vid)
            except Exception:
                name = str(vid)
            out.append((vid, str(name)))
        if not out and _primary_bv is not None:
            vid = _view_id_for(_primary_bv)
            try:
                name = getattr(_primary_bv.file, "filename", vid)
            except Exception:
                name = vid
            out.append((vid, str(name)))
        return out


def switch_binary_view(view_id: str) -> bool:
    with _lock:
        if view_id in _view_registry:
            global _primary_bv
            _primary_bv = _view_registry[view_id]
            return True
    return False
