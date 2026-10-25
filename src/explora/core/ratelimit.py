"""Limiteur de débit asynchrone (token bucket)."""

import asyncio
import time
from collections.abc import Awaitable, Callable


class RateLimiter:
    """Autorise `rate` requêtes par seconde, avec des rafales jusqu'à `burst`.

    L'horloge et la fonction d'attente sont injectables pour des tests déterministes.
    """

    def __init__(
        self,
        rate: float,
        burst: int = 1,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        if rate <= 0:
            raise ValueError("rate doit être strictement positif")
        if burst < 1:
            raise ValueError("burst doit valoir au moins 1")
        self.rate = rate
        self.burst = burst
        self._clock = clock
        self._sleep = sleep
        self._tokens = float(burst)
        self._updated_at = clock()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = self._clock()
        self._tokens = min(self.burst, self._tokens + (now - self._updated_at) * self.rate)
        self._updated_at = now

    async def acquire(self) -> None:
        async with self._lock:
            self._refill()
            if self._tokens < 1:
                await self._sleep((1 - self._tokens) / self.rate)
                self._refill()
            self._tokens -= 1
