from __future__ import annotations

from .helpers import resolve_function, run_on_main, safe_str

from .. import context as ctxmod
from .. import state


def register(mcp, get_bv) -> None:
    @mcp.tool()
    def start_analysis() -> str:
        """Request update analysis (best-effort)."""

        def _do():
            bv = get_bv()
            if hasattr(bv, "update_analysis_and_wait"):
                bv.update_analysis_and_wait()
            elif hasattr(bv, "update_analysis"):
                bv.update_analysis()
            else:
                return "no analysis API"
            return "ok"

        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def wait_for_analysis(timeout_ms: int = 60000) -> str:
        import time

        t0 = time.time()
        while (time.time() - t0) * 1000 < timeout_ms:
            try:
                s = get_analysis_progress_impl(ctxmod.get_binary_view())
                if "100" in s or "complete" in s.lower():
                    return "complete"
            except Exception:
                pass
            time.sleep(0.2)
        return "timeout"

    @mcp.tool()
    def get_analysis_progress() -> str:
        try:
            return get_analysis_progress_impl(get_bv())
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def define_function_at(address: int, name: str = "") -> str:
        def _do():
            bv = get_bv()
            bv.create_user_function(address)
            if name:
                fn = bv.get_function_at(address)
                if fn:
                    fn.name = name
            state.invalidate_after_write(bv)
            return "ok"

        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def undefine_function(address: int) -> str:
        def _do():
            bv = get_bv()
            fn = bv.get_function_at(address)
            if fn is None:
                return "no function"
            bv.remove_user_function(fn)
            state.invalidate_after_write(bv)
            return "ok"

        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def reanalyze_function(address_or_name: str) -> str:
        def _do():
            bv = get_bv()
            fn = resolve_function(bv, address_or_name)
            if hasattr(fn, "reanalyze"):
                fn.reanalyze()
            state.invalidate_after_write(bv)
            return "ok"

        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"


def get_analysis_progress_impl(bv) -> str:
    if hasattr(bv, "analysis_progress"):
        return safe_str(bv.analysis_progress)
    return "unknown"
