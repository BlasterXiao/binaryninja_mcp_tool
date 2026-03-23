"""Global runtime state: caches, last patch undo token (optional)."""
from __future__ import annotations

import threading
from typing import Any, Optional

from .cache import CFGCache, HLILCache, SymbolCache

_lock = threading.RLock()
_hlil_cache: Optional[HLILCache] = None
_symbol_cache: Optional[SymbolCache] = None
_cfg_cache: Optional[CFGCache] = None
_last_undo_token: Any = None


def init_caches(hlil_size: int = 500, cfg_size: int = 500) -> None:
    global _hlil_cache, _symbol_cache, _cfg_cache
    with _lock:
        _hlil_cache = HLILCache(hlil_size)
        _symbol_cache = SymbolCache()
        _cfg_cache = CFGCache(cfg_size)


def hlil_cache() -> HLILCache:
    return _hlil_cache or HLILCache()


def symbol_cache() -> SymbolCache:
    return _symbol_cache or SymbolCache()


def cfg_cache() -> CFGCache:
    return _cfg_cache or CFGCache()


def invalidate_after_write(bv) -> None:
    try:
        bid = id(bv)
        hlil_cache().invalidate_binary(bid)
        symbol_cache().invalidate(bid)
    except Exception:
        pass
