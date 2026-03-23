from __future__ import annotations

from typing import Any, Dict, Optional

from .lru_cache import LRUCache


class CFGCache:
    def __init__(self, max_size: int = 500):
        self._cache = LRUCache(max_size)

    def key(self, bv_id: int, func_start: int) -> str:
        return f"cfg:{bv_id}:{func_start:x}"

    def get(self, bv_id: int, func_start: int) -> tuple[bool, Optional[Dict[str, Any]]]:
        return self._cache.get(self.key(bv_id, func_start))

    def set(self, bv_id: int, func_start: int, data: Dict[str, Any]) -> None:
        self._cache.set(self.key(bv_id, func_start), data)

    def invalidate_function(self, bv_id: int, func_start: int) -> None:
        self._cache.invalidate_prefix(f"cfg:{bv_id}:{func_start:x}")
