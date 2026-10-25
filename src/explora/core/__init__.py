"""Socle commun : client HTTP résilient, cache, rate-limit et contrat des adaptateurs."""

from explora.core.adapter import SourceAdapter, SourceInfo
from explora.core.cache import Cache, MemoryCache
from explora.core.errors import SourceError, SourceUnavailableError
from explora.core.http import RetryPolicy, SourceClient
from explora.core.ratelimit import RateLimiter

__all__ = [
    "Cache",
    "MemoryCache",
    "RateLimiter",
    "RetryPolicy",
    "SourceAdapter",
    "SourceClient",
    "SourceError",
    "SourceInfo",
    "SourceUnavailableError",
]
