from __future__ import annotations

import json
from typing import List, Optional, Set

from .helpers import coerce_address, coalesce_address_or_name, resolve_function, safe_str


def register(mcp, get_bv) -> None:
    @mcp.tool()
    def get_code_xrefs_to(address: int | str) -> str:
        """Code references to address."""
        bv = get_bv()
        try:
            addr = coerce_address(address)
            lines: List[str] = []
            getter = getattr(bv, "get_code_refs_to", None) or getattr(bv, "get_code_refs", None)
            if getter is None:
                return "error: no code ref API"
            for ref in getter(addr):
                try:
                    ra = int(getattr(ref, "address", None) or getattr(ref, "addr", 0))
                    fn = bv.get_function_at(ra)
                    fname = fn.name if fn else "?"
                    lines.append(f"0x{ra:x}\t{fname}\t{safe_str(ref)}")
                except Exception as ex:
                    lines.append(f"<xref err {ex}>")
            return "\n".join(lines) if lines else "(none)"
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def get_code_xrefs_from(address: int | str) -> str:
        """Outgoing code references from address."""
        bv = get_bv()
        try:
            addr = coerce_address(address)
            lines: List[str] = []
            getter = getattr(bv, "get_code_refs_from", None)
            if getter is None:
                return "error: no get_code_refs_from"
            for ref in getter(addr):
                ra = int(getattr(ref, "address", None) or getattr(ref, "addr", 0))
                lines.append(f"0x{ra:x}\t{safe_str(ref)}")
            return "\n".join(lines) if lines else "(none)"
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def get_data_xrefs_to(address: int | str) -> str:
        """Data references to address."""
        bv = get_bv()
        try:
            addr = coerce_address(address)
            lines: List[str] = []
            getter = getattr(bv, "get_data_refs_to", None) or getattr(bv, "get_data_refs", None)
            if getter is None:
                return "error: no data ref API"
            for ref in getter(addr):
                ra = int(getattr(ref, "address", None) or getattr(ref, "addr", 0))
                lines.append(f"0x{ra:x}\t{safe_str(ref)}")
            return "\n".join(lines) if lines else "(none)"
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def get_data_xrefs_from(address: int | str) -> str:
        """Outgoing data references from address."""
        bv = get_bv()
        try:
            addr = coerce_address(address)
            lines: List[str] = []
            getter = getattr(bv, "get_data_refs_from", None)
            if getter is None:
                return "error: no get_data_refs_from"
            for ref in getter(addr):
                ra = int(getattr(ref, "address", None) or getattr(ref, "addr", 0))
                lines.append(f"0x{ra:x}\t{safe_str(ref)}")
            return "\n".join(lines) if lines else "(none)"
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def get_call_graph(
        address_or_name: str | None = None,
        depth: int = 3,
        *,
        name: str | None = None,
    ) -> str:
        """BFS call graph (callees) as JSON nodes/edges."""
        bv = get_bv()
        try:
            key = coalesce_address_or_name(address_or_name, name)
            if not key:
                return "error: provide address_or_name or name"
            root = resolve_function(bv, key)
            nodes: List[dict] = []
            edges: List[dict] = []
            seen: Set[int] = set()
            frontier = [(root, 0)]
            while frontier:
                fn, d = frontier.pop()
                sid = int(fn.start)
                if sid in seen:
                    continue
                seen.add(sid)
                nodes.append({"id": sid, "name": fn.name})
                if d >= depth:
                    continue
                for c in fn.callees:
                    cid = int(c.start)
                    edges.append({"from": sid, "to": cid})
                    if cid not in seen:
                        frontier.append((c, d + 1))
            return json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False)
        except Exception as e:
            return f"error: {e}"
