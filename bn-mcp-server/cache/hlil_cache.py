from __future__ import annotations

from typing import Optional

from .lru_cache import LRUCache


class HLILCache:
    def __init__(self, max_size: int = 500):
        self._cache = LRUCache(max_size)

    def key(self, bv_id: int, func_start: int) -> str:
        return f"{bv_id}:{func_start:x}"

    def get_text(self, bv_id: int, func_start: int) -> tuple[bool, Optional[str]]:
        return self._cache.get(self.key(bv_id, func_start))

    def set_text(self, bv_id: int, func_start: int, text: str) -> None:
        self._cache.set(self.key(bv_id, func_start), text)

    def invalidate_function(self, bv_id: int, func_start: int) -> None:
        self._cache.invalidate_prefix(f"{bv_id}:{func_start:x}")

    def invalidate_binary(self, bv_id: int) -> None:
        self._cache.invalidate_prefix(f"{bv_id}:")
