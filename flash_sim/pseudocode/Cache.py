# -*- coding: utf-8 -*-
"""以 page(lpa) 为单位的 cache 存储，供 Cache_Manager 使用。"""

from typing import Optional

PAGE_SIZE = 4096


class Cache:
    def __init__(self, max_entries: int = 1024):
        self._store: dict[int, bytes] = {}
        self._lru: list[int] = []
        self._max_entries = max_entries

    def get(self, lpa: int) -> Optional[bytes]:
        if lpa not in self._store:
            return None
        self._lru.remove(lpa)
        self._lru.insert(0, lpa)
        return self._store[lpa]

    def put(self, lpa: int, data: bytes) -> None:
        if lpa in self._store:
            self._lru.remove(lpa)
        else:
            while len(self._store) >= self._max_entries and self._lru:
                evict = self._lru.pop()
                del self._store[evict]
        self._store[lpa] = data
        self._lru.insert(0, lpa)
