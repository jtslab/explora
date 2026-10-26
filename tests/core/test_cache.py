from explora.core.cache import MemoryCache
from tests.conftest import FakeClock


async def test_memory_cache_expire(clock: FakeClock) -> None:
    cache = MemoryCache(clock=clock)
    await cache.set("k", {"a": 1}, ttl_s=10)
    assert await cache.get("k") == {"a": 1}
    clock.now = 10
    assert await cache.get("k") is None


async def test_memory_cache_cle_absente() -> None:
    assert await MemoryCache().get("absente") is None
