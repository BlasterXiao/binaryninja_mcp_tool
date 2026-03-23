from __future__ import annotations

import json
from typing import Any, Dict

from .helpers import resolve_function, run_on_main, safe_str

from .. import config as cfgmod
from .. import state


def register(mcp, get_bv) -> None:
    @mcp.tool()
    def rename_function(address_or_name: str, new_name: str) -> str:
        def _do():
            bv = get_bv()
            fn = resolve_function(bv, address_or_name)
            fn.name = new_name
            state.invalidate_after_write(bv)
            return "ok"

        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def rename_variable(function: str, var_name: str, new_name: str) -> str:
        def _do():
            bv = get_bv()
            fn = resolve_function(bv, function)
            for v in fn.vars:
                if v.name == var_name:
                    v.name = new_name
                    state.invalidate_after_write(bv)
                    return "ok"
            return "variable not found"

        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def batch_rename_variables(function: str, mapping_json: str) -> str:
        mapping: Dict[str, str] = json.loads(mapping_json)
        cfg = cfgmod.load_config()
        need_confirm = bool(cfg.get("require_write_confirm", True))
        threshold = int(cfg.get("batch_rename_confirm_threshold", 20))
        if need_confirm and len(mapping) > threshold:
            from ..ui import confirm_dialog

            if not confirm_dialog.confirm_write(
                f"Rename {len(mapping)} variables in {function}?"
            ):
                return "cancelled"

        def _do():
            bv = get_bv()
            fn = resolve_function(bv, function)
            ok = 0
            for old, new in mapping.items():
                for v in fn.vars:
                    if v.name == old:
                        v.name = new
                        ok += 1
                        break
            state.invalidate_after_write(bv)
            return json.dumps({"renamed": ok, "total": len(mapping)})

        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def rename_data_variable(address: int, new_name: str) -> str:
        def _do():
            bv = get_bv()
            var = bv.get_data_var_at(address)
            if var is None:
                return "no data var"
            var.name = new_name
            state.invalidate_after_write(bv)
            return "ok"

        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def set_function_comment(address_or_name: str, comment: str) -> str:
        def _do():
            bv = get_bv()
            fn = resolve_function(bv, address_or_name)
            fn.comment = comment
            state.invalidate_after_write(bv)
            return "ok"

        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def set_address_comment(address: int, comment: str) -> str:
        def _do():
            bv = get_bv()
            if hasattr(bv, "set_comment_at"):
                bv.set_comment_at(address, comment)
            elif hasattr(bv, "set_comment"):
                bv.set_comment(address, comment)
            else:
                return "set_comment not available"
            state.invalidate_after_write(bv)
            return "ok"

        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def get_comments(address_or_name: str) -> str:
        bv = get_bv()
        try:
            fn = resolve_function(bv, address_or_name)
            lines = [f"function: {safe_str(fn.comment)}"]
            for block in fn.basic_blocks:
                for addr in range(block.start, block.end):
                    try:
                        c = bv.get_comment_at(addr)
                        if c:
                            lines.append(f"0x{addr:x}: {c}")
                    except Exception:
                        continue
            return "\n".join(lines)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def add_tag(address: int, tag_type: str, data: str) -> str:
        def _do():
            bv = get_bv()
            if hasattr(bv, "create_tag"):
                bv.create_tag(address, tag_type, data)
            else:
                return "tags API not available"
            state.invalidate_after_write(bv)
            return "ok"

        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"
