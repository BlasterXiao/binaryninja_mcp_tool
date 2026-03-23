from __future__ import annotations

from typing import List, Optional

from .helpers import safe_str

from .. import state


def register(mcp, get_bv) -> None:
    @mcp.tool()
    def list_symbols(type_filter: Optional[str] = None) -> str:
        """List symbols; optional filter: function|data|import|export (best-effort)."""
        bv = get_bv()
        try:
            bid = id(bv)
            hit, cached = state.symbol_cache().get(bid)
            if hit and cached is not None:
                rows = cached
            else:
                rows = list(bv.get_symbols())
                state.symbol_cache().set(bid, rows)
            lines: List[str] = []
            for sym in rows:
                try:
                    st = str(sym.type).lower() if hasattr(sym, "type") else ""
                    name = sym.name
                    addr = int(sym.address) if hasattr(sym, "address") else 0
                    if type_filter:
                        tf = type_filter.lower()
                        if tf not in st and tf not in name.lower():
                            continue
                    lines.append(f"0x{addr:x}\t{st}\t{name}")
                except Exception as ex:
                    lines.append(f"<sym err {ex}>")
            return "\n".join(lines[:5000]) if lines else "(none)"
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def get_symbol_at(address: int) -> str:
        """Symbol at address."""
        bv = get_bv()
        try:
            sym = bv.get_symbol_at(address)
            if sym is None:
                return "(none)"
            return f"{sym.name}\t{safe_str(sym.type)}"
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def list_imports() -> str:
        """Imported symbols."""
        bv = get_bv()
        try:
            lines: List[str] = []
            try:
                import binaryninja as bn

                st = getattr(bn, "SymbolType", None)
                if st is not None:
                    for sym in bv.get_symbols():
                        try:
                            t = sym.type
                            if t in (
                                st.ImportAddressSymbol,
                                st.ImportedFunctionSymbol,
                                st.ImportedDataSymbol,
                            ):
                                lines.append(f"0x{int(sym.address):x}\t{sym.name}")
                        except Exception:
                            continue
            except Exception:
                pass
            if not lines:
                for sym in bv.get_symbols():
                    try:
                        if "import" in str(sym.type).lower():
                            lines.append(f"0x{int(sym.address):x}\t{sym.name}")
                    except Exception:
                        continue
            return "\n".join(lines[:2000]) if lines else "(none; try list_symbols)"
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def list_exports() -> str:
        """Exported symbols (best-effort)."""
        bv = get_bv()
        try:
            lines: List[str] = []
            for sym in bv.get_symbols():
                try:
                    if "export" in str(sym.type).lower():
                        lines.append(f"0x{int(sym.address):x}\t{sym.name}")
                except Exception:
                    continue
            return "\n".join(lines[:2000]) if lines else "(none)"
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def find_symbol_by_name(pattern: str) -> str:
        """Substring search in symbol names."""
        bv = get_bv()
        try:
            pat = pattern.lower()
            lines: List[str] = []
            for sym in bv.get_symbols():
                try:
                    if pat in sym.name.lower():
                        lines.append(f"0x{int(sym.address):x}\t{sym.name}")
                except Exception:
                    continue
            return "\n".join(lines[:500]) if lines else "(no matches)"
        except Exception as e:
            return f"error: {e}"
