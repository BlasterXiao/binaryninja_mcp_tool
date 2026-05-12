"""Status bar indicator for MCP server state."""
from __future__ import annotations

from typing import Optional

_widget: Optional[object] = None
_dot: Optional[object] = None
_label: Optional[object] = None
_fallback_widget_id: Optional[str] = None
_fallback_task: Optional[object] = None
_state = "stopped"
_port: Optional[int] = None

_GREEN = "#2fbf5b"
_RED = "#e5484d"


def set_running(port: int) -> None:
    global _state, _port
    _state = "running"
    _port = port
    _run_on_ui_thread(_apply_state)


def set_stopped() -> None:
    global _state, _port
    _state = "stopped"
    _port = None
    _run_on_ui_thread(_apply_state)


def _run_on_ui_thread(fn) -> None:
    try:
        import binaryninja.mainthread as mainthread

        is_main_thread = getattr(mainthread, "is_main_thread", None)
        if callable(is_main_thread) and not is_main_thread():
            mainthread.execute_on_main_thread(fn)
            return
    except Exception:
        pass
    try:
        fn()
    except Exception:
        pass


def _apply_state() -> None:
    parts = _ensure_widget()
    if parts is None:
        if not _apply_fallback_status_report():
            _apply_fallback_background_task()
        return

    _finish_fallback_background_task()

    widget, dot, label = parts
    running = _state == "running"
    color = _GREEN if running else _RED
    text = f"MCP :{_port}" if running and _port is not None else "MCP Stopped"
    tooltip = (
        f"Binary Ninja MCP server running on port {_port}"
        if running and _port is not None
        else "Binary Ninja MCP server stopped"
    )

    dot.setStyleSheet(
        f"QLabel {{ background-color: {color}; border-radius: 4px; }}"
    )
    label.setText(text)
    widget.setToolTip(tooltip)
    widget.setVisible(True)


def _ensure_widget():
    global _widget, _dot, _label
    if _is_valid_qobject(_widget) and _is_valid_qobject(_dot) and _is_valid_qobject(_label):
        return _widget, _dot, _label

    parent = _get_widget_parent()
    if parent is None:
        return None

    try:
        import binaryninjaui  # noqa: F401
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

        widget = QWidget(parent)
        widget.setObjectName("bnMcpStatusIndicator")
        widget.setFixedHeight(20)
        widget.setMinimumWidth(105)

        layout = QHBoxLayout(widget)
        layout.setContentsMargins(6, 0, 8, 0)
        layout.setSpacing(5)

        dot = QLabel(widget)
        dot.setFixedSize(9, 9)

        label = QLabel(widget)
        label.setObjectName("bnMcpStatusLabel")
        label.setMinimumWidth(78)

        layout.addWidget(dot, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(label, 0, Qt.AlignmentFlag.AlignVCenter)

        if not _insert_widget(parent, widget):
            return None
        _widget = widget
        _dot = dot
        _label = label
        return widget, dot, label
    except Exception:
        return None


def _active_context():
    try:
        import binaryninja

        if hasattr(binaryninja, "core_ui_enabled") and not binaryninja.core_ui_enabled():
            return None

        from binaryninjaui import UIContext

        context = UIContext.activeContext()
        if context is None:
            contexts = list(UIContext.allContexts())
            context = contexts[0] if contexts else None
        if context is None:
            return None

        return context
    except Exception:
        return None


def _get_widget_parent():
    context = _active_context()
    if context is None:
        return None

    for widget in _candidate_parent_widgets(context):
        if _is_valid_qobject(widget):
            return widget
    return None


def _is_valid_qobject(obj: Optional[object]) -> bool:
    if obj is None:
        return False
    try:
        from shiboken6 import isValid

        return bool(isValid(obj))
    except Exception:
        pass
    try:
        getattr(obj, "objectName")()
        return True
    except Exception:
        return False


def _candidate_parent_widgets(context):
    try:
        anchor = context.fileContentsLockStatusWidget()
        parent = anchor.parentWidget() if anchor is not None else None
        if parent is not None and parent.layout() is not None:
            yield parent
    except Exception:
        pass

    try:
        frame = context.getCurrentViewFrame()
        view = frame.getCurrentView() if frame is not None else None
        status = view.getStatusBarWidget() if view is not None else None
        if status is not None and status.layout() is not None:
            yield status
    except Exception:
        pass

    try:
        main_window = context.mainWindow()
        status_bar = getattr(main_window, "statusBar", None)
        if callable(status_bar):
            yield status_bar()
    except Exception:
        pass


def _insert_widget(parent, widget) -> bool:
    try:
        status_add = getattr(parent, "addWidget", None)
        if callable(status_add):
            status_add(widget, 0)
            return True
    except Exception:
        pass

    try:
        layout = parent.layout()
        if layout is None:
            return False
        insert = getattr(layout, "insertWidget", None)
        if callable(insert):
            insert(0, widget)
        else:
            layout.addWidget(widget)
        return True
    except Exception:
        return False


def _apply_fallback_status_report() -> bool:
    global _fallback_widget_id
    try:
        import binaryninja.interaction as interaction

        show = getattr(interaction, "show_status_report", None)
        if not callable(show):
            return False

        hide = getattr(interaction, "hide_status_report", None)
        if callable(hide) and _fallback_widget_id is not None:
            try:
                hide(_fallback_widget_id)
            except TypeError:
                hide()
            except Exception:
                pass

        text = _text_status()
        _fallback_widget_id = show(text, 0)
        return True
    except Exception:
        return False


def _apply_fallback_background_task() -> None:
    global _fallback_task
    try:
        from binaryninja.plugin import BackgroundTask

        text = _text_status()
        if _state == "running":
            _finish_fallback_background_task()
            return
        if _fallback_task is None:
            _fallback_task = BackgroundTask(text, False)
        else:
            _fallback_task.progress = text
    except Exception:
        pass


def _finish_fallback_background_task() -> None:
    global _fallback_task
    if _fallback_task is None:
        return
    try:
        _fallback_task.finish()
    except Exception:
        pass
    _fallback_task = None


def _text_status() -> str:
    if _state == "running" and _port is not None:
        return f"🟢 MCP Server :{_port}"
    return "🔴 MCP Server Stopped"
