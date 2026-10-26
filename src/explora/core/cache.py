"""Cache clé/valeur avec expiration.

Le protocole `Cache` permet de brancher plus tard Redis ou un cache disque
sans toucher aux adaptateurs.
"""

import json
import time
from collections.abc import Callable
from pathlib import Path
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


class FileCache:
    """Cache disque en JSON : un job d'ingestion relancé ne rappelle pas les sources.

    Les clés produites par `SourceClient` sont des empreintes hexadécimales, utilisables
    telles quelles comme noms de fichiers. L'expiration suit l'horloge murale.
    """

    def __init__(self, directory: Path, clock: Callable[[], float] = time.time) -> None:
        self._dir = directory
        self._clock = clock
        directory.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        return self._dir / f"{key.replace(':', '_')}.json"

    async def get(self, key: str) -> Any | None:
        path = self._path(key)
        try:
            expires_at, value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if self._clock() >= expires_at:
            path.unlink(missing_ok=True)
            return None
        return value

    async def set(self, key: str, value: Any, ttl_s: float) -> None:
        path = self._path(key)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps([self._clock() + ttl_s, value]), encoding="utf-8")
        tmp.replace(path)
