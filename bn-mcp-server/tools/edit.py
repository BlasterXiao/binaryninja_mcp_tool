from __future__ import annotations

import json
from typing import Any, Dict

from .helpers import (
    coerce_address,
    coalesce_address_or_name,
    parse_type_safe,
    resolve_function,
    run_on_main,
    safe_str,
)

from .. import config as cfgmod
from .. import state


def register(mcp, get_bv) -> None:
    @mcp.tool()
    def rename_function(
        address_or_name: str | None = None,
        new_name: str | None = None,
        *,
        name: str | None = None,
    ) -> str:
        def _do():
            bv = get_bv()
            key = coalesce_address_or_name(address_or_name, name)
            if not key:
                raise ValueError("provide address_or_name or name")
            if not new_name:
                raise ValueError("new_name is required")
            fn = resolve_function(bv, key)
            fn.name = str(new_name)
            state.invalidate_after_write(bv)
            return "ok"

        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def rename_variable(function: str, var_name: str, new_name: str) -> str:
        def _do():
            import binaryninja as bn
            bv = get_bv()
            fn = resolve_function(bv, function)
            # Find the target variable first
            target = None
            for v in fn.vars:
                if v.name == var_name:
                    target = v
                    break
            if target is None:
                return "variable not found"
            # Rename ALL variables at the same storage offset (all SSA indices)
            count = 0
            for v in fn.vars:
                if v.storage == target.storage and v.source_type == target.source_type:
                    fn.create_user_var(v, v.type, new_name)
                    count += 1
            # Force HLIL regeneration
            fn.request_advanced_analysis_data()
            state.invalidate_after_write(bv)
            return f"ok (renamed {count} variants)"

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
            import binaryninja as bn
            bv = get_bv()
            fn = resolve_function(bv, function)
            ok = 0
            all_vars = list(fn.vars)
            for old, new in mapping.items():
                # Find base variable
                target = None
                for v in all_vars:
                    if v.name == old:
                        target = v
                        break
                if target is None:
                    continue
                # Rename ALL variables at same storage offset (all SSA indices)
                for v in all_vars:
                    if v.storage == target.storage and v.source_type == target.source_type:
                        fn.create_user_var(v, v.type, new)
                ok += 1
            fn.request_advanced_analysis_data()
            state.invalidate_after_write(bv)
            return json.dumps({"renamed": ok, "total": len(mapping)})

        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def debug_variable_info(function: str, var_name: str) -> str:
        """Debug: show all Variable objects matching a name across fn.vars, hlil.vars, mlil.vars"""
        def _do():
            bv = get_bv()
            fn = resolve_function(bv, function)
            lines = []
            for label, var_list in [("fn.vars", fn.vars)]:
                for v in var_list:
                    if v.name == var_name:
                        lines.append(f"[{label}] name={v.name} type={v.type} source_type={v.source_type} index={v.index} storage={v.storage}")
            try:
                for v in fn.hlil.vars:
                    if v.name == var_name:
                        lines.append(f"[hlil.vars] name={v.name} type={v.type} source_type={v.source_type} index={v.index} storage={v.storage}")
            except Exception as e:
                lines.append(f"[hlil error] {e}")
            try:
                for v in fn.mlil.vars:
                    if v.name == var_name:
                        lines.append(f"[mlil.vars] name={v.name} type={v.type} source_type={v.source_type} index={v.index} storage={v.storage}")
            except Exception as e:
                lines.append(f"[mlil error] {e}")
            return "\n".join(lines) if lines else "not found in any var list"
        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def test_rename_and_decompile(function: str, var_name: str, new_name: str) -> str:
        """Debug: try constructing index=0 Variable at same storage offset to rename"""
        def _do():
            import binaryninja as bn
            bv = get_bv()
            fn = resolve_function(bv, function)
            target = None
            for v in fn.vars:
                if v.name == var_name:
                    target = v
                    break
            if target is None:
                return f"variable {var_name} not found"
            
            lines = [f"target: index={target.index} storage={target.storage} src={target.source_type}"]
            
            # Key approach: construct a Variable with index=0 at the same storage offset
            # This should create a "base" user variable that BN uses for display
            zero_var = bn.Variable(fn, target.source_type, 0, target.storage)
            lines.append(f"constructed zero_var: index={zero_var.index} storage={zero_var.storage}")
            
            # Method A: create_user_var with the constructed index=0 variable
            fn.create_user_var(zero_var, target.type, new_name)
            fn.request_advanced_analysis_data()
            hlilA = str(fn.hlil)
            lines.append(f"MA create_user_var(zero_var): new_in_hlil={new_name in hlilA}, old_in_hlil={var_name in hlilA}")
            
            # Count occurrences
            old_count = hlilA.count(var_name)
            new_count = hlilA.count(new_name)
            lines.append(f"counts: old={old_count} new={new_count}")
            
            return "\\n".join(lines)
        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def rename_data_variable(address: int | str, new_name: str) -> str:
        def _do():
            import binaryninja as bn

            addr = coerce_address(address)
            bv = get_bv()
            var = bv.get_data_var_at(addr)
            if var is not None:
                var.name = new_name
            else:
                bv.define_user_symbol(
                    bn.Symbol(bn.SymbolType.DataSymbol, addr, new_name)
                )
            state.invalidate_after_write(bv)
            return "ok"

        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def set_variable_type(function: str, var_name: str, type_name: str) -> str:
        """Change the type of a local/stack variable in a function."""

        def _do():
            bv = get_bv()
            fn = resolve_function(bv, function)
            new_ty = parse_type_safe(bv, type_name)
            if new_ty is None:
                raise ValueError(f"unknown type {type_name}")
            for v in fn.vars:
                if v.name == var_name:
                    fn.create_user_var(v, new_ty, v.name)
                    state.invalidate_after_write(bv)
                    return "ok"
            return "variable not found"

        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def set_function_comment(
        address_or_name: str | None = None,
        comment: str | None = None,
        *,
        name: str | None = None,
    ) -> str:
        def _do():
            bv = get_bv()
            key = coalesce_address_or_name(address_or_name, name)
            if not key:
                raise ValueError("provide address_or_name or name")
            if comment is None:
                raise ValueError("comment is required")
            fn = resolve_function(bv, key)
            fn.comment = str(comment)
            state.invalidate_after_write(bv)
            return "ok"

        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def set_address_comment(address: int | str, comment: str) -> str:
        def _do():
            addr = coerce_address(address)
            bv = get_bv()
            if hasattr(bv, "set_comment_at"):
                bv.set_comment_at(addr, comment)
            elif hasattr(bv, "set_comment"):
                bv.set_comment(addr, comment)
            else:
                return "set_comment not available"
            state.invalidate_after_write(bv)
            return "ok"

        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def get_comments(
        address_or_name: str | None = None, *, name: str | None = None
    ) -> str:
        bv = get_bv()
        try:
            key = coalesce_address_or_name(address_or_name, name)
            if not key:
                return "error: provide address_or_name or name"
            fn = resolve_function(bv, key)
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
    def set_switch_case_enum(
        function: str, enum_name: str, switch_var: str = ""
    ) -> str:
        """Set all integer constants in a switch to display as enum members.
        Uses multiple (address, operand) combinations to ensure BN picks up
        the display type for jump-table-based switch cases."""

        def _do():
            from binaryninja.enums import (
                HighLevelILOperation,
                IntegerDisplayType,
            )

            bv = get_bv()
            fn = resolve_function(bv, function)
            enum_ty = bv.get_type_by_name(enum_name)
            if enum_ty is None:
                raise ValueError(f"enum not found: {enum_name}")

            enum_type_id = bv.get_type_id(enum_name) or ""
            ENUM_DISPLAY = IntegerDisplayType.EnumerationDisplayType

            hlil = fn.hlil
            if hlil is None:
                return "no hlil"

            count = 0
            for block in hlil:
                for instr in block:
                    if instr.operation != HighLevelILOperation.HLIL_SWITCH:
                        continue
                    switch_addr = instr.address
                    for case_obj in instr.cases:
                        body = getattr(case_obj, "body", None)
                        body_addr = getattr(body, "address", None) if body else None
                        case_addr = getattr(case_obj, "address", None)

                        vals = getattr(case_obj, "values", None)
                        if vals is None:
                            continue

                        for val_item in vals:
                            try:
                                val = int(
                                    val_item.constant
                                    if hasattr(val_item, "constant")
                                    else val_item
                                )
                            except Exception:
                                continue

                            addrs = set()
                            if case_addr is not None:
                                addrs.add(case_addr)
                            if body_addr is not None:
                                addrs.add(body_addr)
                            addrs.add(switch_addr)
                            val_addr = getattr(val_item, "address", None)
                            if val_addr is not None:
                                addrs.add(val_addr)

                            for try_addr in addrs:
                                for operand in [0xFFFFFFFF, 0]:
                                    try:
                                        fn.set_int_display_type(
                                            try_addr, val, operand,
                                            ENUM_DISPLAY,
                                            fn.arch, enum_type_id,
                                        )
                                    except Exception:
                                        pass
                            count += 1

            state.invalidate_after_write(bv)
            return f"ok: {count} case values annotated"

        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def add_tag(address: int | str, tag_type: str, data: str) -> str:
        def _do():
            addr = coerce_address(address)
            bv = get_bv()
            if hasattr(bv, "create_tag"):
                bv.create_tag(addr, tag_type, data)
            else:
                return "tags API not available"
            state.invalidate_after_write(bv)
            return "ok"

        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"
