from __future__ import annotations

import re
from typing import List, Optional

from .helpers import coerce_address, safe_str


def register(mcp, get_bv) -> None:
    @mcp.tool()
    def list_strings(min_length: int = 4, encoding: str = "utf-8") -> str:
        """List strings in binary (best-effort encoding filter)."""
        bv = get_bv()
        try:
            lines: List[str] = []
            for s in bv.strings:
                try:
                    if len(s.value) < min_length:
                        continue
                    raw = s.value
                    if isinstance(raw, bytes):
                        text = raw.decode(encoding, errors="replace")
                    else:
                        text = str(raw)
                    lines.append(
                        f"0x{int(s.start):x}\t{len(s.value)}\t{text[:200]}"
                    )
                except Exception as ex:
                    lines.append(f"<str err {ex}>")
            return "\n".join(lines[:3000]) if lines else "(none)"
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def search_string(
        keyword: str | None = None,
        pattern: str | None = None,
        regex: bool = False,
        limit: int = 500,
    ) -> str:
        """Search substring (or regex) in discovered strings.

        Args:
            keyword: substring to search (case-insensitive).
            pattern: alias for keyword.
            regex: if True, treat the search term as a Python regex.
            limit: max results to return (default 500).
        """
        kw_source = pattern if pattern is not None else keyword
        if kw_source is None or str(kw_source).strip() == "":
            return "error: missing required argument: keyword or pattern"
        bv = get_bv()
        kw = str(kw_source)
        compiled_re = None
        if regex:
            try:
                compiled_re = re.compile(kw, re.IGNORECASE)
            except re.error as e:
                return f"error: invalid regex: {e}"
        else:
            kw = kw.lower()
        cap = max(1, min(limit, 5000))
        try:
            lines: List[str] = []
            for s in bv.strings:
                try:
                    raw = s.value
                    if isinstance(raw, bytes):
                        text = raw.decode("utf-8", errors="replace")
                    else:
                        text = str(raw)
                    if compiled_re:
                        if not compiled_re.search(text):
                            continue
                    else:
                        if kw not in text.lower():
                            continue
                    lines.append(f"0x{int(s.start):x}\t{text[:300]}")
                    if len(lines) >= cap:
                        break
                except Exception:
                    continue
            return "\n".join(lines) if lines else "(no matches)"
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def get_data_at(address: int | str) -> str:
        """Data variable at address. ``address`` may be int or hex string (e.g. ``0x463474``)."""
        bv = get_bv()
        try:
            addr = coerce_address(address)
            var = bv.get_data_var_at(addr)
            if var is None:
                return "(none)"
            return f"{var.name}\t{safe_str(var.type)}\t{safe_str(var)}"
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def list_data_variables() -> str:
        """List defined data variables."""
        bv = get_bv()
        try:
            lines: List[str] = []
            dvs = getattr(bv, "data_vars", None)
            if dvs is None:
                return "(data_vars not available)"
            for addr, dv in dvs.items():
                try:
                    lines.append(
                        f"0x{int(addr):x}\t{getattr(dv, 'name', '')}\t{safe_str(getattr(dv, 'type', ''))}"
                    )
                except Exception as ex:
                    lines.append(f"<dv err {ex}>")
            return "\n".join(lines[:3000]) if lines else "(none)"
        except Exception as e:
            return f"error: {e}"

    @mcp.tool()
    def search_bytes(pattern: str) -> str:
        """Search hex bytes (e.g. '4883ec20') or regex on bytes; returns match addresses."""
        bv = get_bv()
        try:
            pat = pattern.strip()
            if re.match(r"^[0-9a-fA-F]+$", pat.replace(" ", "")) and len(pat.replace(" ", "")) % 2 == 0:
                needle = bytes.fromhex(pat.replace(" ", ""))
                hits: List[int] = []
                # simple scan (slow on huge binaries)
                step = max(1, len(needle) // 4)
                for seg in bv.segments:
                    try:
                        data = bv.read(seg.start, seg.end - seg.start)
                        off = 0
                        while True:
                            i = data.find(needle, off)
                            if i < 0:
                                break
                            hits.append(seg.start + i)
                            off = i + 1
                            if len(hits) > 500:
                                break
                    except Exception:
                        continue
                return "\n".join(f"0x{x:x}" for x in hits) if hits else "(no matches)"
            return "error: only hex byte search implemented in this pattern"
        except Exception as e:
            return f"error: {e}"
