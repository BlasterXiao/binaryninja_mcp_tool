from __future__ import annotations

from typing import Any, Dict, List, Optional

from .. import context


def register(mcp, get_bv) -> None:
    @mcp.tool()
    def get_binary_info() -> str:
        """Return metadata for the active BinaryView (path, arch, platform, base, size, entry)."""
        bv = get_bv()
        try:
            path = getattr(bv.file, "filename", None) or ""
            arch = str(bv.arch.name) if bv.arch else ""
            plat = str(bv.platform) if bv.platform else ""
            base = int(bv.start) if hasattr(bv, "start") else 0
            length = int(bv.length) if hasattr(bv, "length") else 0
            ep = int(bv.entry_point) if hasattr(bv, "entry_point") and bv.entry_point else 0
            return (
                f"file: {path}\n"
                f"arch: {arch}\n"
                f"platform: {plat}\n"
                f"start: 0x{base:x}\n"
                f"length: {length}\n"
                f"entry_point: 0x{ep:x}"
            )
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def list_binary_views() -> str:
        """List open BinaryView ids and file names."""
        rows = context.list_open_views()
        if not rows:
            return "(no tracked views; start server from a loaded binary or open a file)"
        return "\n".join(f"{vid}\t{name}" for vid, name in rows)

    @mcp.tool()
    def switch_binary_view(view_id: str) -> str:
        """Switch active view by view_id from list_binary_views."""
        ok = context.switch_binary_view(view_id)
        return "ok" if ok else "failed: unknown view_id"

    @mcp.tool()
    def get_segments(view_id: Optional[str] = None) -> str:
        """List memory segments (name, start, length, r/w/x)."""
        bv = get_bv(view_id)
        lines: List[str] = []
        try:
            for seg in bv.segments:
                try:
                    name = getattr(seg, "name", "") or ""
                    start = int(seg.start)
                    length = int(seg.end - seg.start)
                    r = getattr(seg, "readable", False)
                    w = getattr(seg, "writable", False)
                    x = getattr(seg, "executable", False)
                    lines.append(f"0x{start:x}\t+{length:x}\t{name}\tR={r} W={w} X={x}")
                except Exception as ex:
                    lines.append(f"<segment error: {ex}>")
        except Exception as e:
            return f"error: {e}"
        return "\n".join(lines) if lines else "(no segments)"

    @mcp.tool()
    def get_sections(view_id: Optional[str] = None) -> str:
        """List ELF/PE sections if available."""
        bv = get_bv(view_id)
        lines: List[str] = []
        try:
            if hasattr(bv, "sections"):
                for sec in bv.sections:
                    try:
                        name = getattr(sec, "name", "") or ""
                        start = int(sec.start)
                        length = int(sec.end - sec.start)
                        lines.append(f"0x{start:x}\t+{length:x}\t{name}")
                    except Exception as ex:
                        lines.append(f"<section error: {ex}>")
        except Exception as e:
            return f"error: {e}"
        return "\n".join(lines) if lines else "(no sections or not supported)"

    @mcp.tool()
    def read_memory(address: int, length: int) -> str:
        """Read raw bytes at address (hex string)."""
        bv = get_bv()
        try:
            data = bv.read(address, length)
            return data.hex()
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def write_memory(address: int, data: str) -> str:
        """Write raw bytes (hex string, no spaces) at address. Uses main thread."""
        from .helpers import run_on_main

        from .. import state

        def _do():
            bv = get_bv()
            raw = bytes.fromhex(data.replace(" ", ""))
            bv.write(address, raw)
            state.invalidate_after_write(bv)
            return "ok"

        try:
            return run_on_main(_do)
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def get_entry_points() -> str:
        """List entry point addresses."""
        bv = get_bv()
        try:
            eps: List[int] = []
            if hasattr(bv, "entry_point") and bv.entry_point:
                eps.append(int(bv.entry_point))
            return "\n".join(f"0x{x:x}" for x in eps) if eps else "(none)"
        except Exception as e:
            return f"error: {e}"
