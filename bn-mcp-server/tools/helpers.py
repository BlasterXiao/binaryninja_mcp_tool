from __future__ import annotations

import re
from typing import Any, Callable, List, Optional, Tuple, TypeVar

T = TypeVar("T")


def parse_address(s: str) -> int:
    s = s.strip()
    if s.startswith("0x") or s.startswith("0X"):
        return int(s, 16)
    if re.match(r"^[0-9]+$", s):
        return int(s, 10)
    raise ValueError(f"Not a valid address: {s}")


def coerce_address(addr: int | str) -> int:
    """Accept int or decimal/hex string (e.g. ``0x401000``) for MCP tool args.

    LLM clients often pass addresses as JSON strings; Pydantic rejects ``0x...``
    when the schema is ``int`` only.
    """
    if isinstance(addr, int):
        return addr
    if isinstance(addr, str):
        return parse_address(addr)
    raise TypeError(f"address must be int or str, got {type(addr).__name__}")


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


def coalesce_address_or_name(
    address_or_name: str | None = None,
    name: str | None = None,
) -> str | None:
    """Resolve function target from MCP args.

    Some clients send ``name`` instead of ``address_or_name``. Prefer a
    non-empty ``address_or_name`` when both are present.
    """
    a = address_or_name.strip() if isinstance(address_or_name, str) else ""
    n = name.strip() if isinstance(name, str) else ""
    out = a or n
    return out if out else None


def run_on_main(fn: Callable[[], T]) -> T:
    """Execute fn on Binary Ninja main thread and capture its return value.

    ``execute_on_main_thread_and_wait`` is void – it discards the
    callback's return value.  We work around this by storing the result
    (or exception) in a closure-accessible list.
    """
    import binaryninja.mainthread as mainthread

    _result: List[Any] = [None]
    _exc: List[Optional[BaseException]] = [None]

    def _wrapper():
        try:
            _result[0] = fn()
        except BaseException as e:
            _exc[0] = e

    mainthread.execute_on_main_thread_and_wait(_wrapper)

    if _exc[0] is not None:
        raise _exc[0]
    return _result[0]


def parse_type_safe(bv, type_str: str):
    """Resolve a type name/string via BN, supporting C primitives."""
    ty = bv.get_type_by_name(type_str)
    if ty is not None:
        return ty
    try:
        result = bv.parse_type_string(type_str)
        if result is not None:
            if isinstance(result, tuple):
                return result[0]
            return result
    except Exception:
        pass
    import binaryninja as bn
    _BUILTINS = {
        "char": bn.types.Type.int(1, True),
        "unsigned char": bn.types.Type.int(1, False),
        "uint8_t": bn.types.Type.int(1, False),
        "int8_t": bn.types.Type.int(1, True),
        "short": bn.types.Type.int(2, True),
        "unsigned short": bn.types.Type.int(2, False),
        "uint16_t": bn.types.Type.int(2, False),
        "int16_t": bn.types.Type.int(2, True),
        "int": bn.types.Type.int(4, True),
        "unsigned int": bn.types.Type.int(4, False),
        "uint32_t": bn.types.Type.int(4, False),
        "int32_t": bn.types.Type.int(4, True),
        "long long": bn.types.Type.int(8, True),
        "unsigned long long": bn.types.Type.int(8, False),
        "uint64_t": bn.types.Type.int(8, False),
        "int64_t": bn.types.Type.int(8, True),
        "float": bn.types.Type.float(4),
        "double": bn.types.Type.float(8),
        "void": bn.types.Type.void(),
        "bool": bn.types.Type.bool(),
    }
    norm = type_str.strip().lower()
    if norm in _BUILTINS:
        return _BUILTINS[norm]
    return None


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
