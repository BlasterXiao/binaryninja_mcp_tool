from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .helpers import (
    coerce_address,
    coalesce_address_or_name,
    parse_type_safe,
    resolve_function,
    run_on_main,
    safe_str,
)

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

            st = bn.types.StructureBuilder.create()
            for f in sorted(fields, key=lambda x: int(x.get("offset", 0))):
                tn = f.get("type", "int")
                off = int(f.get("offset", 0))
                nm = f.get("name", "field")
                inner = parse_type_safe(bv, tn)
                if inner is None:
                    inner = bn.types.Type.int(4)
                st.insert(off, inner, nm)
            bv.define_user_type(name, bn.types.Type.structure_type(st))
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
            eb = bn.types.EnumerationBuilder.create()
            for m in members:
                eb.append(m.get("name", "m"), int(m.get("value", 0)))
            bv.define_user_type(name, bn.types.Type.enumeration_type(bv.arch, eb))
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
            inner = parse_type_safe(bv, target_type)
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
    def apply_type_to_address(address: int | str, type_name: str) -> str:
        """Apply named type at data address."""

        def _do():
            addr = coerce_address(address)
            bv = get_bv()
            ty = parse_type_safe(bv, type_name)
            if ty is None:
                raise ValueError(f"unknown type {type_name}")
            bv.define_user_data_var(addr, ty)
            state.invalidate_after_write(bv)
            return "ok"

        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def set_function_type(
        address_or_name: str | None = None,
        signature: str | None = None,
        *,
        name: str | None = None,
    ) -> str:
        """Set function prototype string (BN parse_types_from_source)."""

        def _do():
            bv = get_bv()
            key = coalesce_address_or_name(address_or_name, name)
            if not key:
                raise ValueError("provide address_or_name or name")
            if not signature:
                raise ValueError("signature is required")
            fn = resolve_function(bv, key)
            if hasattr(bv, "parse_type_string"):
                ty, _ = bv.parse_type_string(str(signature))
                fn.type = ty
                state.invalidate_after_write(bv)
                return "ok"
            return "parse_type_string not available"

        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def import_type_from_header(header_content: str) -> str:
        """Parse C header snippet for types."""

        def _do():
            bv = get_bv()
            result = None
            if hasattr(bv, "parse_types_from_source"):
                result = bv.parse_types_from_source(header_content)
            elif hasattr(bv, "parse_type_string"):
                result = bv.parse_type_string(header_content)
                state.invalidate_after_write(bv)
                return safe_str(result)

            if result is None:
                return "not supported"

            imported = []
            types_dict = getattr(result, "types", None)
            if types_dict:
                for tname, tobj in types_dict.items():
                    tname_str = str(tname) if not isinstance(tname, str) else tname
                    bv.define_user_type(tname_str, tobj)
                    imported.append(tname_str)

            state.invalidate_after_write(bv)
            if imported:
                return f"ok: imported {', '.join(imported)}"
            return f"parsed but no types found: {safe_str(result)}"

        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"
