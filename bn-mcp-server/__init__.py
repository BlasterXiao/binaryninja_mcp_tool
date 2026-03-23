"""
Binary Ninja MCP Server plugin — HTTP (Streamable HTTP) MCP for AI clients.

Install deps into Binary Ninja's Python environment:
    pip install -r requirements.txt
"""
from __future__ import annotations

try:
    from . import bv_hooks

    bv_hooks.register_binary_view_hooks()
except Exception as _ex:
    import traceback

    traceback.print_exc()
    print(f"[bn-mcp-server] BinaryView hooks failed: {_ex}")

try:
    from .ui.menu import register as _register_menu

    _register_menu()
except Exception as _ex:
    import traceback

    traceback.print_exc()
    print(f"[bn-mcp-server] menu registration failed: {_ex}")

# 插件晚于样本加载时，全局 finalized 事件不会回溯；在主线程尝试绑定当前已打开的标签页
try:
    from . import context as _ctxmod

    _bv = _ctxmod.try_get_active_binary_view()
    if _bv is not None:
        _ctxmod.set_primary_binary_view(_bv)
except Exception:
    pass
