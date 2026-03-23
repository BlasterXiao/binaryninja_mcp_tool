from __future__ import annotations

import json
from typing import Any, Dict, List

from .helpers import resolve_function, safe_str

from .. import state


def register(mcp, get_bv) -> None:
    @mcp.tool()
    def get_basic_blocks(address_or_name: str) -> str:
        """List basic blocks with successors."""
        bv = get_bv()
        try:
            fn = resolve_function(bv, address_or_name)
            lines: List[str] = []
            for bb in fn.basic_blocks:
                try:
                    succ = [hex(int(s.start)) for s in bb.outgoing_edges]
                    lines.append(
                        f"0x{int(bb.start):x}-0x{int(bb.end):x}\tout={','.join(succ)}"
                    )
                except Exception as ex:
                    lines.append(f"<bb err {ex}>")
            return "\n".join(lines) if lines else "(none)"
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def get_cfg(address_or_name: str) -> str:
        """CFG as JSON nodes/edges (basic blocks)."""
        bv = get_bv()
        try:
            fn = resolve_function(bv, address_or_name)
            bid = id(bv)
            start = int(fn.start)
            hit, cached = state.cfg_cache().get(bid, start)
            if hit and cached is not None:
                return json.dumps(cached, ensure_ascii=False)

            nodes: List[Dict[str, Any]] = []
            edges: List[Dict[str, Any]] = []
            for bb in fn.basic_blocks:
                nid = int(bb.start)
                nodes.append({"id": nid, "start": nid, "end": int(bb.end)})
                edges_iter = getattr(bb, "outgoing_edges", None) or []
                for edge in edges_iter:
                    try:
                        target = getattr(edge, "target", None)
                        if target is None:
                            continue
                        tgt = int(target.start)
                        edges.append(
                            {
                                "from": nid,
                                "to": tgt,
                                "type": safe_str(getattr(edge, "type", "")),
                            }
                        )
                    except Exception:
                        continue
            data = {"nodes": nodes, "edges": edges}
            state.cfg_cache().set(bid, start, data)
            return json.dumps(data, ensure_ascii=False)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def get_dominators(address_or_name: str) -> str:
        """Dominators if available; else approximate from CFG."""
        bv = get_bv()
        try:
            fn = resolve_function(bv, address_or_name)
            doms: Dict[str, Any] = {}
            for bb in fn.basic_blocks:
                if hasattr(bb, "dominators"):
                    doms[str(int(bb.start))] = [
                        int(d.start) for d in bb.dominators  # type: ignore
                    ]
                else:
                    doms[str(int(bb.start))] = []
            return json.dumps(doms, ensure_ascii=False)
        except Exception as e:
            return f"error: {e}"
