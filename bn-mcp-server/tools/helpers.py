from __future__ import annotations

import re
from typing import Any, Callable, List, Optional, TypeVar

T = TypeVar("T")


def parse_address(s: str) -> int:
    s = s.strip()
    if s.startswith("0x") or s.startswith("0X"):
        return int(s, 16)
    if re.match(r"^[0-9]+$", s):
        return int(s, 10)
    raise ValueError(f"Not a valid address: {s}")


def resolve_function(bv, address_or_name: str):
    """Return Binary Ninja Function from name or address string."""
    s = address_or_name.strip()
    try:
        addr = parse_address(s)
        fn = bv.get_function_at(addr)
        if fn is not None:
            return fn
    except ValueError:
        pass
    funcs = bv.get_functions_by_name(s)
    if funcs:
        return funcs[0]
    # try partial match
    matches = []
    for f in bv.functions:
        if s in f.name or f.name == s:
            matches.append(f)
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(f"Ambiguous function name: {s!r} ({len(matches)} matches)")
    raise ValueError(f"Function not found: {address_or_name!r}")


def run_on_main(fn: Callable[[], T]) -> T:
    """Execute fn on Binary Ninja main thread (required for many mutating operations)."""
    import binaryninja.mainthread as mainthread

    return mainthread.execute_on_main_thread_and_wait(fn)


def il_to_lines(il_func) -> List[str]:
    """Serialize IL as list of lines."""
    lines: List[str] = []
    try:
        for i in range(len(il_func)):  # type: ignore
            lines.append(str(il_func[i]))
    except Exception:
        try:
            lines.append(str(il_func))
        except Exception:
            lines.append("<unavailable>")
    return lines


def safe_str(obj: Any) -> str:
    try:
        return str(obj)
    except Exception:
        return repr(obj)


def json_safe(obj: Any) -> Any:
    """Best-effort JSON-serializable conversion."""
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, dict):
        return {str(k): json_safe(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(x) for x in obj]
    return str(obj)
