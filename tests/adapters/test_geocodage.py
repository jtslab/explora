"""Réponse GeoJSON réelle du géocodeur de la Géoplateforme (voir `tests/fixtures`)."""

from collections.abc import Callable

import respx

from explora.adapters.geocodage import GeocodageAdapter
from explora.core.http import SourceClient
from tests.conftest import fixture_json

REPONSE = fixture_json("geocodage_search_rennes.json")


@respx.mock
async def test_search(make_client: Callable[..., SourceClient]) -> None:
    route = respx.get("https://geo.test/search").respond(json=REPONSE)
    async with make_client("https://geo.test") as client:
        results = await GeocodageAdapter(client).search("rennes", limit=1, type="municipality")
    assert route.calls.last.request.url.params["type"] == "municipality"
    assert "citycode" not in route.calls.last.request.url.params
    assert results[0].code_insee == "35238"
    assert results[0].point.lon == -1.68365
    assert results[0].code_postal == "35000"


@respx.mock
async def test_search_vide(make_client: Callable[..., SourceClient]) -> None:
    respx.get("https://geo.test/search").respond(json={"features": []})
    async with make_client("https://geo.test") as client:
        assert await GeocodageAdapter(client).search("zzzz") == []
