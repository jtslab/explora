"""Cache clé/valeur avec expiration.

Le protocole `Cache` permet de brancher plus tard Redis ou un cache disque
sans toucher aux adaptateurs.
"""

import time
from collections.abc import Callable
from typing import Any, Protocol


class Cache(Protocol):
    async def get(self, key: str) -> Any | None: ...

    async def set(self, key: str, value: Any, ttl_s: float) -> None: ...


class MemoryCache:
    """Cache en mémoire, suffisant pour un job d'ingestion ou les tests."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._items: dict[str, tuple[float, Any]] = {}

    async def get(self, key: str) -> Any | None:
        item = self._items.get(key)
        if item is None:
            return None
        expires_at, value = item
        if self._clock() >= expires_at:
            del self._items[key]
            return None
        return value

    async def set(self, key: str, value: Any, ttl_s: float) -> None:
        self._items[key] = (self._clock() + ttl_s, value)


class NullCache:
    """Cache désactivé."""

    async def get(self, key: str) -> Any | None:
        return None

    async def set(self, key: str, value: Any, ttl_s: float) -> None:
        return None
