"""Client HTTP partagé par tous les adaptateurs : cache, rate-limit et retry."""

import asyncio
import hashlib
import json
import logging
import random
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from typing import Any

import httpx

from explora.core.cache import Cache, NullCache
from explora.core.errors import SourceError, SourceUnavailableError
from explora.core.ratelimit import RateLimiter

logger = logging.getLogger(__name__)

RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})

Params = Mapping[str, str | int | float | list[str] | None]
"""Une liste répète le paramètre (`?TSH=200&TSH=_T`)."""


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 4
    backoff_base_s: float = 0.5
    backoff_max_s: float = 30.0

    def delay(self, attempt: int, retry_after: float | None = None) -> float:
        """Délai avant la tentative `attempt + 1` (backoff exponentiel + jitter)."""
        if retry_after is not None:
            return min(retry_after, self.backoff_max_s)
        exp: float = self.backoff_base_s * 2 ** (attempt - 1)
        return min(exp + random.uniform(0, self.backoff_base_s), self.backoff_max_s)


def _retry_after(response: httpx.Response) -> float | None:
    value = response.headers.get("Retry-After")
    if value is None:
        return None
    try:
        return max(float(value), 0.0)
    except ValueError:
        return None


class SourceClient:
    """Client d'une source REST.

    Chaque adaptateur reçoit un `SourceClient` configuré pour sa source : les
    réponses sont mises en cache, les appels sont limités en débit et les
    erreurs transitoires (timeouts, 429, 5xx) sont rejouées.
    """

    def __init__(
        self,
        source: str,
        base_url: str,
        *,
        rate_limiter: RateLimiter | None = None,
        cache: Cache | None = None,
        cache_ttl_s: float = 24 * 3600,
        retry: RetryPolicy | None = None,
        timeout_s: float = 15.0,
        user_agent: str = "explora",
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.source = source
        self._limiter = rate_limiter
        self._cache: Cache = cache or NullCache()
        self._cache_ttl_s = cache_ttl_s
        self._retry = retry or RetryPolicy()
        self._sleep = sleep
        self._http = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout_s,
            headers={"User-Agent": user_agent},
            transport=transport,
            follow_redirects=True,
        )

    async def __aenter__(self) -> "SourceClient":
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._http.aclose()

    def _cache_key(self, path: str, params: Params | None) -> str:
        clean = {k: v for k, v in (params or {}).items() if v is not None}
        raw = json.dumps([self.source, path, clean], sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()

    async def get_json(self, path: str, params: Params | None = None) -> Any:
        """GET JSON avec cache ; lève `SourceError` ou `SourceUnavailableError`."""
        key = self._cache_key(path, params)
        cached = await self._cache.get(key)
        if cached is not None:
            return cached
        response = await self._request("GET", path, params)
        try:
            data = response.json()
        except ValueError as exc:
            raise SourceError(self.source, f"réponse JSON invalide pour {path}") from exc
        await self._cache.set(key, data, self._cache_ttl_s)
        return data

    async def get_text(
        self, path: str, params: Params | None = None, *, fallback_encoding: str | None = None
    ) -> str:
        """GET texte brut (CSV...) avec cache.

        Le contenu est décodé en UTF-8 (BOM retiré). Certains fichiers publics sont
        servis en `charset=utf-8` alors qu'ils sont encodés en Windows-1252 : avec
        `fallback_encoding`, on se rabat sur cet encodage si l'UTF-8 échoue.
        """
        key = "text:" + self._cache_key(path, params)
        cached = await self._cache.get(key)
        if cached is not None:
            return str(cached)
        response = await self._request("GET", path, params)
        try:
            text = response.content.decode("utf-8-sig")
        except UnicodeDecodeError:
            if fallback_encoding is None:
                text = response.text
            else:
                text = response.content.decode(fallback_encoding)
        await self._cache.set(key, text, self._cache_ttl_s)
        return text

    async def _request(self, method: str, path: str, params: Params | None) -> httpx.Response:
        clean = {k: v for k, v in (params or {}).items() if v is not None}
        last_error = "aucune tentative"
        for attempt in range(1, self._retry.max_attempts + 1):
            if self._limiter is not None:
                await self._limiter.acquire()
            retry_after: float | None = None
            try:
                response = await self._http.request(method, path, params=clean)
            except httpx.TransportError as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            else:
                if response.is_success:
                    return response
                if response.status_code not in RETRYABLE_STATUS:
                    raise SourceError(
                        self.source,
                        f"HTTP {response.status_code} sur {path}",
                        status_code=response.status_code,
                    )
                last_error = f"HTTP {response.status_code}"
                retry_after = _retry_after(response)
            if attempt < self._retry.max_attempts:
                delay = self._retry.delay(attempt, retry_after)
                logger.warning(
                    "%s: %s sur %s, nouvelle tentative dans %.1fs",
                    self.source,
                    last_error,
                    path,
                    delay,
                )
                await self._sleep(delay)
        raise SourceUnavailableError(
            self.source, f"{last_error} après {self._retry.max_attempts} tentatives sur {path}"
        )
