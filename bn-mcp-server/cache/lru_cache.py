from __future__ import annotations

from collections import OrderedDict
from threading import RLock
from typing import Any, Callable, Hashable, Optional, Tuple


class LRUCache:
    def __init__(self, max_size: int = 500):
        self._max = max(1, int(max_size))
        self._data: "OrderedDict[Hashable, Any]" = OrderedDict()
        self._lock = RLock()

    def get(self, key: Hashable) -> Tuple[bool, Any]:
        with self._lock:
            if key not in self._data:
                return False, None
            self._data.move_to_end(key)
            return True, self._data[key]

    def set(self, key: Hashable, value: Any) -> None:
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
            self._data[key] = value
            while len(self._data) > self._max:
                self._data.popitem(last=False)

    def invalidate_prefix(self, prefix: str) -> None:
        with self._lock:
            keys = [k for k in self._data if str(k).startswith(prefix)]
            for k in keys:
                del self._data[k]

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
