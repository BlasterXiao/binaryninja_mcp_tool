from __future__ import annotations

import json
from typing import Any, List, Optional

from .helpers import il_to_lines, resolve_function, safe_str


def register(mcp, get_bv) -> None:
    @mcp.tool()
    def list_functions(offset: int = 0, limit: int = 1000) -> str:
        """List functions with pagination (default limit 1000)."""
        bv = get_bv()
        try:
            funcs = list(bv.functions)
            slice_ = funcs[offset : offset + limit]
            lines = []
            for f in slice_:
                sym = f.symbol is not None
                lines.append(
                    f"0x{int(f.start):x}\t{getattr(f, 'total_bytes', 0)}\t{sym}\t{f.name}"
                )
            return "\n".join(lines) if lines else "(no functions)"
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def get_function_by_address(address: int) -> str:
        """Get function summary by address."""
        bv = get_bv()
        try:
            fn = bv.get_function_at(address)
            if fn is None:
                return f"no function at 0x{address:x}"
            return _func_summary(fn)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def get_function_by_name(name: str) -> str:
        """Get function summary by exact or unique partial name."""
        bv = get_bv()
        try:
            fn = resolve_function(bv, name)
            return _func_summary(fn)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def decompile_function(address_or_name: str) -> str:
        """Return HLIL decompilation as text (cached)."""
        from .. import state

        bv = get_bv()
        try:
            fn = resolve_function(bv, address_or_name)
            bid = id(bv)
            start = int(fn.start)
            hit, txt = state.hlil_cache().get_text(bid, start)
            if hit and txt is not None:
                return txt
            hlil = fn.hlil
            text = str(hlil) if hlil is not None else "(no hlil)"
            state.hlil_cache().set_text(bid, start, text)
            return text
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def get_function_llil(address_or_name: str) -> str:
        """List LLIL instructions as text lines."""
        bv = get_bv()
        try:
            fn = resolve_function(bv, address_or_name)
            llil = fn.llil
            if llil is None:
                return "(no llil)"
            return "\n".join(il_to_lines(llil))
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def get_function_mlil(address_or_name: str) -> str:
        """List MLIL instructions as text lines."""
        bv = get_bv()
        try:
            fn = resolve_function(bv, address_or_name)
            mlil = fn.mlil
            if mlil is None:
                return "(no mlil)"
            return "\n".join(il_to_lines(mlil))
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def get_function_hlil(address_or_name: str) -> str:
        """HLIL as structured JSON-ish summary (roots + string dump)."""
        bv = get_bv()
        try:
            fn = resolve_function(bv, address_or_name)
            hlil = fn.hlil
            if hlil is None:
                return "(no hlil)"
            roots = []
            try:
                for r in hlil.root:  # type: ignore
                    roots.append(safe_str(r))
            except Exception:
                roots.append(safe_str(hlil))
            return json.dumps({"roots": roots, "text": str(hlil)}, ensure_ascii=False)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def get_function_ssa(address_or_name: str, il_level: str = "mlil") -> str:
        """SSA form for mlil or hlil."""
        bv = get_bv()
        try:
            fn = resolve_function(bv, address_or_name)
            il_level = il_level.lower().strip()
            if il_level == "hlil":
                h = fn.hlil
                if h is None:
                    return "(no hlil)"
                ssa = h.ssa_form
            else:
                m = fn.mlil
                if m is None:
                    return "(no mlil)"
                ssa = m.ssa_form
            if ssa is None:
                return "(no ssa)"
            return "\n".join(il_to_lines(ssa))
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def get_function_assembly(address_or_name: str) -> str:
        """Disassembly lines for the function."""
        bv = get_bv()
        try:
            fn = resolve_function(bv, address_or_name)
            lines: List[str] = []
            try:
                addrs = getattr(fn, "instruction_addresses", None)
                if addrs is not None:
                    for addr in addrs:
                        lines.append(f"0x{int(addr):x}\t{bv.get_disassembly(addr)}")
                    return "\n".join(lines) if lines else "(empty)"
            except Exception:
                pass
            for block in fn.basic_blocks:
                addr = block.start
                end = block.end
                while addr < end:
                    try:
                        lines.append(f"0x{addr:x}\t{bv.get_disassembly(addr)}")
                        ilen = bv.get_instruction_length(addr) or 1
                        addr = addr + ilen
                    except Exception:
                        addr += 1
            return "\n".join(lines) if lines else "(empty)"
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def get_function_callees(address_or_name: str) -> str:
        """Functions called by this function."""
        bv = get_bv()
        try:
            fn = resolve_function(bv, address_or_name)
            out: List[str] = []
            for c in fn.callees:
                out.append(f"0x{int(c.start):x}\t{c.name}")
            return "\n".join(out) if out else "(none)"
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def get_function_callers(address_or_name: str) -> str:
        """Functions that call this function."""
        bv = get_bv()
        try:
            fn = resolve_function(bv, address_or_name)
            out: List[str] = []
            for c in fn.callers:
                out.append(f"0x{int(c.start):x}\t{c.name}")
            return "\n".join(out) if out else "(none)"
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def get_function_variables(address_or_name: str) -> str:
        """Local/stack variables."""
        bv = get_bv()
        try:
            fn = resolve_function(bv, address_or_name)
            lines: List[str] = []
            for v in fn.vars:
                try:
                    lines.append(f"{v.name}\t{safe_str(v.type)}\t{safe_str(v.storage)}")
                except Exception as ex:
                    lines.append(f"<var err {ex}>")
            return "\n".join(lines) if lines else "(none)"
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def get_function_parameters(address_or_name: str) -> str:
        """Function parameter names and types."""
        bv = get_bv()
        try:
            fn = resolve_function(bv, address_or_name)
            lines: List[str] = []
            for p in fn.parameter_vars:
                lines.append(f"{p.name}\t{safe_str(p.type)}")
            return "\n".join(lines) if lines else "(none)"
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def get_function_return_type(address_or_name: str) -> str:
        """Return type string."""
        bv = get_bv()
        try:
            fn = resolve_function(bv, address_or_name)
            return safe_str(fn.return_type)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def get_function_tags(address_or_name: str) -> str:
        """Tags attached to the function."""
        bv = get_bv()
        try:
            fn = resolve_function(bv, address_or_name)
            lines: List[str] = []
            if hasattr(fn, "tags"):
                for t in fn.tags:
                    lines.append(safe_str(t))
            return "\n".join(lines) if lines else "(none)"
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def get_function_complexity(address_or_name: str) -> str:
        """Cyclomatic complexity (approximate via basic blocks)."""
        bv = get_bv()
        try:
            fn = resolve_function(bv, address_or_name)
            n = len(list(fn.basic_blocks))
            # rough: edges not always available uniformly
            return str(max(1, n))
        except Exception as e:
            return f"error: {e}"


def _func_summary(fn) -> str:
    lines = [
        f"name: {fn.name}",
        f"start: 0x{int(fn.start):x}",
        f"return: {safe_str(fn.return_type)}",
    ]
    try:
        ps = [f"{p.name}:{safe_str(p.type)}" for p in fn.parameter_vars]
        lines.append("params: " + ", ".join(ps))
    except Exception:
        pass
    return "\n".join(lines)
