from __future__ import annotations

import difflib
import json
from typing import List

from .helpers import resolve_function, safe_str


_DEFAULT_DANGEROUS = [
    "strcpy",
    "strcat",
    "sprintf",
    "gets",
    "memcpy",
    "memmove",
    "scanf",
    "system",
]


def register(mcp, get_bv) -> None:
    @mcp.tool()
    def find_dangerous_functions(func_list: str = "") -> str:
        """Find calls to libc-style dangerous APIs (substring match on callee name)."""
        names = _DEFAULT_DANGEROUS
        if func_list.strip():
            names = [x.strip() for x in func_list.split(",") if x.strip()]
        bv = get_bv()
        lines: List[str] = []
        try:
            for fn in bv.functions:
                for callee in fn.callees:
                    for n in names:
                        if n.lower() in callee.name.lower():
                            lines.append(
                                f"caller 0x{int(fn.start):x} {fn.name} -> "
                                f"0x{int(callee.start):x} {callee.name}"
                            )
            return "\n".join(lines[:2000]) if lines else "(none)"
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def get_data_flow(function: str, var_name: str) -> str:
        """Best-effort variable use sites in MLIL SSA (if available)."""
        bv = get_bv()
        try:
            fn = resolve_function(bv, function)
            mlil = fn.mlil
            if mlil is None:
                return "(no mlil)"
            ssa = mlil.ssa_form
            if ssa is None:
                return "(no ssa)"
            lines: List[str] = []
            for i in range(len(ssa)):
                instr = ssa[i]
                st = str(instr)
                if var_name in st:
                    lines.append(f"insn {i}: {st}")
            return "\n".join(lines[:500]) if lines else "(no matches)"
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def get_taint_sources(address_or_name: str) -> str:
        """Heuristic: calls and reads that may be external input."""
        bv = get_bv()
        try:
            fn = resolve_function(bv, address_or_name)
            lines: List[str] = []
            mlil = fn.mlil
            if mlil is None:
                return "(no mlil)"
            for i in range(len(mlil)):
                instr = mlil[i]
                s = str(instr).lower()
                if "call" in s or "syscall" in s or "read" in s or "recv" in s:
                    lines.append(f"insn {i}: {instr}")
            return "\n".join(lines[:200]) if lines else "(none)"
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def find_buffer_operations(address_or_name: str) -> str:
        """Heuristic: memcpy/memset/strcpy-like MLIL patterns."""
        bv = get_bv()
        try:
            fn = resolve_function(bv, address_or_name)
            mlil = fn.mlil
            if mlil is None:
                return "(no mlil)"
            keys = ("memcpy", "memmove", "memset", "strcpy", "strncpy", "sprintf")
            lines: List[str] = []
            for i in range(len(mlil)):
                st = str(mlil[i]).lower()
                if any(k in st for k in keys):
                    lines.append(f"insn {i}: {mlil[i]}")
            return "\n".join(lines[:500]) if lines else "(none)"
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def compare_functions(func_a: str, func_b: str) -> str:
        """Simple HLIL text similarity diff."""
        bv = get_bv()
        try:
            fa = resolve_function(bv, func_a)
            fb = resolve_function(bv, func_b)
            ta = str(fa.hlil or "").splitlines()
            tb = str(fb.hlil or "").splitlines()
            sm = difflib.SequenceMatcher(a=ta, b=tb)
            ratio = sm.ratio()
            diff = "\n".join(
                difflib.unified_diff(ta, tb, lineterm="", fromfile=func_a, tofile=func_b)
            )
            return json.dumps(
                {"similarity": ratio, "diff_excerpt": diff[:8000]},
                ensure_ascii=False,
            )
        except Exception as e:
            return f"error: {e}"
