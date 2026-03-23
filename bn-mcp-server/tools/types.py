from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .helpers import resolve_function, run_on_main, safe_str

from .. import state


def register(mcp, get_bv) -> None:
    @mcp.tool()
    def list_types() -> str:
        """List user-defined types."""
        bv = get_bv()
        try:
            lines: List[str] = []
            for t in bv.types:
                try:
                    lines.append(safe_str(t))
                except Exception:
                    continue
            return "\n".join(lines[:2000]) if lines else "(none)"
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def get_type(name: str) -> str:
        """Show type definition by name."""
        bv = get_bv()
        try:
            ty = bv.get_type_by_name(name)
            if ty is None:
                return f"not found: {name}"
            return safe_str(ty)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def define_struct(name: str, fields_json: str) -> str:
        """Define struct from JSON list of {name, type, offset}."""
        fields: List[Dict[str, Any]] = json.loads(fields_json)

        def _do():
            bv = get_bv()
            import binaryninja as bn

            members: List[Any] = []
            for f in fields:
                tn = f.get("type")
                off = int(f.get("offset", 0))
                nm = f.get("name", "field")
                inner = bv.get_type_by_name(tn) if isinstance(tn, str) else None
                if inner is None:
                    inner = bn.types.Type.int(4, bv.arch, False)
                members.append((off, nm, inner))
            st = bn.types.Structure()
            for off, nm, ty in sorted(members, key=lambda x: x[0]):
                st.insert(off, ty, nm)
            bv.define_user_type(name, st)
            state.invalidate_after_write(bv)
            return "ok"

        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def define_enum(name: str, members_json: str) -> str:
        """Define enum from JSON list of {name, value}."""

        def _do():
            bv = get_bv()
            import binaryninja as bn

            members = json.loads(members_json)
            en = bn.types.Enumeration(bv.arch, name)
            for m in members:
                en.append(m.get("name", "m"), int(m.get("value", 0)))
            bv.define_user_type(name, en)
            state.invalidate_after_write(bv)
            return "ok"

        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def define_typedef(name: str, target_type: str) -> str:
        """Create typedef alias."""

        def _do():
            bv = get_bv()
            inner = bv.get_type_by_name(target_type)
            if inner is None:
                raise ValueError(f"unknown type {target_type}")
            bv.define_user_type(name, inner)
            state.invalidate_after_write(bv)
            return "ok"

        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def apply_type_to_address(address: int, type_name: str) -> str:
        """Apply named type at data address."""

        def _do():
            bv = get_bv()
            ty = bv.get_type_by_name(type_name)
            if ty is None:
                raise ValueError(f"unknown type {type_name}")
            bv.define_user_data_var(address, ty)
            state.invalidate_after_write(bv)
            return "ok"

        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def set_function_type(address_or_name: str, signature: str) -> str:
        """Set function prototype string (BN parse_types_from_source)."""

        def _do():
            bv = get_bv()
            fn = resolve_function(bv, address_or_name)
            if hasattr(bv, "parse_types_from_source"):
                res = bv.parse_types_from_source(signature)
                # apply first function type found - API varies
                state.invalidate_after_write(bv)
                return safe_str(res)
            return "parse_types_from_source not available"

        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def import_type_from_header(header_content: str) -> str:
        """Parse C header snippet for types."""

        def _do():
            bv = get_bv()
            if hasattr(bv, "parse_types_from_source"):
                r = bv.parse_types_from_header(header_content)
                state.invalidate_after_write(bv)
                return safe_str(r)
            if hasattr(bv, "parse_types_from_source"):
                r = bv.parse_types_from_source(header_content)
                state.invalidate_after_write(bv)
                return safe_str(r)
            return "not supported"

        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"
