"""Construction des adaptateurs pour l'API (surchargeable dans les tests)."""

from collections.abc import AsyncIterator

from explora.adapters.geo_api import GeoApiAdapter
from explora.core.cache import MemoryCache
from explora.core.config import get_settings
from explora.core.http import SourceClient
from explora.core.ratelimit import RateLimiter

_cache = MemoryCache()


async def geo_api() -> AsyncIterator[GeoApiAdapter]:
    settings = get_settings()
    async with SourceClient(
        GeoApiAdapter.info.id,
        settings.geo_api_url,
        rate_limiter=RateLimiter(rate=10, burst=10),
        cache=_cache,
        cache_ttl_s=settings.cache_ttl_s,
        timeout_s=settings.http_timeout_s,
        user_agent=settings.http_user_agent,
    ) as client:
        yield GeoApiAdapter(client)
