from __future__ import annotations

from typing import Any, List, Optional

from .lru_cache import LRUCache


class SymbolCache:
    def __init__(self):
        self._cache = LRUCache(max_size=32)

    def key(self, bv_id: int) -> str:
        return f"sym:{bv_id}"

    def get(self, bv_id: int) -> tuple[bool, Optional[List[Any]]]:
        return self._cache.get(self.key(bv_id))

    def set(self, bv_id: int, rows: List[Any]) -> None:
        self._cache.set(self.key(bv_id), rows)

    def invalidate(self, bv_id: int) -> None:
        self._cache.invalidate_prefix(self.key(bv_id))
