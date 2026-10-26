from collections.abc import Callable

import httpx
import pytest
import respx

from explora.core.cache import MemoryCache
from explora.core.errors import SourceError, SourceUnavailableError
from explora.core.http import SourceClient
from tests.conftest import FakeClock

ClientFactory = Callable[..., SourceClient]


@respx.mock
async def test_get_json_ok(make_client: ClientFactory) -> None:
    route = respx.get("https://api.test/x", params={"a": "1"}).respond(json={"ok": True})
    async with make_client() as client:
        assert await client.get_json("/x", {"a": 1, "ignore": None}) == {"ok": True}
    assert route.call_count == 1


@respx.mock
async def test_cache_evite_le_second_appel(make_client: ClientFactory) -> None:
    route = respx.get("https://api.test/x").respond(json=[1, 2])
    async with make_client(cache=MemoryCache()) as client:
        await client.get_json("/x")
        assert await client.get_json("/x") == [1, 2]
    assert route.call_count == 1


@respx.mock
async def test_retry_sur_503_puis_succes(make_client: ClientFactory, clock: FakeClock) -> None:
    route = respx.get("https://api.test/x").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json={"ok": 1})]
    )
    async with make_client() as client:
        assert await client.get_json("/x") == {"ok": 1}
    assert route.call_count == 2
    assert len(clock.sleeps) == 1


@respx.mock
async def test_retry_after_respecte(make_client: ClientFactory, clock: FakeClock) -> None:
    respx.get("https://api.test/x").mock(
        side_effect=[httpx.Response(429, headers={"Retry-After": "7"}), httpx.Response(200, json=1)]
    )
    async with make_client() as client:
        await client.get_json("/x")
    assert clock.sleeps == [7.0]


@respx.mock
async def test_retry_sur_erreur_reseau(make_client: ClientFactory) -> None:
    route = respx.get("https://api.test/x").mock(
        side_effect=[httpx.ConnectTimeout("lent"), httpx.Response(200, json=1)]
    )
    async with make_client() as client:
        assert await client.get_json("/x") == 1
    assert route.call_count == 2


@respx.mock
async def test_abandon_apres_max_tentatives(make_client: ClientFactory) -> None:
    route = respx.get("https://api.test/x").respond(500)
    async with make_client() as client:
        with pytest.raises(SourceUnavailableError, match="3 tentatives"):
            await client.get_json("/x")
    assert route.call_count == 3


@respx.mock
async def test_404_non_rejoue(make_client: ClientFactory) -> None:
    route = respx.get("https://api.test/x").respond(404)
    async with make_client() as client:
        with pytest.raises(SourceError) as info:
            await client.get_json("/x")
    assert info.value.status_code == 404
    assert route.call_count == 1


@respx.mock
async def test_json_invalide(make_client: ClientFactory) -> None:
    respx.get("https://api.test/x").respond(200, text="<html>")
    async with make_client() as client:
        with pytest.raises(SourceError, match="JSON invalide"):
            await client.get_json("/x")


@respx.mock
async def test_get_text(make_client: ClientFactory) -> None:
    respx.get("https://api.test/f.csv").respond(200, text="a;b\n1;2\n")
    async with make_client() as client:
        assert await client.get_text("/f.csv") == "a;b\n1;2\n"
