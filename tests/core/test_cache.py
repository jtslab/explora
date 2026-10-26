from pathlib import Path

from explora.core.cache import FileCache, MemoryCache
from tests.conftest import FakeClock


async def test_memory_cache_expire(clock: FakeClock) -> None:
    cache = MemoryCache(clock=clock)
    await cache.set("k", {"a": 1}, ttl_s=10)
    assert await cache.get("k") == {"a": 1}
    clock.now = 10
    assert await cache.get("k") is None


async def test_memory_cache_cle_absente() -> None:
    assert await MemoryCache().get("absente") is None


async def test_file_cache_survit_au_redemarrage(tmp_path: Path, clock: FakeClock) -> None:
    await FileCache(tmp_path, clock=clock).set("text:abc", ["é", 1], ttl_s=10)
    relu = FileCache(tmp_path, clock=clock)
    assert await relu.get("text:abc") == ["é", 1]
    clock.now = 10
    assert await relu.get("text:abc") is None
    assert not any(tmp_path.iterdir())  # noqa: ASYNC240


async def test_file_cache_fichier_illisible(tmp_path: Path) -> None:
    (tmp_path / "k.json").write_text("{tronqué", encoding="utf-8")
    assert await FileCache(tmp_path).get("k") is None
