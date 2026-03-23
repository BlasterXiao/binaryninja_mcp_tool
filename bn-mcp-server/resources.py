"""Optional MCP Resources (binja:// URIs)."""

from __future__ import annotations


def register(mcp, get_bv) -> None:
    r = getattr(mcp, "resource", None)
    if r is None:
        return
    try:

        @r("binja://binary/info")
        def _binary_info() -> str:
            bv = get_bv()
            return str(
                {
                    "file": getattr(bv.file, "filename", ""),
                    "arch": str(bv.arch.name) if bv.arch else "",
                    "platform": str(bv.platform) if bv.platform else "",
                }
            )

        @r("binja://functions/list")
        def _functions_list() -> str:
            bv = get_bv()
            return "\n".join(f"0x{int(f.start):x}\t{f.name}" for f in bv.functions[:5000])

        @r("binja://symbols/table")
        def _symbols() -> str:
            bv = get_bv()
            return "\n".join(
                f"0x{int(s.address):x}\t{s.name}" for s in bv.get_symbols()[:5000]
            )

        @r("binja://strings/all")
        def _strings() -> str:
            bv = get_bv()
            lines = []
            for s in bv.strings:
                try:
                    lines.append(f"0x{int(s.start):x}\t{s.value!r}")
                except Exception:
                    pass
            return "\n".join(lines[:5000])

        @r("binja://types/all")
        def _types() -> str:
            bv = get_bv()
            return "\n".join(str(t) for t in list(bv.types)[:2000])

        @r("binja://analysis/progress")
        def _progress() -> str:
            from .tools import analysis as an

            return an.get_analysis_progress_impl(get_bv())

    except Exception:
        pass
